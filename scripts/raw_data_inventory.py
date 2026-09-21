#!/usr/bin/env python3
"""Recursively inventory the raw data tree.

The scanner records file-level facts for every CSV/PDF and scans selected
fields without loading any source file into memory.  It is intentionally
independent of the later research sample construction.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCRIPT_VERSION = "2.0.0"

FILE_CONFIG: dict[str, dict[str, list[str]]] = {
    "american equities.csv": {
        "dates": ["datadate"],
        "categories": ["marketarea"],
        "key": ["dxlid", "cusip", "isin", "sedol", "indicativefee", "dcbs"],
    },
    "crsp0025(daily).csv": {
        "dates": ["DlyCalDt", "SecurityBegDt", "SecurityEndDt"],
        "categories": ["SecurityType", "SecuritySubType", "ShareType", "PrimaryExch"],
        "key": ["PERMNO", "CUSIP9", "DlyPrc", "DlyCap", "DlyRetx", "DlyVol"],
    },
    "crsp2599(daily).csv": {
        "dates": ["DlyCalDt", "SecurityBegDt", "SecurityEndDt"],
        "categories": ["SecurityType", "SecuritySubType", "ShareType", "PrimaryExch"],
        "key": ["PERMNO", "CUSIP9", "DlyPrc", "DlyCap", "DlyRetx", "DlyVol"],
    },
    "crsp_ stock header information(new).csv": {
        "dates": ["SecInfoStartDt", "SecInfoEndDt", "SecurityBegDt", "SecurityEndDt"],
        "categories": ["SecurityType", "SecuritySubType", "ShareType"],
        "key": ["PERMNO", "CUSIP9", "HdrCUSIP9", "SecurityNm"],
    },
    "crsp_ stock header information(new).csv": {
        "dates": ["SecInfoStartDt", "SecInfoEndDt", "SecurityBegDt", "SecurityEndDt"],
        "categories": ["SecurityType", "SecuritySubType", "ShareType"],
        "key": ["PERMNO", "CUSIP9", "HdrCUSIP9", "SecurityNm"],
    },
    "crsp_stock header information(new).csv": {
        "dates": ["SecInfoStartDt", "SecInfoEndDt", "SecurityBegDt", "SecurityEndDt"],
        "categories": ["SecurityType", "SecuritySubType", "ShareType"],
        "key": ["PERMNO", "CUSIP9", "HdrCUSIP9", "SecurityNm"],
    },
    "crsp_distribution.csv": {
        "dates": ["DisExDt", "DisDeclareDt", "DisRecordDt", "DisPayDt"],
        "categories": ["DisType", "DisOrdinaryFlg"],
        "key": ["DisPERMNO", "DisDivAmt", "DisFacPr"],
    },
    "crsp_delisting.csv": {
        "dates": ["DelistingDt", "DelDtPrc", "DelNextDt"],
        "categories": ["DelActionType", "DelStatusType", "DelReasonType"],
        "key": ["PERMNO", "DelRet", "DelistingDt"],
    },
    "comp_quarterly6126.csv": {
        "dates": ["datadate", "rdq", "reportdate", "ipodate"],
        "categories": ["indfmt", "datafmt", "popsrc", "consol", "fic", "exchg"],
        "key": ["gvkey", "datadate", "conm", "tic", "cusip", "cik"],
    },
    "link.csv": {
        "dates": ["LINKDT", "LINKENDDT", "dldte"],
        "categories": ["LINKPRIM", "LINKTYPE", "linkprim", "linktype"],
        "key": ["gvkey", "LPERMNO", "LPERMCO", "cusip", "LINKDT", "LINKENDDT"],
    },
    "compustat_supplemental_short_interest.csv.csv": {
        "dates": ["datadate", "date", "month"],
        "categories": [],
        "key": ["gvkey", "permno", "cusip", "shortint"],
    },
}


def clean_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "nat", "none", "null", "n/a", "."} else text


def parse_date(value: Any) -> dt.date | None:
    text = clean_value(value)
    if not text:
        return None
    for candidate in (text[:10], text):
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y%m%d"):
            try:
                return dt.datetime.strptime(candidate, fmt).date()
            except ValueError:
                pass
    return None


def fmt_date(value: dt.date | None) -> str:
    return value.isoformat() if value else "-"


def fmt_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(block_size):
            digest.update(chunk)
    return digest.hexdigest()


def hash_and_count_rows(path: Path, block_size: int = 16 * 1024 * 1024) -> tuple[str, int]:
    digest = hashlib.sha256()
    line_count = 0
    last = b""
    with path.open("rb") as handle:
        while chunk := handle.read(block_size):
            digest.update(chunk)
            line_count += chunk.count(b"\n")
            last = chunk[-1:]
    if path.stat().st_size and last != b"\n":
        line_count += 1
    return digest.hexdigest(), max(0, line_count - 1)


def count_physical_rows(path: Path, block_size: int = 16 * 1024 * 1024) -> int:
    """Count data lines.

    These WRDS exports use one record per physical line.  The report makes
    this assumption explicit instead of silently treating line count as a
    fully parsed CSV row count.
    """
    line_count = 0
    last = b""
    with path.open("rb") as handle:
        while chunk := handle.read(block_size):
            line_count += chunk.count(b"\n")
            last = chunk[-1:]
    if path.stat().st_size and last != b"\n":
        line_count += 1
    return max(0, line_count - 1)


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return next(csv.reader(handle), [])


def scan_selected(path: Path, header: list[str], scan_limit: int | None) -> dict[str, Any]:
    config = FILE_CONFIG.get(path.name.lower(), {})
    dates = [x for x in config.get("dates", []) if x in header]
    categories = [x for x in config.get("categories", []) if x in header]
    keys = [x for x in config.get("key", []) if x in header]
    result: dict[str, Any] = {
        "date_min": {x: None for x in dates},
        "date_max": {x: None for x in dates},
        "date_invalid": {x: 0 for x in dates},
        "nonempty": {x: 0 for x in keys},
        "sample": {x: "" for x in keys},
        "categories": {x: Counter() for x in categories},
        "scanned_rows": 0,
    }
    if not (dates or categories or keys):
        return result
    index = {name: i for i, name in enumerate(header)}
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle)
        next(reader, None)
        for row in reader:
            if scan_limit is not None and result["scanned_rows"] >= scan_limit:
                break
            result["scanned_rows"] += 1
            for field in dates:
                value = row[index[field]] if index[field] < len(row) else ""
                if not clean_value(value):
                    continue
                parsed = parse_date(value)
                if parsed is None:
                    result["date_invalid"][field] += 1
                else:
                    current_min = result["date_min"][field]
                    current_max = result["date_max"][field]
                    result["date_min"][field] = parsed if current_min is None or parsed < current_min else current_min
                    result["date_max"][field] = parsed if current_max is None or parsed > current_max else current_max
            for field in keys:
                value = clean_value(row[index[field]] if index[field] < len(row) else "")
                if value:
                    result["nonempty"][field] += 1
                    if not result["sample"][field]:
                        result["sample"][field] = value[:160]
            for field in categories:
                value = clean_value(row[index[field]] if index[field] < len(row) else "")
                if value:
                    result["categories"][field][value] += 1
    return result


def pdf_metadata(path: Path) -> dict[str, str]:
    result = {"size": fmt_bytes(path.stat().st_size), "text": ""}
    executable = shutil.which("pdftotext")
    if not executable:
        result["text"] = "pdftotext unavailable"
        return result
    try:
        proc = subprocess.run(
            [executable, "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        result["text"] = proc.stdout[:12000]
    except Exception as exc:
        result["text"] = f"PDF extraction failed: {exc}"
    return result


def guide_rows_for(raw_dir: Path) -> list[tuple[str, str, str, str]]:
    relative_paths = {
        p.relative_to(raw_dir).as_posix()
        for p in raw_dir.rglob("*")
        if p.is_file()
    }
    lower_paths = {x.lower(): x for x in relative_paths}

    def find(*terms: str) -> list[str]:
        return sorted(
            original
            for lower, original in lower_paths.items()
            if any(term.lower() in lower for term in terms)
        )

    def make(title: str, terms: tuple[str, ...], note: str, status: str = "已获取") -> tuple[str, str, str, str]:
        matches = find(*terms)
        if not matches:
            return title, "（未发现对应文件）", "未获取", note
        evidence = "；".join(f"`{x}`" for x in matches[:4])
        if len(matches) > 4:
            evidence += f"；…（共 {len(matches)} 个）"
        return title, evidence, status, note

    return [
        make("Markit 买方口径借券费", ("american equities.csv",), "文件存在，但仍需核对字段单位、覆盖期和证券匹配。"),
        make("CRSP 日频股票文件", ("daily).csv", "daily.csv"), "可用于普通股筛选、价量信号和收益构造。"),
        make("CRSP 分配表", ("distribution.csv", "dividend"), "用于显式股利事件核验。"),
        make("CRSP 退市文件", ("delisting.csv", "delist"), "用于退市收益处理；原型中单独记录退市限制。"),
        make("CRSP 证券属性表", ("stock header", "dsenames", "attribute"), "用于 CIZ 普通股映射和历史 CUSIP。"),
        make("CRSP 月频", ("monthly", "msf", "月频"), "当前月频面板由日频 CRSP 聚合。"),
        make("Compustat 年度与 Pension Annual", ("funda", "pension"), "当前只有季度 Compustat，不能替代年度点时财务数据。", "部分获取"),
        make("CCM 链接表", ("link.csv",), "按有效日期使用；不等同于完整 JKMP 输入。", "基本具备"),
        make("月度空头兴趣", ("short_interest", "short interest"), "字段定义和覆盖期仍需核对。"),
        make("Chen-Zimmermann 信号面板", ("predictor", "chen", "zimmermann"), "当前检测到相关代码/文件，是否为可执行成品面板需另行确认。", "部分获取"),
        make("DGTW/因子收益", ("dgtw", "factor"), "成品 DGTW/因子文件未发现，后续可自建。", "部分获取"),
        ("课表", "用户说明已发送；证据和日期待补充", "已发送（待补证）", "本次记录不伪造发送凭证。"),
    ]


def md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def build_report(
    raw_dir: Path,
    output: Path,
    records: list[dict[str, Any]],
    pdfs: list[dict[str, Any]],
    started: dt.datetime,
    finished: dt.datetime,
    scan_limit: int | None,
) -> None:
    lines = [
        "# Raw 数据盘点与指南落实核对报告",
        "",
        f"- 扫描目录：`{raw_dir}`",
        f"- 扫描时间：{started.isoformat(timespec='seconds')} 至 {finished.isoformat(timespec='seconds')}",
        f"- 脚本版本：`{SCRIPT_VERSION}`",
        f"- CSV 行数：物理换行计数；选定字段扫描上限：`{scan_limit or '全量'}`",
        "- 处理方式：递归发现文件；CSV 不整体载入内存；文件哈希使用 SHA-256。",
        "- 注意：文件总览中的日期范围只来自选定字段的 scan-limit 抽样，不代表超大 CSV 的全量覆盖期；Markit 完整覆盖请以专门处理输出为准。",
        "",
        "## 文件总览",
        "",
        "| 相对路径 | 类型 | 大小 | 行数 | 列数 | SHA-256 | 选定字段日期范围（scan-limit 内） | 状态 |",
        "|---|---|---:|---:|---:|---|---|---|",
    ]
    for record in records:
        date_ranges = "; ".join(
            f"{field}: {fmt_date(record['scan']['date_min'][field])} ~ {fmt_date(record['scan']['date_max'][field])}"
            for field in record["scan"]["date_min"]
        ) or "-"
        lines.append(
            f"| `{md(record['relative'])}` | CSV | {fmt_bytes(record['size'])} | "
            f"{record['rows']:,} | {len(record['header']):,} | `{record['sha256']}` | "
            f"{md(date_ranges)} | {record['status']} |"
        )
    for record in pdfs:
        lines.append(
            f"| `{md(record['relative'])}` | PDF | {record['meta']['size']} | — | — | "
            f"`{record['sha256']}` | 字段字典/说明 | 完成 |"
        )
    lines += ["", "## 重复文件组", ""]
    hash_groups: dict[str, list[str]] = defaultdict(list)
    for record in records + pdfs:
        if record["sha256"]:
            hash_groups[record["sha256"]].append(record["relative"])
    duplicates = [paths for paths in hash_groups.values() if len(paths) > 1]
    if duplicates:
        lines.append("以下文件内容哈希完全相同；保留原文件，仅在后续代码中指定规范输入：")
        for paths in duplicates:
            lines.append(" - " + "；".join(f"`{path}`" for path in paths))
    else:
        lines.append("未发现内容哈希完全相同的文件组。")
    lines += ["", "## 重点文件摘要", ""]
    for record in records:
        scan = record["scan"]
        if not (scan["date_min"] or scan["categories"] or scan["nonempty"]):
            continue
        lines += [
            f"### `{record['relative']}`",
            "",
            f"- 行数：**{record['rows']:,}**；列数：**{len(record['header']):,}**；SHA-256：`{record['sha256']}`",
        ]
        if scan["date_min"]:
            lines += ["", "| 日期字段 | 最小日期 | 最大日期 | 无效日期数（扫描部分） |", "|---|---|---|---:|"]
            for field in scan["date_min"]:
                lines.append(
                    f"| `{field}` | {fmt_date(scan['date_min'][field])} | "
                    f"{fmt_date(scan['date_max'][field])} | {scan['date_invalid'][field]:,} |"
                )
        if scan["categories"]:
            lines += ["", "分类字段 Top-N："]
            for field, counts in scan["categories"].items():
                values = "; ".join(f"`{md(value)}` ({count:,})" for value, count in counts.most_common(20))
                lines.append(f"- `{field}`：{values or '无'}")
        lines += ["", "**字段清单**", "", ", ".join(f"`{md(x)}`" for x in record["header"]), ""]
    lines += [
        "## 指南第一部分逐项落实核对",
        "",
        "| 指南项目 | 当前本地证据 | 当前状态 | 对照结论与复刻影响 |",
        "|---|---|---|---|",
    ]
    for item, evidence, status, conclusion in guide_rows_for(raw_dir):
        lines.append(f"| {item} | {evidence} | **{status}** | {conclusion} |")
    lines += [
        "",
        "## 研究复现边界",
        "",
        "- 文件存在不等于研究输入已经完成；仍需逐字段确认口径、单位、许可证和点时可得性。",
        "- CRSP CIZ 普通股筛选采用 `SecurityType=EQTY`、`SecuritySubType=COM`、`ShareType=NS` 的近似映射，不直接声称等于旧版 `shrcd=10/11`。",
        "- 官方 JKMP 全量复现仍受官方数据文件、R/Rscript、因子面板和集群运行环境限制。",
        "- 课表按用户说明记录为已发送，具体证据和日期留待补充。",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[1]
    parser.add_argument("--raw-dir", type=Path, default=root / "data" / "raw")
    parser.add_argument("--output", type=Path, default=root / "docs" / "raw_data_inventory_report.md")
    parser.add_argument("--scan-limit", type=int, default=100_000, help="selected-field scan rows per CSV; use 0 for full scan")
    parser.add_argument("--no-hash", action="store_true")
    args = parser.parse_args()
    raw_dir = args.raw_dir.resolve()
    output = args.output.resolve()
    if not raw_dir.is_dir():
        raise SystemExit(f"raw directory does not exist: {raw_dir}")
    scan_limit = None if args.scan_limit == 0 else args.scan_limit
    started = dt.datetime.now().astimezone()
    files = sorted(p for p in raw_dir.rglob("*") if p.is_file())
    csv_files = [p for p in files if p.suffix.lower() == ".csv"]
    pdf_files = [p for p in files if p.suffix.lower() == ".pdf"]
    records: list[dict[str, Any]] = []
    for index, path in enumerate(csv_files, 1):
        relative = path.relative_to(raw_dir).as_posix()
        print(f"[{index}/{len(csv_files)}] inventory {relative}", flush=True)
        header = read_header(path)
        if args.no_hash:
            digest = ""
            rows = count_physical_rows(path)
        else:
            digest, rows = hash_and_count_rows(path)
        records.append(
            {
                "relative": relative,
                "size": path.stat().st_size,
                "rows": rows,
                "header": header,
                "sha256": digest,
                "scan": scan_selected(path, header, scan_limit),
                "status": "完成",
            }
        )
    pdfs = []
    for index, path in enumerate(pdf_files, 1):
        relative = path.relative_to(raw_dir).as_posix()
        print(f"[PDF {index}/{len(pdf_files)}] inventory {relative}", flush=True)
        pdfs.append(
            {
                "relative": relative,
                "sha256": "" if args.no_hash else sha256_file(path),
                "meta": pdf_metadata(path),
            }
        )
    finished = dt.datetime.now().astimezone()
    build_report(raw_dir, output, records, pdfs, started, finished, scan_limit)
    print(f"Wrote report: {output}")
    print(f"CSV files: {len(csv_files)}; PDF files: {len(pdf_files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
