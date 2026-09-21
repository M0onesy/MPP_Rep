#!/usr/bin/env python3
"""Generate a detailed raw-data dictionary and reproduction-status report.

The script is deliberately conservative with large source files: it reads CSV
headers only, reuses the existing inventory report for row counts and hashes,
and extracts field definitions from local WRDS PDF dictionaries when available.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import os
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_VERSION = "1.1.0"


@dataclass
class FieldDef:
    dtype: str
    meaning: str
    source: str
    use: str


@dataclass
class FileNote:
    title: str
    source: str
    how_obtained: str
    purpose: str
    current_use: str
    quality_note: str
    dictionary_pdf: str | None = None
    canonical_of: str | None = None


@dataclass(frozen=True)
class FigureSpec:
    rel_path: str
    category: str
    source: str
    generator: str
    status: str
    what: str
    reading: str
    interpretation: str
    caveat: str


def clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\ue000-\uf8ff]", "", text)
    for menu_label in (
        " Share Outstanding",
        " Stock Header Information",
        " Monthly Stock File",
        " Daily Stock File",
        " Delisting Information",
        " Distribution",
        " Names",
    ):
        text = text.replace(menu_label, "")
    return re.sub(r"\s+", " ", text.replace("\uf059", "").strip())


def md_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


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


def read_header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        return next(csv.reader(handle), [])


def read_inventory_metadata(path: Path) -> dict[str, dict[str, str]]:
    """Parse the file-level table from raw_data_inventory_report.md."""
    if not path.exists():
        return {}
    metadata: dict[str, dict[str, str]] = {}
    pattern = re.compile(
        r"^\| `(?P<rel>[^`]+)` \| (?P<kind>[^|]+) \| (?P<size>[^|]+) \| "
        r"(?P<rows>[^|]+) \| (?P<cols>[^|]+) \| `(?P<sha>[^`]+)` \| "
        r"(?P<dates>[^|]+) \| (?P<status>[^|]+) \|$"
    )
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line.strip())
        if match:
            row = {k: v.strip() for k, v in match.groupdict().items()}
            metadata[row["rel"]] = row
    return metadata


def pdftotext_executable() -> str | None:
    found = shutil.which("pdftotext")
    if found:
        return found
    candidate = Path(r"D:\Software\Program\tex\texlive\2026\bin\windows\pdftotext.exe")
    return str(candidate) if candidate.exists() else None


def extract_pdf_fields(pdf_path: Path) -> dict[str, FieldDef]:
    executable = pdftotext_executable()
    if not executable or not pdf_path.exists():
        return {}
    proc = subprocess.run(
        [executable, "-layout", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    text = unicodedata.normalize("NFKC", proc.stdout)
    fields: dict[str, FieldDef] = {}
    current: str | None = None
    var_re = re.compile(
        r"^\s*([A-Za-z][A-Za-z0-9_]*)\s+(?:[^\w]*\s*)?"
        r"(Int|Date|Char|Decimal)\s+(?:\(([^)]*)\)\s*)?(.*)$"
    )
    stop_tokens = (
        "Product:",
        "Library:",
        "File:",
        "Date Range:",
        "Last Updated",
        "Update Frequency",
        "Variable Reference",
        "Variable Name",
        "Top",
        "About WRDS",
        "Knowledge Base",
        "Manuals and Overviews",
    )
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            current = None
            continue
        match = var_re.match(line)
        if match:
            name, dtype, parenthetical, desc = match.groups()
            lower = name.lower()
            if lower in {"product", "library", "file", "date", "last", "update", "frequency", "variable"}:
                current = None
                continue
            desc = clean_text(desc)
            parenthetical = clean_text(parenthetical or lower)
            meaning = desc if desc else parenthetical
            meaning = meaning.replace("Sic Code Names", "Sic Code")
            fields[lower] = FieldDef(dtype=dtype, meaning=meaning, source=f"WRDS PDF: {pdf_path.name}", use="")
            current = lower
            continue
        stripped = clean_text(line)
        if current and stripped and not any(stripped.startswith(token) for token in stop_tokens):
            if len(stripped) <= 120 and not stripped.startswith(("Home /", "Search WRDS", "Unless otherwise")):
                fields[current].meaning = clean_text(fields[current].meaning + " " + stripped)
    if pdf_path.name == "CRSP_Distribution.pdf":
        distribution_meanings = {
            "primaryexch": "Primary Exchange",
            "nasdissuno": "Nasdaq Issue Number",
            "siccd": "Sic Code",
            "permno": "PERMNO",
            "disexdt": "Ex-Distribution Date",
            "disseqnbr": "Distribution Sequence Number",
            "disordinaryflg": "Distribution Ordinary Dividend Flag",
            "distype": "Distribution Type",
            "disfreqtype": "Distribution Frequency Type",
            "dispaymenttype": "Distribution Payment Method Type",
            "disdetailtype": "Distribution Detail Type",
            "distaxtype": "Distribution Tax Status Type",
            "disorigcurtype": "Distribution Original Currency Type",
            "disdivamt": "Dividend Amount",
            "disfacpr": "Factor To Adjust Price",
            "disfacshr": "Factor To Adjust Shares",
            "disdeclaredt": "Declaration Date",
            "disrecorddt": "Record Date",
            "dispaydt": "Payment Date",
            "dispermno": "PERMNO of the Security Received",
            "dispermco": "PERMCO of the Issuer Providing Payment",
            "disamountsourcetype": "Distribution Amount Source Type",
        }
        for key, meaning in distribution_meanings.items():
            if key in fields:
                fields[key].meaning = meaning
    if pdf_path.name == "crsp2525(daily).pdf":
        fields["dispaymenttype"] = FieldDef(
            dtype="Char",
            meaning="Distribution Payment Method Type",
            source=f"WRDS PDF: {pdf_path.name}",
            use="",
        )
    return fields


def infer_role(field: str) -> str:
    lower = field.lower()
    if lower in {"permno", "permco", "lpermno", "lpermco", "gvkey", "cusip", "cusip9", "hdrcusip", "hdrcusip9", "isin", "sedol", "dxlid", "cik", "mgrno", "companyid", "keydevid"}:
        return "标识符"
    if lower.endswith("dt") or "date" in lower or lower in {"datadate", "rdate", "fdate", "prdate", "yyyymmdd", "rdq"}:
        return "日期/时点"
    if "ret" in lower or "prc" in lower or "price" in lower or lower in {"vwretd", "vwretx", "ewretd", "ewretx", "sprtrn"}:
        return "价格/收益"
    if any(token in lower for token in ("fee", "rebate", "dcbs", "saf", "sar", "utilisation", "utilization")):
        return "借券成本/供需"
    if any(token in lower for token in ("share", "shr", "vol", "quantity", "qty", "value", "cap", "own")):
        return "数量/规模"
    if any(token in lower for token in ("sic", "naics", "gsector", "ggroup", "gind", "gsubind", "indcode", "exch")):
        return "分类"
    if lower in {"conm", "conml", "companyname", "instrumentname", "securitynm", "stkname", "mgrname", "headline"}:
        return "名称/文本"
    return "属性"


def default_use(field: str, file_rel: str) -> str:
    lower = field.lower()
    file_lower = file_rel.lower()
    if file_rel == "American Equities.csv" or file_rel == "output_head.csv":
        if lower in {
            "dxlid",
            "datadate",
            "isin",
            "sedol",
            "cusip",
            "marketarea",
            "indicativefee",
            "indicativerebate",
            "dcbs",
            "saf",
            "sar",
            "utilisation",
            "activeutilisation",
            "lendablevalue",
            "lendablequantity",
            "valueonloan",
            "quantityonloan",
            "shortloanvalue",
            "shortloanquantity",
        }:
            return "当前 Markit 处理脚本直接读取；用于 US Equity 过滤、CUSIP 匹配、费用/利用率覆盖和股票-月费用摘要。"
        return "保留为 Markit 原始字段；当前原型未直接使用，后续可用于借券供需、集中度或数据质量扩展。"
    if "日频" in file_rel or "属性" in file_rel:
        if lower in {"permno", "dlycaldt", "dlyprc", "dlycap", "dlyret", "dlyretx", "dlyvol", "cusip", "cusip9", "hdrcusip9", "primaryexch", "securitytype", "securitysubtype", "sharetype", "securitynm"}:
            return "当前 CRSP 面板构建脚本直接读取；用于普通股过滤、收益/价量信号、月度聚合和 Markit 匹配。"
        if lower.startswith("del") or lower in {"delret", "delistingdt"}:
            return "用于退市收益与退市事件处理/核验；当前原型记录其可用性但未完整复刻官方退市调整。"
        if lower.startswith("dis"):
            return "用于分红/拆股等分配事件核验；当前主 CRSP 日频文件已包含部分分配字段。"
        return "保留为 CRSP 原始字段；当前原型未直接使用或仅作审计背景。"
    if "股利分配" in file_rel:
        return "用于分红、拆股和其他分配事件的显式核验；当前主原型未单独读入。"
    if "退市" in file_rel:
        return "用于退市收益、退市日期和退市原因处理；当前主原型未完整整合退市收益。"
    if "comp_quarterly" in file_lower or "月频" in file_rel:
        if lower in {"gvkey", "datadate", "conm", "tic", "cusip", "cik", "indfmt", "datafmt", "popsrc", "consol", "fic", "exchg"}:
            return "用于识别 Compustat 公司、季度时点和基本筛选；当前未进入主 M0-M3 原型。"
        if lower in {"atq", "actq", "ltq", "seqq", "ceqq", "txditcq", "pstkq", "pstkrq", "niq", "saleq", "revtq", "prccq", "cshoq"}:
            return "可用于未来账面权益、规模、盈利和基本面信号构造；当前不是官方年度 funda 的替代品。"
        return "保留为 Compustat 季度原始字段；未来可用于信号或财务控制变量。"
    if "13f" in file_lower or "stockownership" in file_lower:
        return "用于机构持股、13F 持有人/证券/持仓和持股集中度审计；当前未进入主 M0-M3 原型。"
    if "short_interest" in file_lower:
        return "用于月度空头兴趣审计和 Table IX 类替代路径；当前未进入主 M0-M3 原型。"
    if file_rel == "link.csv":
        if lower in {"gvkey", "lpermno", "lpermco", "linkdt", "linkenddt", "linktype", "linkprim", "cusip"}:
            return "用于 Compustat-CRSP 时变链接；当前主原型主要依赖 CRSP-Markit CUSIP 匹配，后续 DGTW/基本面复刻需要。"
        return "链接表附带公司属性；当前多为审计背景。"
    if file_rel == "keydevelopment.csv":
        return "用于 Capital IQ Key Developments 公司事件研究的潜在扩展；当前主复现流程未使用。"
    return "保留为原始字段；当前流程未直接使用。"


def make_field_defs_for(header: list[str], file_rel: str, pdf_defs: dict[str, FieldDef], manual_defs: dict[str, FieldDef]) -> dict[str, FieldDef]:
    result: dict[str, FieldDef] = {}
    for field in header:
        key = field.lower()
        if key in pdf_defs:
            item = pdf_defs[key]
        elif key in manual_defs:
            item = manual_defs[key]
        else:
            item = FieldDef(
                dtype=infer_role(field),
                meaning="根据字段名和项目上下文推断；需供应商/WRDS 字典进一步核验。",
                source="字段名推断，待核验",
                use="",
            )
        dtype = item.dtype if item.dtype else infer_role(field)
        use = item.use if item.use else default_use(field, file_rel)
        result[field] = FieldDef(dtype=dtype, meaning=item.meaning, source=item.source, use=use)
    return result


def add_defs(target: dict[str, FieldDef], source: str, rows: dict[str, tuple[str, str, str]]) -> None:
    for name, (dtype, meaning, use) in rows.items():
        target[name.lower()] = FieldDef(dtype=dtype, meaning=meaning, source=source, use=use)


def build_manual_defs() -> dict[str, FieldDef]:
    defs: dict[str, FieldDef] = {}
    add_defs(
        defs,
        "Markit/S&P Securities Finance 字段名、项目脚本与现有研究说明；部分缩写需供应商字典最终核验",
        {
            "dxlid": ("标识符", "Markit DataExplorer/数据供应商内部证券标识。", ""),
            "datadate": ("日期/时点", "日频观测日期。", ""),
            "isin": ("标识符", "International Securities Identification Number。", ""),
            "sedol": ("标识符", "伦敦证券交易所维护的证券标识。", ""),
            "cusip": ("标识符", "Markit 导出的历史 CUSIP，项目中规范化为 CUSIP8/CUSIP9 后与 CRSP 匹配。", ""),
            "quick": ("标识符", "日本 QUICK 证券代码；美国股票主流程通常不用。", ""),
            "instrumentname": ("名称/文本", "证券或工具名称。", ""),
            "marketarea": ("分类", "Markit 市场区域/资产类别分组，例如 US Equity (S&P500)。", ""),
            "bbgid": ("标识符", "Bloomberg Global ID/FIGI 类标识；需供应商字段字典核验具体口径。", ""),
            "bb_ticker": ("标识符", "Bloomberg ticker。", ""),
            "valueonloan": ("借券供需", "在贷证券市值，通常表示借出/借入市场中已在贷部分的价值。", ""),
            "quantityonloan": ("借券供需", "在贷证券数量。", ""),
            "lendervalueonloan": ("借券供需", "出借方口径在贷市值；需供应商字典确认与 valueonloan 的差别。", ""),
            "lenderquantityonloan": ("借券供需", "出借方口径在贷数量；需供应商字典确认。", ""),
            "utilisation": ("借券供需", "借券利用率，一般表示在贷量相对可借供给的比例；当前数据单位需核验。", ""),
            "averagetenure": ("借券供需", "平均借券期限/存续天数；需供应商字典核验单位。", ""),
            "transactioncount": ("借券供需", "借券交易笔数或交易活动计数；需供应商字典核验口径。", ""),
            "activeutilisation": ("借券供需", "活跃供给口径的利用率；当前数据单位需核验。", ""),
            "activeutilisationbyquantity": ("借券供需", "按数量计算的活跃利用率。", ""),
            "utilisationbyquantity": ("借券供需", "按数量计算的利用率。", ""),
            "lenderconcentration": ("借券供需", "出借方集中度指标；需供应商字典核验计算方式。", ""),
            "lendermarketshare1": ("借券供需", "最大出借方或一级出借方市场份额；需供应商字典核验。", ""),
            "lendermarketshare2": ("借券供需", "前两名出借方或二级出借方市场份额；需供应商字典核验。", ""),
            "borrowerconcentration": ("借券供需", "借入方集中度指标；需供应商字典核验计算方式。", ""),
            "borrowermarketshare1": ("借券供需", "最大借入方或一级借入方市场份额；需供应商字典核验。", ""),
            "borrowermarketshare2": ("借券供需", "前两名借入方或二级借入方市场份额；需供应商字典核验。", ""),
            "shortloanquantity": ("借券供需", "短贷/卖空相关在贷数量；需供应商字典核验与 quantityonloan 的关系。", ""),
            "shortloanvalue": ("借券供需", "短贷/卖空相关在贷市值；需供应商字典核验。", ""),
            "lenderquantityonloanstability": ("数据质量/稳定性", "出借方在贷数量稳定性指标；需供应商字典核验。", ""),
            "lendervalueonloanstability": ("数据质量/稳定性", "出借方在贷市值稳定性指标；需供应商字典核验。", ""),
            "lendablevalue": ("借券供需", "可借证券市值，是衡量借券供给的重要字段。", ""),
            "lendablequantity": ("借券供需", "可借证券数量，是衡量借券供给的重要字段。", ""),
            "activelendablevalue": ("借券供需", "活跃可借证券市值；需供应商字典核验。", ""),
            "activelendablequantity": ("借券供需", "活跃可借证券数量；需供应商字典核验。", ""),
            "activeavailablevalue": ("借券供需", "活跃可用证券市值；需供应商字典核验。", ""),
            "activeavailablequantity": ("借券供需", "活跃可用证券数量；需供应商字典核验。", ""),
            "inventoryconcentration": ("借券供需", "可借库存集中度指标；需供应商字典核验计算方式。", ""),
            "inventorymarketshare1": ("借券供需", "最大库存提供方市场份额；需供应商字典核验。", ""),
            "inventorymarketshare2": ("借券供需", "前两名库存提供方市场份额；需供应商字典核验。", ""),
            "availablequantitystability": ("数据质量/稳定性", "可用数量稳定性指标；需供应商字典核验。", ""),
            "availablevaluestability": ("数据质量/稳定性", "可用市值稳定性指标；需供应商字典核验。", ""),
            "lendablequantitystability": ("数据质量/稳定性", "可借数量稳定性指标；需供应商字典核验。", ""),
            "lendablevaluestability": ("数据质量/稳定性", "可借市值稳定性指标；需供应商字典核验。", ""),
            "indicativefee": ("借券成本", "Markit 买方口径指示性年化借券费，是本文复现最核心的卖空成本字段。", ""),
            "indicativerebate": ("借券成本", "指示性 rebate/回扣率，和借券费相关；具体符号与单位需供应商字典核验。", ""),
            "dcbs": ("借券成本", "Daily Cost of Borrow Score，1 到 10 的借券成本分档/评分，数值越高通常表示越难借或越贵。", ""),
            "indicativefee1day": ("借券成本", "1 日窗口指示性借券费变化或短期费率字段；需供应商字典核验。", ""),
            "indicativefee7day": ("借券成本", "7 日窗口指示性借券费变化或短期费率字段；需供应商字典核验。", ""),
            "indicativerebate1day": ("借券成本", "1 日窗口指示性 rebate 字段；需供应商字典核验。", ""),
            "indicativerebate7day": ("借券成本", "7 日窗口指示性 rebate 字段；需供应商字典核验。", ""),
            "saf": ("借券成本", "Simple Average Fee，出借方/成交费率类辅助字段；单位和口径需供应商字典核验。", ""),
            "sar": ("借券成本", "Simple Average Rebate 或相关 rebate 类辅助字段；缩写需供应商字典核验。", ""),
            "dns": ("数据质量/稳定性", "Markit 供应商缩写字段；当前仅能根据名称保留，需供应商字典核验。", ""),
            "dips": ("数据质量/稳定性", "Markit 供应商缩写字段；当前仅能根据名称保留，需供应商字典核验。", ""),
            "dimv": ("数据质量/稳定性", "Markit 供应商缩写字段；当前仅能根据名称保留，需供应商字典核验。", ""),
            "dps": ("数据质量/稳定性", "Markit 供应商缩写字段；当前仅能根据名称保留，需供应商字典核验。", ""),
            "dss": ("数据质量/稳定性", "Markit 供应商缩写字段；当前仅能根据名称保留，需供应商字典核验。", ""),
        },
    )
    add_defs(
        defs,
        "WRDS/Thomson-Reuters 13F 字段惯例与字段名推断，需与 WRDS 13F 字典核验",
        {
            "mgrno": ("标识符", "13F 机构管理人编号。", ""),
            "rdate": ("日期/时点", "13F 报告期末日期。", ""),
            "fdate": ("日期/时点", "13F 申报/文件日期或 WRDS 文件日期。", ""),
            "mgrname": ("名称/文本", "机构管理人名称。", ""),
            "country": ("分类", "管理人国家/地区。", ""),
            "typecode": ("分类", "13F 管理人或申报类型代码。", ""),
            "permkey": ("标识符", "WRDS/Thomson 永久管理人键或映射键。", ""),
            "cusip": ("标识符", "13F 报告中的证券 CUSIP，通常需要规范化为 8 位后与 CRSP 历史 CUSIP 匹配。", ""),
            "prdate": ("日期/时点", "处理日期/产品记录日期。", ""),
            "ticker": ("标识符", "证券 ticker。", ""),
            "ticker2": ("标识符", "备用或历史 ticker。", ""),
            "stkname": ("名称/文本", "证券名称。", ""),
            "stkcd": ("分类", "股票/证券代码分类。", ""),
            "stkcdesc": ("分类", "股票/证券代码描述。", ""),
            "indcode": ("分类", "行业代码。", ""),
            "shares": ("数量/规模", "13F 报告持有股数。", ""),
            "sole": ("数量/规模", "sole voting authority 股数。", ""),
            "shared": ("数量/规模", "shared voting authority 股数。", ""),
            "no": ("数量/规模", "no voting authority 股数。", ""),
            "type": ("分类", "13F 持仓类型/记录类型代码。", ""),
            "change": ("数量/规模", "相对上一期的持仓变化。", ""),
            "shrout1": ("数量/规模", "证券流通股数/股份数版本 1；需 WRDS 字典核验单位。", ""),
            "shrout2": ("数量/规模", "证券流通股数/股份数版本 2；需 WRDS 字典核验单位。", ""),
            "prc": ("价格/收益", "证券价格。", ""),
            "exchcd": ("分类", "交易所代码。", ""),
            "shrout": ("数量/规模", "流通股数。", ""),
            "top5instown": ("机构持股", "前 5 大机构持股量或比例；需 WRDS 字典核验单位。", ""),
            "top10instown": ("机构持股", "前 10 大机构持股量或比例；需 WRDS 字典核验单位。", ""),
            "numinstblockowners": ("机构持股", "机构大宗持有人数量。", ""),
            "instblockown": ("机构持股", "机构大宗持股量或比例。", ""),
            "numinstowners": ("机构持股", "机构持有人数量。", ""),
            "maxinstown": ("机构持股", "单一最大机构持股量或比例。", ""),
            "instown": ("机构持股", "机构总持股量。", ""),
            "instown_hhi": ("机构持股", "机构持股集中度 HHI。", ""),
            "instown_perc": ("机构持股", "机构持股比例。", ""),
        },
    )
    add_defs(
        defs,
        "Compustat short interest 字段惯例与 CrossSection 下载脚本",
        {
            "gvkey": ("标识符", "Compustat Global Company Key。", ""),
            "conm": ("名称/文本", "Compustat 公司名称。", ""),
            "cik": ("标识符", "SEC Central Index Key。", ""),
            "tic": ("标识符", "Compustat ticker。", ""),
            "iid": ("标识符", "Compustat issue id。", ""),
            "shortint": ("空头兴趣", "报告的空头股数；CrossSection 脚本后续按百万股缩放。", ""),
            "shortintadj": ("空头兴趣", "拆股调整后的空头股数；CrossSection 脚本后续按百万股缩放。", ""),
            "splitadjdate": ("日期/时点", "拆股调整日期。", ""),
        },
    )
    add_defs(
        defs,
        "Capital IQ Key Developments 字段名推断，需 S&P/Capital IQ 字典核验",
        {
            "gvkey": ("标识符", "Capital IQ/Compustat Global Company Key。", ""),
            "ticker_startdate": ("日期/时点", "ticker 生效起始日期。", ""),
            "ticker_enddate": ("日期/时点", "ticker 生效结束日期。", ""),
            "announcedate": ("日期/时点", "事件公告日期。", ""),
            "companyid": ("标识符", "Capital IQ 公司 ID。", ""),
            "companyname": ("名称/文本", "公司名称。", ""),
            "objectroletype": ("分类", "公司在事件中的对象角色类型。", ""),
            "keydevid": ("标识符", "Capital IQ key development 事件 ID。", ""),
            "headline": ("名称/文本", "事件标题。", ""),
            "keydeveventtypeid": ("分类", "Key Development 事件类型 ID。", ""),
            "situation": ("名称/文本", "事件情境/状态描述。", ""),
            "eventtype": ("分类", "事件类型。", ""),
            "keydevtoobjectroletypeid": ("分类", "事件-对象角色类型 ID。", ""),
            "announcetime": ("日期/时点", "公告时间。", ""),
            "announcedatetimezone": ("日期/时点", "公告时间的时区。", ""),
            "announceddateutc": ("日期/时点", "UTC 公告日期时间。", ""),
            "enterdate": ("日期/时点", "记录进入数据库日期。", ""),
            "entertime": ("日期/时点", "记录进入数据库时间。", ""),
            "entereddateutc": ("日期/时点", "UTC 入库日期时间。", ""),
            "lastmodifieddate": ("日期/时点", "最后修改日期。", ""),
            "lastmodifieddateutc": ("日期/时点", "UTC 最后修改日期时间。", ""),
            "mostimportantdateutc": ("日期/时点", "供应商标记的最重要 UTC 日期。", ""),
            "speffectivedate": ("日期/时点", "S&P 生效日期。", ""),
            "sptodate": ("日期/时点", "S&P 截止日期。", ""),
            "sourcetypename": ("分类", "事件信息来源类型名称。", ""),
        },
    )
    add_defs(
        defs,
        "CCM/Compustat company 与 CRSP link 字段惯例",
        {
            "gvkey": ("标识符", "Compustat Global Company Key。", ""),
            "cusip": ("标识符", "Compustat/CCM 公司或证券 CUSIP。", ""),
            "linkprim": ("链接", "CRSP-Compustat 链接主记录标记。", ""),
            "liid": ("链接", "Compustat issue id。", ""),
            "linktype": ("链接", "CRSP-Compustat 链接类型代码。", ""),
            "lpermno": ("链接", "链接到的 CRSP PERMNO。", ""),
            "lpermco": ("链接", "链接到的 CRSP PERMCO。", ""),
            "linkdt": ("日期/时点", "链接生效起始日期。", ""),
            "linkenddt": ("日期/时点", "链接生效结束日期。", ""),
            "ein": ("标识符", "Employer Identification Number。", ""),
            "costat": ("分类", "Compustat 公司状态。", ""),
            "dlrsn": ("分类", "Compustat 删除原因。", ""),
            "priusa": ("分类", "美国 primary issue 标记。", ""),
            "prican": ("分类", "加拿大 primary issue 标记。", ""),
            "prirow": ("分类", "其他地区 primary issue 标记。", ""),
            "idbflag": ("分类", "International/Industrial database 标记。", ""),
            "fic": ("分类", "注册地 ISO 国家代码。", ""),
            "loc": ("分类", "总部所在地 ISO 国家代码。", ""),
            "incorp": ("分类", "公司注册地。", ""),
            "state": ("分类", "州/省。", ""),
            "county": ("分类", "县/地区代码。", ""),
            "city": ("名称/文本", "城市。", ""),
            "conml": ("名称/文本", "公司法定名称。", ""),
            "weburl": ("名称/文本", "公司网站。", ""),
            "phone": ("名称/文本", "电话。", ""),
            "fax": ("名称/文本", "传真。", ""),
            "add1": ("名称/文本", "地址第 1 行。", ""),
            "add2": ("名称/文本", "地址第 2 行。", ""),
            "add3": ("名称/文本", "地址第 3 行。", ""),
            "add4": ("名称/文本", "地址第 4 行。", ""),
            "addzip": ("名称/文本", "邮政编码。", ""),
            "busdesc": ("名称/文本", "业务描述。", ""),
            "ipodate": ("日期/时点", "IPO 日期。", ""),
            "dldte": ("日期/时点", "Compustat 删除日期。", ""),
            "stko": ("分类", "股票所有权/上市状态代码。", ""),
            "fyrc": ("分类", "当前财政年结束月份。", ""),
            "gsector": ("分类", "GICS sector。", ""),
            "ggroup": ("分类", "GICS group。", ""),
            "gind": ("分类", "GICS industry。", ""),
            "gsubind": ("分类", "GICS sub-industry。", ""),
            "spcindcd": ("分类", "S&P 行业部门代码。", ""),
            "spcseccd": ("分类", "S&P 经济部门代码。", ""),
            "consol": ("分类", "Compustat 合并口径。", ""),
            "datafmt": ("分类", "Compustat 数据格式。", ""),
            "indfmt": ("分类", "Compustat 行业格式。", ""),
            "datadate": ("日期/时点", "Compustat/Markit/CRSP 记录日期或财务数据日期；具体含义随文件而定。", ""),
        },
    )
    return defs


def manual_defs_for_file(file_rel: str, defs: dict[str, FieldDef]) -> dict[str, FieldDef]:
    """Keep same-named fields from borrowing a definition from another vendor."""
    rel = file_rel.lower()
    selected: dict[str, FieldDef]
    if rel in {"american equities.csv", "output_head.csv"}:
        source_prefix = "Markit/S&P Securities Finance"
    elif rel.startswith("13f/") or rel == "stockownershipsummary.csv":
        source_prefix = "WRDS/Thomson-Reuters 13F"
    elif "short_interest" in rel:
        source_prefix = "Compustat short interest"
    elif rel == "keydevelopment.csv":
        source_prefix = "Capital IQ Key Developments"
    elif rel == "link.csv":
        source_prefix = "CCM/Compustat company"
    elif "comp_quarterly" in rel:
        allowed = {"costat", "datafmt", "indfmt", "consol", "datadate"}
        selected = {key: item for key, item in defs.items() if key in allowed}
        selected["datadate"] = FieldDef(
            dtype="日期/时点",
            meaning="Compustat 财务数据对应的季度数据日期。",
            source="Compustat 字段名与本地 fundq PDF 语境",
            use="用于季度财务数据的 point-in-time 对齐。",
        )
        return selected
    else:
        return {}
    selected = {key: item for key, item in defs.items() if item.source.startswith(source_prefix)}
    if rel in {"american equities.csv", "output_head.csv"}:
        selected["datadate"] = FieldDef(
            dtype="日期/时点",
            meaning="Markit 借券市场日频观测日期。",
            source="Markit/S&P Securities Finance 字段名与项目脚本",
            use="用于 US Equity 过滤、覆盖率统计和股票-月费用聚合。",
        )
        selected["cusip"] = FieldDef(
            dtype="标识符",
            meaning="Markit 导出的历史 CUSIP，用于规范化后与 CRSP CUSIP 匹配。",
            source="Markit/S&P Securities Finance 字段名与项目脚本",
            use="用于 Markit-CRSP 证券匹配。",
        )
    elif rel.startswith("13f/") or rel == "stockownershipsummary.csv":
        selected["cusip"] = FieldDef(
            dtype="标识符",
            meaning="13F 报告中的证券 CUSIP，通常规范化为 8 位后与 CRSP 历史 CUSIP 匹配。",
            source="WRDS/Thomson-Reuters 13F 字段惯例",
            use="用于机构持仓与 CRSP 证券匹配。",
        )
    elif "short_interest" in rel:
        selected["gvkey"] = FieldDef(
            dtype="标识符",
            meaning="Compustat Global Company Key。",
            source="Compustat short interest 字段惯例",
            use="用于按公司和日期组织空头兴趣。",
        )
        selected["datadate"] = FieldDef(
            dtype="日期/时点",
            meaning="空头兴趣观测日期。",
            source="Compustat short interest 字段惯例",
            use="用于按月组织空头兴趣并与持仓数据对齐。",
        )
    elif rel == "keydevelopment.csv":
        selected["gvkey"] = FieldDef(
            dtype="标识符",
            meaning="关联公司的 Compustat Global Company Key（若该记录有映射）。",
            source="Capital IQ/Compustat 字段名推断，待供应商字典核验",
            use="用于将公司事件与 Compustat/CRSP 公司链接。",
        )
        selected["ticker"] = FieldDef(
            dtype="标识符",
            meaning="公司在事件记录对应期间的 ticker。",
            source="Capital IQ Key Developments 字段名推断，待供应商字典核验",
            use="用于事件记录的证券级定位和辅助匹配。",
        )
    return selected


def build_file_notes() -> dict[str, FileNote]:
    return {
        "American Equities.csv": FileNote(
            title="Markit/S&P Securities Finance American Equities 日频证券借贷数据",
            source="Markit/S&P Global Securities Finance Analytics，American Equities 导出。",
            how_obtained="本地已有原始 CSV；现有脚本按块读取，过滤 US Equity (Others/RUSSELL 2000/S&P500)。",
            purpose="度量股票层面的借券费、借券供需和可借库存，是卖空成本复现的核心输入。",
            current_use="`markit_coverage.py` 直接使用，生成 Markit 覆盖率、年度 Parquet 分区和股票-月费用摘要。",
            quality_note="IndicativeFee、SAF/SAR、Utilisation 等字段的单位仍需供应商字典最终核验；脚本仅按现有项目口径记录。",
        ),
        "output_head.csv": FileNote(
            title="American Equities.csv 的前若干行样例输出",
            source="由 `peek_row.py` 从 Markit 原始文件导出的调试样例，不是独立原始来源。",
            how_obtained="本地辅助脚本截取 `American Equities.csv` 表头和样例行。",
            purpose="方便快速查看 Markit 表头与样例值。",
            current_use="不进入研究管线；仅作为调试/查看文件。",
            quality_note="字段与 `American Equities.csv` 相同，但不能作为完整数据使用。",
            canonical_of="American Equities.csv",
        ),
        "compustat_supplemental_short_interest.csv.csv": FileNote(
            title="Compustat Supplemental Short Interest 月度/半月度空头兴趣数据",
            source="Compustat supplemental short interest 导出。",
            how_obtained="本地已有 CSV；字段与 CrossSection 下载脚本中的 `comp.sec_shortint` 口径一致。",
            purpose="为 Table IX 类空头兴趣替代路径提供空头股数输入。",
            current_use="当前 M0-M3 原型未使用；用于原始数据审计和未来扩展。",
            quality_note="需进一步核验 `shortint`/`shortintadj` 单位、频率和与 13F 分母的对齐规则。",
        ),
        "keydevelopment.csv": FileNote(
            title="Capital IQ Key Developments 公司事件数据",
            source="S&P Capital IQ Key Developments 导出。",
            how_obtained="本地已有 CSV；无本地 PDF 字典，字段含义按 Capital IQ 常见命名推断。",
            purpose="可用于公司事件、公告或新闻事件研究扩展。",
            current_use="当前复现流程未使用。",
            quality_note="文件极大；字段定义需 S&P/Capital IQ 官方字典核验。",
        ),
        "link.csv": FileNote(
            title="Compustat-CRSP link-like 公司证券链接表",
            source="CCM/Compustat company 与 CRSP 链接类导出。",
            how_obtained="本地已有 CSV。",
            purpose="在 Compustat `gvkey` 与 CRSP `PERMNO/PERMCO` 之间建立时变映射。",
            current_use="当前主原型主要走 Markit-CRSP CUSIP 匹配；DGTW、账面权益和基本面信号复刻需要该表。",
            quality_note="需要按 `LINKDT`/`LINKENDDT` 做 point-in-time 链接；不能把静态映射当作全历史真值。",
        ),
        "stockownershipsummary.csv": FileNote(
            title="13F 机构持股汇总表",
            source="WRDS/Thomson-Reuters 13F stock ownership summary 类导出。",
            how_obtained="本地已有 CSV；与 `13f/stockownershipsummary.csv`、`13f/stock_ownership_summary_csv.csv` 哈希相同。",
            purpose="提供证券层面的机构持股比例、机构数量和持股集中度。",
            current_use="当前主原型未使用；用于未来 Table IX 类机构持股分母和审计。",
            quality_note="重复文件保留但应指定一个规范输入；字段单位需 WRDS 13F 字典核验。",
        ),
        "13f/stockownershipsummary.csv": FileNote(
            title="13F 机构持股汇总表副本",
            source="同根目录 `stockownershipsummary.csv`。",
            how_obtained="本地已有 CSV。",
            purpose="同机构持股汇总。",
            current_use="不建议作为规范输入；与根目录文件完全重复。",
            quality_note="哈希重复文件。",
            canonical_of="stockownershipsummary.csv",
        ),
        "13f/stock_ownership_summary_csv.csv": FileNote(
            title="13F 机构持股汇总表副本",
            source="同根目录 `stockownershipsummary.csv`。",
            how_obtained="本地已有 CSV。",
            purpose="同机构持股汇总。",
            current_use="不建议作为规范输入；与根目录文件完全重复。",
            quality_note="哈希重复文件。",
            canonical_of="stockownershipsummary.csv",
        ),
        "13f/13ftype1.csv": FileNote(
            title="13F Type 1 管理人主表",
            source="WRDS/Thomson-Reuters 13F type1 类导出。",
            how_obtained="本地已有 CSV；与 `13f/type1.csv` 哈希相同。",
            purpose="提供机构管理人、报告期和管理人类型信息。",
            current_use="当前主原型未使用；未来可用于 13F 管理人维度聚合。",
            quality_note="与 `13f/type1.csv` 完全重复。",
            canonical_of="13f/type1.csv",
        ),
        "13f/type1.csv": FileNote(
            title="13F Type 1 管理人主表",
            source="WRDS/Thomson-Reuters 13F type1 类导出。",
            how_obtained="本地已有 CSV。",
            purpose="提供机构管理人、报告期和管理人类型信息。",
            current_use="当前主原型未使用；未来可用于 13F 管理人维度聚合。",
            quality_note="可作为 type1 规范输入。",
        ),
        "13f/type2.csv": FileNote(
            title="13F Type 2 证券主表",
            source="WRDS/Thomson-Reuters 13F type2 类导出。",
            how_obtained="本地已有 CSV。",
            purpose="提供 13F 可报告证券、CUSIP、ticker、价格、流通股数和行业/交易所信息。",
            current_use="当前主原型未使用；未来用于 13F 持仓与证券信息匹配。",
            quality_note="字段单位和 type2 具体版本需 WRDS 字典核验。",
        ),
        "13f/type3.csv": FileNote(
            title="13F Type 3 机构-证券持仓明细",
            source="WRDS/Thomson-Reuters 13F type3 类导出。",
            how_obtained="本地已有 CSV。",
            purpose="提供管理人-证券-报告期持股明细和投票权拆分。",
            current_use="当前主原型未使用；未来可聚合机构持股和计算机构分母。",
            quality_note="需要处理修正件、重复记录和报告期/申报期时点。",
        ),
        "13f/type4.csv": FileNote(
            title="13F Type 4 持仓变化表",
            source="WRDS/Thomson-Reuters 13F type4 类导出。",
            how_obtained="本地已有 CSV。",
            purpose="记录管理人-证券层面的持仓变化。",
            current_use="当前主原型未使用；未来可用于持仓变化或修正件审计。",
            quality_note="字段 `change` 的计算基准需 WRDS 字典核验。",
        ),
        "13f/s34.csv": FileNote(
            title="WRDS 13F s34 合并持仓表",
            source="WRDS/Thomson-Reuters 13F s34 类导出。",
            how_obtained="本地已有 CSV。",
            purpose="把管理人、证券和持仓字段合并在一张大表中，便于直接聚合机构持股。",
            current_use="当前主原型未使用；未来可用于 Table IX 类机构持股分母。",
            quality_note="文件非常大；使用时需流式/分块读取，并处理修正件和重复申报。",
        ),
        "属性/CRSP_Stock Header Information(new).csv": FileNote(
            title="CRSP CIZ Stock Header Information",
            source="WRDS CRSP Annual Update, Stock Version 2 (CIZ), StkSecurityInfoHdr。",
            how_obtained="CSV 与本地 PDF 字典成对保存。",
            purpose="提供 PERMNO 证券属性、历史 CUSIP、证券类型和有效日期。",
            current_use="`build_crsp_panel.py` 直接读取，用于 EQTY/COM/NS 普通股筛选和 CUSIP 映射。",
            quality_note="CIZ 普通股映射不直接等同旧版 shrcd=10/11，需要在论文中说明。",
            dictionary_pdf="属性/CRSP_Stock Header Information(new).pdf",
        ),
        "日频/crsp0025(daily).csv": FileNote(
            title="CRSP CIZ Daily Stock File 分片 1",
            source="WRDS CRSP Annual Update, Stock Version 2 (CIZ), Daily Stock File。",
            how_obtained="CSV 与本地 PDF 字典成对保存；该文件是日频分片之一。",
            purpose="提供日价格、收益、成交量、市值、分配字段和市场指数收益。",
            current_use="`build_crsp_panel.py` 直接读取并聚合为月度普通股面板。",
            quality_note="DlyCap 在当前脚本中按千美元转换为美元；需要与 WRDS 字典/导出设置保持一致。",
            dictionary_pdf="日频/crsp2525(daily).pdf",
        ),
        "日频/crsp2599(daily).csv": FileNote(
            title="CRSP CIZ Daily Stock File 分片 2",
            source="WRDS CRSP Annual Update, Stock Version 2 (CIZ), Daily Stock File。",
            how_obtained="CSV 与本地 PDF 字典成对保存；该文件是日频分片之一。",
            purpose="提供日价格、收益、成交量、市值、分配字段和市场指数收益。",
            current_use="`build_crsp_panel.py` 直接读取并聚合为月度普通股面板。",
            quality_note="与另一个日频分片字段相同，后续处理应合并两者且去重。",
            dictionary_pdf="日频/crsp2525(daily).pdf",
        ),
        "月频/Comp_Quarterly6126.csv": FileNote(
            title="Compustat Fundamentals Quarterly",
            source="WRDS Compustat - Capital IQ North America Fundamentals Quarterly, fundq。",
            how_obtained="CSV 与本地 PDF 字典成对保存。",
            purpose="提供季度财务报表和公司属性字段，可用于基本面信号和控制变量。",
            current_use="当前主原型未直接使用；不能替代论文所需的 Compustat annual/funda 与 Pension Annual。",
            quality_note="表名所在目录叫“月频”，但文件本身是 Compustat quarterly；不要误写成 CRSP 月频。",
            dictionary_pdf="月频/Comp_Quarterly6126.pdf",
        ),
        "股利分配/CRSP_Distribution.csv": FileNote(
            title="CRSP CIZ Distribution Information",
            source="WRDS CRSP Annual Update, Stock Version 2 (CIZ), stkdistributions。",
            how_obtained="CSV 与本地 PDF 字典成对保存。",
            purpose="提供分红、拆股和其他分配事件。",
            current_use="当前主原型未单独读入；CRSP 日频文件中已带部分分配字段，后续可用于显式事件核验。",
            quality_note="需要按 ex-date/record/pay date 区分事件时点。",
            dictionary_pdf="股利分配/CRSP_Distribution.pdf",
        ),
        "退市/crsp_Delisting.csv": FileNote(
            title="CRSP CIZ Delisting Information",
            source="WRDS CRSP Annual Update, Stock Version 2 (CIZ), stkdelists。",
            how_obtained="CSV 与本地 PDF 字典成对保存。",
            purpose="提供退市日期、退市收益、退市原因和退市后价格。",
            current_use="当前主原型未完整整合退市收益；官方级复现需要正确处理 DelRet。",
            quality_note="退市收益是论文复现关键缺口之一，不能用普通价格数据自动替代。",
            dictionary_pdf="退市/crsp_Delisting.pdf",
        ),
    }


def file_note_for(rel: str) -> FileNote:
    notes = build_file_notes()
    return notes.get(
        rel,
        FileNote(
            title=rel,
            source="本地 data/raw 文件。",
            how_obtained="本地已有文件；暂无更细来源说明。",
            purpose="保留为原始材料。",
            current_use="当前主流程未明确使用。",
            quality_note="需人工补充来源与口径。",
        ),
    )


def pdf_note_for(rel: str) -> FileNote:
    if "CRSP_Stock Header" in rel:
        title = "CRSP Stock Header Information 字段字典 PDF"
    elif "daily" in rel:
        title = "CRSP Daily Stock File 字段字典 PDF"
    elif "Comp_Quarterly" in rel:
        title = "Compustat Fundamentals Quarterly 字段字典 PDF"
    elif "Distribution" in rel:
        title = "CRSP Distribution 字段字典 PDF"
    elif "Delisting" in rel:
        title = "CRSP Delisting 字段字典 PDF"
    else:
        title = "字段字典 PDF"
    return FileNote(
        title=title,
        source="WRDS 查询页面导出的变量说明 PDF。",
        how_obtained="与对应 CSV 一起保存在 data/raw 中。",
        purpose="为对应 CSV 提供字段类型和字段定义。",
        current_use="由本报告生成脚本解析，用于字段释义。",
        quality_note="PDF 抽取可能丢失少量换行或页面菜单文本，关键字段已抽查。",
    )


def helper_note_for(rel: str) -> FileNote:
    if rel.endswith("peek_line.py"):
        return FileNote(
            title="Markit 行数统计辅助脚本",
            source="本地调试脚本，不是原始数据。",
            how_obtained="人工创建，用于统计 `American Equities.csv` 物理行数。",
            purpose="辅助核验超大 CSV 行数。",
            current_use="不属于研究输入；不应纳入数据复现口径。",
            quality_note="保存在 raw 目录下但类型是辅助脚本。",
        )
    return FileNote(
        title="Markit 表头/样例导出辅助脚本",
        source="本地调试脚本，不是原始数据。",
        how_obtained="人工创建，用于导出 `American Equities.csv` 前若干行到 `output_head.csv`。",
        purpose="辅助查看超大 CSV 表头和样例记录。",
        current_use="不属于研究输入；不应纳入数据复现口径。",
        quality_note="保存在 raw 目录下但类型是辅助脚本。",
    )


def metadata_for(rel: str, path: Path, cache: dict[str, dict[str, str]], no_hash: bool) -> dict[str, str]:
    cached = cache.get(rel, {})
    cached_sha = cached.get("sha", "")
    should_hash = bool(not cached_sha and (not no_hash or path.stat().st_size <= 10 * 1024 * 1024))
    rows = cached.get("rows", "—")
    cols = cached.get("cols", "—")
    if path.suffix.lower() == ".csv" and path.stat().st_size <= 10 * 1024 * 1024 and rows == "—":
        with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
            rows = str(max(sum(1 for _ in csv.reader(handle)) - 1, 0))
        if cols == "—":
            cols = str(len(read_header(path)))
    return {
        "size": cached.get("size", fmt_bytes(path.stat().st_size)),
        "rows": rows,
        "cols": cols,
        "sha": cached_sha or (sha256_file(path) if should_hash else ""),
        "dates": cached.get("dates", "—"),
    }


def reproduction_status_rows() -> list[tuple[str, str, str, str]]:
    return [
        ("Markit/S&P Securities Finance American Equities", "已取得", "`American Equities.csv`", "核心借券费原始文件存在；IndicativeFee 等字段仍需供应商口径最终核验。"),
        ("CRSP 日频股票文件", "已取得并用于 Python 原型", "`日频/crsp0025(daily).csv`, `日频/crsp2599(daily).csv`", "已构建 CRSP 月度普通股面板；CIZ 普通股筛选需说明其与旧版 share code 的差别。"),
        ("CRSP Stock Header", "已取得并用于 Python 原型", "`属性/CRSP_Stock Header Information(new).csv`", "用于历史 CUSIP 和证券属性映射。"),
        ("CRSP Distribution", "已取得", "`股利分配/CRSP_Distribution.csv`", "可用于分红/拆股事件核验；当前主原型未单独读入。"),
        ("CRSP Delisting", "已取得但未完整并入原型", "`退市/crsp_Delisting.csv`", "官方级复现需要把 DelRet 正确并入收益。"),
        ("Compustat Quarterly", "已取得", "`月频/Comp_Quarterly6126.csv`", "是季度 fundq，不是论文所需 annual funda 的完整替代。"),
        ("CCM/link-like 表", "基本具备", "`link.csv`", "可支持 gvkey-PERMNO 链接；使用时必须按有效日期。"),
        ("Compustat supplemental short interest", "已取得", "`compustat_supplemental_short_interest.csv.csv`", "可支持 Table IX 类扩展；字段单位与频率需核验。"),
        ("13F 机构持股", "已取得", "`13f/` 多个 type/s34/summary 文件", "可支持机构持股分母和集中度审计；需处理重复、修正件和 point-in-time。"),
        ("Capital IQ Key Developments", "已取得但当前未使用", "`keydevelopment.csv`", "可作为事件研究扩展，非当前论文复现必需输入。"),
        ("官方 JKMP 打包输入", "缺失", "`usa.csv`, `usa_dsf.csv`, `world_ret_monthly.csv` 等未发现", "因此不能声称官方 JKMP 全量复现完成。"),
        ("OSAP/Chen-Zimmermann 论文 exact vintage 信号面板", "缺失/未确认", "未在 `data/raw` 发现 `signed_predictors_dl_wide.zip`", "无法直接复刻 162 个异象完整组合。"),
        ("DGTW/因子收益成品", "缺失", "未发现成品 DGTW 或因子收益文件", "后续需自建或补齐。"),
        ("Compustat Annual 与 Pension Annual", "缺失", "仅发现 quarterly fundq", "严格账面权益/DGTW 构造仍不完整。"),
        ("R/Rscript 与 HPC/SLURM 官方环境", "缺失/未配置", "当前项目是 Python 原型", "不等同于官方复制包运行环境。"),
    ]


def figure_specs() -> list[FigureSpec]:
    return [
        FigureSpec(
            "markit/crsp_fee_by_size_group.png",
            "CRSP 横截面费用",
            "data/prod/crsp_fee_by_size_group.csv",
            "scripts/make_research_reports.py",
            "规范描述性图表",
            "按 CRSP 滞后市值五组展示借券费的中位数、90 分位和 99 分位。",
            "横轴从小市值组到大市值组，纵轴为年化 Indicative fee 百分比；重点比较不同分位数的斜率和尾部高度。",
            "小市值股票的费用中位数和高分位通常更高，说明借券成本的横截面差异可能与规模和可借性有关。",
            "这是 CRSP 合格股票样本的市值分组描述，不是控制其他特征后的因果估计，也不等于论文中的 alpha 检验。",
        ),
        FigureSpec(
            "markit/fee_log_histogram.png",
            "Markit 分布诊断",
            "data/mid/markit/ 与 data/prod/markit_fee_descriptive.csv",
            "scripts/markit_coverage.py",
            "规范描述性图表",
            "展示 Indicative fee 百分比的对数分布，观察主体区间和右尾。",
            "横轴是 fee percent 的 log10 变换，纵轴是股票-月份观察数；对数尺度下横向距离代表数量级差异。",
            "费用分布明显右偏，少量极高费用观察会拉高均值，因此中位数、分位数和尾部指标比均值更适合一起报告。",
            "绘图将下界限制为正值，并把上界裁到 99.9% 分位附近；图形用于看形状，不代表未裁剪的完整极端值分布。",
        ),
        FigureSpec(
            "markit/fee_rank_group_boxplot.png",
            "Markit 分组诊断",
            "data/mid/markit/ 与 data/prod/markit_fee_descriptive.csv",
            "scripts/markit_coverage.py",
            "规范诊断图",
            "按月内费用排名构造的五组箱线图，用于检查费用排序后的分布差异。",
            "箱体表示组内四分位区间，中线表示中位数；各组是每月内部排名组，不是市值组。",
            "该图检查费用排序和极端值是否稳定，帮助判断费用信号是否有明显横截面层次。",
            "不能把 Group 1 至 Group 5 解释为小盘到大盘；它不是因子收益或投资组合回测结果。",
        ),
        FigureSpec(
            "markit/fee_timeseries.png",
            "Markit 时间序列",
            "data/prod/markit_fee_timeseries.csv",
            "scripts/markit_coverage.py",
            "规范描述性图表",
            "展示费用中位数、均值、25-75 分位区间和 90 分位随月份的变化。",
            "先看中位数和四分位带的长期水平，再看均值和 90 分位是否在危机或高费用阶段明显抬升。",
            "费用不是固定常数，而是随时间和市场状态变化的持有成本；均值与高分位的分离体现右尾风险。",
            "事件线只是时间定位，不构成事件研究；2026 年若出现只代表部分年度的观察。",
        ),
        FigureSpec(
            "presentation/fig01_coverage_heatmap.png",
            "数据覆盖与匹配",
            "data/prod/markit_coverage.csv 与 data/prod/crsp_markit_matching_summary.csv",
            "scripts/make_presentation_visuals.py",
            "规范汇报图表",
            "按年份汇总 IndicativeFee、供需字段、CUSIP9 和 CRSP-Markit 匹配覆盖率。",
            "颜色越深表示覆盖或匹配比例越高；需要区分 Markit 字段覆盖和 CRSP 样本匹配，它们不是同一个分母。",
            "核心费用字段和匹配结果在主要研究区间内具备持续覆盖，支持继续做样本构建和机制原型。",
            "2026 年可能是部分年度；覆盖率高不等于字段单位、经济含义和匹配误差已经完全核验。",
        ),
        FigureSpec(
            "presentation/fig02_sample_timeline.png",
            "样本规模时间线",
            "data/prod/markit_stock_monthly.parquet 与 data/prod/crsp_monthly_panel.parquet",
            "scripts/make_presentation_visuals.py",
            "规范汇报图表",
            "比较 Markit 有费用股票、满足 4-of-21 条件的股票、CRSP 共同样本和原型目标宇宙的月度规模。",
            "观察各条线的长期水平、突变和彼此之间的筛选损耗；不要把股票数和股票-月份数混为一谈。",
            "主要研究期内共同样本规模足以支撑每月约 1,000 只股票的原型选择。",
            "不同曲线的定义和筛选条件不同，不能只根据曲线高度判断数据质量；2026 年为不完整样本期。",
        ),
        FigureSpec(
            "presentation/fig03_fee_timeseries_annotated.png",
            "费用动态",
            "data/prod/markit_fee_timeseries.csv",
            "scripts/make_presentation_visuals.py",
            "规范汇报图表",
            "将费用中位数、均值、90 分位、99 分位和四分位带放在同一时间轴，并标注重要市场阶段。",
            "中位数反映典型股票，90/99 分位反映尾部；均值高于中位数时说明右尾对总体均值有影响。",
            "高费用阶段主要体现在高分位和均值的抬升，说明借券成本具有状态依赖和尾部风险。",
            "时间共变不能单独证明费用导致收益或异象；事件标注用于描述背景，不是正式识别设计。",
        ),
        FigureSpec(
            "presentation/fig04_key_year_fee_distributions.png",
            "关键年份横截面",
            "data/prod/markit_stock_monthly.parquet",
            "scripts/make_presentation_visuals.py",
            "规范描述性图表",
            "比较 2006、2008、2020 和 2024 年的月度费用横截面分布。",
            "横轴为对数尺度；虚线分别标记中位数、90 分位和 99 分位，重点看分布整体移动还是只有尾部扩张。",
            "不同年份均存在右偏，2024 年高费用尾部更突出，说明尾部变化不能被单个平均值概括。",
            "每个面板是年度内股票-月份观察的合并分布，不是同一批股票的平衡面板，也不进行因果比较。",
        ),
        FigureSpec(
            "presentation/fig05_fee_by_size_group.png",
            "市值梯度",
            "data/prod/crsp_fee_by_size_group.csv",
            "scripts/make_presentation_visuals.py",
            "规范描述性图表",
            "展示五个 CRSP 市值组的中位数、90 分位和 99 分位，并加入外部文献口径参考线。",
            "使用对数纵轴比较不同数量级；先看组间梯度，再看小盘组的尾部是否远高于大盘组。",
            "借券费尾部风险集中在小市值端；大市值组更接近外部文献中较温和的费用情景。",
            "MPP 和 JKMP 参考线不一定与当前样本、字段定义和筛选口径完全一致，只能作背景比较，不能视为同口径检验。",
        ),
        FigureSpec(
            "presentation/fig06_variance_persistence.png",
            "方差分解与持续性",
            "data/prod/markit_fee_variance_decomposition.csv 与 data/prod/markit_fee_persistence.csv",
            "scripts/make_presentation_visuals.py",
            "规范描述性图表",
            "左侧展示股票固定效应、月份固定效应和双向分解，右侧展示费用自相关及高费用状态持续概率。",
            "左图看横截面和时间维度对费用变异的描述性贡献；右图看滞后月数增加后相关性和高费状态延续率如何下降。",
            "费用既有稳定的股票间差异，也有显著的时间持续性，不像纯粹的瞬时噪声。",
            "这是描述性分解，不是结构模型或因果识别；固定效应分解的数值依赖样本、缺失处理和当前实现方式。",
        ),
        FigureSpec(
            "presentation/fig07_crsp_markit_funnel.png",
            "样本筛选漏斗",
            "data/prod/crsp_monthly_panel.parquet",
            "scripts/make_presentation_visuals.py",
            "规范数据审计图",
            "展示 CRSP 月度面板、价格市值资格、费用匹配、fee_asof、4-of-21 条件和原型宇宙的逐层数量。",
            "从上到下阅读每一层筛选后的股票-月份观察数，关注费用匹配和 4-of-21 条件带来的损耗。",
            "样本筛选链路透明可追踪，当前研究样本不是凭空产生，而是从 CRSP 面板逐层筛选得到。",
            "各层指标仍受匹配口径、时间可得性和目标宇宙约束影响；漏斗本身不证明样本没有选择偏差。",
        ),
        FigureSpec(
            "presentation/fig08_m0_m3_dashboard.png",
            "M0-M3 原型结果",
            "data/prod/prototype_summary.csv",
            "scripts/make_presentation_visuals.py",
            "机制验证原型",
            "比较 M0 到 M3 的年化净收益、交易成本、空头借券费、多头出借收入、换手和空头权重。",
            "沿模型序列阅读成本项如何逐步加入；M0 是无成本基准，M1 加交易成本，M2 事后扣借券费，M3 将借券费纳入目标函数。",
            "当前原型中成本项会显著改变净收益和模型间差异，说明借券费值得作为内生持有成本研究。",
            "这些结果是 Python 机制原型，不是官方 JKMP 全量复现，也不能直接当作最终 alpha 或投资建议。",
        ),
        FigureSpec(
            "presentation/fig09_m2_m3_core_comparison.png",
            "M2-M3 机制比较",
            "data/prod/prototype_monthly_metrics.csv 与 data/prod/prototype_summary.csv",
            "scripts/make_presentation_visuals.py",
            "机制验证原型",
            "比较 M2 与 M3 的累计净收益路径、核心指标和 M3-M2 差值。",
            "第一面板看时间路径，第二面板看汇总指标，第三面板看把借券费内生化后相对于事后扣费的变化方向。",
            "M2 与 M3 的差异用于识别费用进入优化目标后是否改变权重和成本，而不是单纯事后会计调整。",
            "M2 使用 M1 权重事后扣费，M3 是简化的内生化原型；两者差异不能直接解释为因果收益提升。",
        ),
        FigureSpec(
            "presentation/fig10_sensitivity_panel.png",
            "M2-M3 敏感性",
            "data/prod/prototype_sensitivity.csv",
            "scripts/make_presentation_visuals.py",
            "机制验证原型",
            "展示交易成本、费用缩放、目标股票数、样本口径和多头出借收入开关变化下的 M2/M3 结果。",
            "逐个参数观察年化净收益变化，并比较 M2 与 M3 曲线或柱形之间的相对位置。",
            "交易成本和费用口径是当前原型净收益最敏感的参数，样本和出借收入开关的影响相对需要结合具体面板解读。",
            "这是单参数敏感性，不是联合参数不确定性分析，也没有统计置信区间；结果仍受简化优化和风险代理约束。",
        ),
        FigureSpec(
            "presentation/fig11_m0_m3_method_flow.png",
            "方法流程",
            "scripts/run_m0_m3_prototype.py 与 data/prod/prototype_metadata.json",
            "scripts/make_presentation_visuals.py",
            "方法说明图",
            "说明 CRSP 价量信号、Markit fee_asof、风险代理、权重约束和 M0-M3 成本处理之间的关系。",
            "按“输入 → 月度优化 → 模型分支 → 输出”阅读；重点区分 M2 的事后扣费与 M3 的目标函数内生化。",
            "该图帮助审计模型实现和解释实验设计，是机制链条的结构化说明。",
            "它不是实证结果图，也不能替代对数据、约束、求解状态和收益计算代码的审计。",
        ),
        FigureSpec(
            "prototype/m0_m3_cumulative_net_returns.png",
            "M0-M3 累计结果",
            "data/prod/prototype_monthly_metrics.csv",
            "scripts/run_m0_m3_prototype.py",
            "规范原型图表",
            "绘制 2007-01 至 2025-12 期间 M0-M3 月度净收益的累计路径。",
            "比较各模型路径的相对位置、拐点和成本加入后的长期差异；累计收益是净收益序列的连乘结果。",
            "该图直观展示成本处理如何改变原型组合的长期路径。",
            "累计路径对样本期、费用单位、交易成本和模型简化高度敏感，不是官方论文回测或稳健 alpha 证据。",
        ),
        FigureSpec(
            "prototype_test3/m0_m3_cumulative_net_returns.png",
            "M0-M3 测试结果",
            "data/prod/test_proto3/prototype_monthly_metrics.csv",
            "scripts/run_m0_m3_prototype.py",
            "历史/测试图表",
            "展示 test_proto3 短期测试运行中的 M0-M3 累计净收益路径。",
            "仅用于检查代码、求解器和图表生成是否正常，不用于比较长期模型表现。",
            "它可以作为可复现调试痕迹，帮助确认短样本运行链路没有中断。",
            "该版本只覆盖短期测试区间，不能与规范全样本图混用，也不进入主结论。",
        ),
    ]


def build_figure_section(project_root: Path, output: Path) -> list[str]:
    figures_dir = project_root / "reports" / "figures"
    actual_paths = {
        path.relative_to(figures_dir).as_posix()
        for path in figures_dir.rglob("*.png")
    } if figures_dir.exists() else set()
    specs = figure_specs()
    spec_paths = {spec.rel_path for spec in specs}
    lines = [
        "## 四、描述性统计与分析图表",
        "",
        "本节把 `reports/figures/` 中已有图表统一登记。图表只链接现有 PNG，不复制数据或图片；"
        "“规范”表示当前主流程生成的正式输出，“机制验证原型”表示用于检查借券费进入优化目标的 Python 原型，"
        "“历史/测试”不进入主结论。",
        "",
        f"- 图表目录：`{figures_dir}`",
        f"- 实际发现 PNG：{len(actual_paths)} 个",
        f"- 已登记图表：{len(specs)} 个",
        "",
        "| 图表 | 类别 | 来源数据 | 生成脚本 | 状态 |",
        "|---|---|---|---|---|",
    ]
    for spec in specs:
        exists = spec.rel_path in actual_paths
        status = f"{spec.status}；文件存在" if exists else f"{spec.status}；文件缺失"
        lines.append(
            f"| `{spec.rel_path}` | {md_escape(spec.category)} | `{spec.source}` | "
            f"`{spec.generator}` | **{md_escape(status)}** |"
        )

    unknown_paths = sorted(actual_paths - spec_paths)
    if unknown_paths:
        lines += [
            "",
            "以下 PNG 已在目录中发现，但尚未加入预定义图表字典，需补充解释后才能作为规范图表使用：",
            "",
        ]
        lines.extend(f"- `{path}`" for path in unknown_paths)

    for index, spec in enumerate(specs, start=1):
        path = figures_dir / spec.rel_path
        exists = path.exists()
        image_link = os.path.relpath(path, output.parent).replace("\\", "/")
        lines += [
            "",
            f"### 4.{index} `{spec.rel_path}`",
            "",
            f"![{spec.category}：{spec.rel_path}]({image_link})",
            "",
            f"- 文件状态：**{'存在' if exists else '缺失'}**",
            f"- 图表类别：{spec.category}",
            f"- 来源数据：`{spec.source}`",
            f"- 生成脚本：`{spec.generator}`",
            f"- 规范状态：{spec.status}",
            f"- 展示什么：{spec.what}",
            f"- 怎么读：{spec.reading}",
            f"- 主要解读：{spec.interpretation}",
            f"- 解释边界：{spec.caveat}",
        ]
    return lines


def build_report(
    raw_dir: Path,
    output: Path,
    inventory: Path,
    no_hash: bool,
    project_root: Path | None = None,
) -> None:
    project_root = project_root or raw_dir.parents[1]
    cache = read_inventory_metadata(inventory)
    manual_defs = build_manual_defs()
    csv_paths = sorted(raw_dir.rglob("*.csv"), key=lambda p: p.relative_to(raw_dir).as_posix().lower())
    pdf_paths = sorted(raw_dir.rglob("*.pdf"), key=lambda p: p.relative_to(raw_dir).as_posix().lower())
    py_paths = sorted(raw_dir.rglob("*.py"), key=lambda p: p.relative_to(raw_dir).as_posix().lower())

    pdf_field_cache: dict[str, dict[str, FieldDef]] = {}
    for path in pdf_paths:
        rel = path.relative_to(raw_dir).as_posix()
        pdf_field_cache[rel] = extract_pdf_fields(path)

    lines: list[str] = [
        "# data/raw 原始文件说明与复现状态",
        "",
        f"- 生成时间：{dt.datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- 扫描目录：`{raw_dir}`",
        f"- 生成脚本：`mainProj/scripts/raw_data_dictionary_report.py`，版本 `{SCRIPT_VERSION}`",
        "- 项目结构报告：`mainProj/docs/project_structure_report.md`",
        f"- 元数据来源：优先复用 `{inventory}` 中的行数、列数和 SHA-256；CSV 正文只读取表头。",
        "- 解释原则：WRDS/Compustat/CRSP 字段优先使用本地 PDF 字典；无本地字典的供应商字段明确标注为字段名/项目用法推断，需供应商字典核验。",
        "",
        "## 一、总览",
        "",
        f"- CSV 文件：{len(csv_paths)} 个",
        f"- PDF 字典：{len(pdf_paths)} 个",
        f"- raw 目录内辅助脚本：{len(py_paths)} 个",
        "- 重要提醒：文件存在不等于官方论文复现已经完成；当前项目已经跑通的是 Python 研究原型。",
        "",
        "| 文件 | 类型 | 大小 | 行数 | 列数 | SHA-256 | 说明 |",
        "|---|---|---:|---:|---:|---|---|",
    ]

    for path in csv_paths:
        rel = path.relative_to(raw_dir).as_posix()
        meta = metadata_for(rel, path, cache, no_hash=True)
        note = file_note_for(rel)
        lines.append(
            f"| `{md_escape(rel)}` | CSV | {meta['size']} | {meta['rows']} | {meta['cols']} | "
            f"`{meta['sha'] or '未计算'}` | {md_escape(note.title)} |"
        )
    for path in pdf_paths:
        rel = path.relative_to(raw_dir).as_posix()
        meta = metadata_for(rel, path, cache, no_hash=no_hash)
        note = pdf_note_for(rel)
        lines.append(f"| `{md_escape(rel)}` | PDF | {meta['size']} | — | — | `{meta['sha'] or '未计算'}` | {md_escape(note.title)} |")
    for path in py_paths:
        rel = path.relative_to(raw_dir).as_posix()
        note = helper_note_for(rel)
        digest = "未计算" if no_hash else sha256_file(path)
        lines.append(f"| `{md_escape(rel)}` | 辅助脚本 | {fmt_bytes(path.stat().st_size)} | — | — | `{digest}` | {md_escape(note.title)} |")

    lines += [
        "",
        "## 二、重复与规范输入",
        "",
        "- `13f/13ftype1.csv` 与 `13f/type1.csv` 内容哈希相同；建议后续以 `13f/type1.csv` 为规范输入。",
        "- `13f/stock_ownership_summary_csv.csv`、`13f/stockownershipsummary.csv` 与根目录 `stockownershipsummary.csv` 内容哈希相同；建议后续以根目录 `stockownershipsummary.csv` 为规范输入。",
        "- `output_head.csv` 是 `American Equities.csv` 的调试样例，不是独立原始数据源。",
        "- `peek_line.py` 与 `peek_row.py` 是辅助脚本，误放在 raw 目录下；本报告记录它们，但不把它们算作论文数据输入。",
        "",
        "## 三、复现完成情况矩阵",
        "",
        "| 数据需求 | 当前状态 | 本地证据 | 复现含义 |",
        "|---|---|---|---|",
    ]
    for requirement, status, evidence, implication in reproduction_status_rows():
        lines.append(f"| {md_escape(requirement)} | **{md_escape(status)}** | {evidence} | {md_escape(implication)} |")

    lines += build_figure_section(project_root, output)

    lines += [
        "",
        "## 五、逐文件说明与字段字典",
        "",
    ]

    for path in csv_paths:
        rel = path.relative_to(raw_dir).as_posix()
        header = read_header(path)
        note = file_note_for(rel)
        meta = metadata_for(rel, path, cache, no_hash=True)
        pdf_defs: dict[str, FieldDef] = {}
        if note.dictionary_pdf:
            pdf_defs = pdf_field_cache.get(note.dictionary_pdf, {})
        fields = make_field_defs_for(header, rel, pdf_defs, manual_defs_for_file(rel, manual_defs))
        lines += [
            f"### `{rel}`",
            "",
            f"- 内容：{note.title}",
            f"- 来源/怎么来的：{note.source} {note.how_obtained}",
            f"- 用来干什么：{note.purpose}",
            f"- 当前项目使用情况：{note.current_use}",
            f"- 质量与口径备注：{note.quality_note}",
        ]
        if note.canonical_of:
            lines.append(f"- 规范输入建议：这是 `{note.canonical_of}` 的重复或样例文件，除调试外不建议单独作为研究输入。")
        if note.dictionary_pdf:
            lines.append(f"- 字段定义来源：优先匹配 `{note.dictionary_pdf}`。")
        lines += [
            f"- 文件元数据：大小 {meta['size']}；行数 {meta['rows']}；列数 {len(header)}；SHA-256 `{meta['sha'] or '未计算'}`。",
            "",
            "| 字段 | 类型/角色 | 含义 | 定义来源 | 当前用途 |",
            "|---|---|---|---|---|",
        ]
        for field in header:
            item = fields[field]
            lines.append(
                f"| `{md_escape(field)}` | {md_escape(item.dtype or infer_role(field))} | "
                f"{md_escape(item.meaning)} | {md_escape(item.source)} | {md_escape(item.use)} |"
            )
        lines.append("")

    lines += ["## 六、PDF 字典与辅助脚本", ""]
    for path in pdf_paths:
        rel = path.relative_to(raw_dir).as_posix()
        note = pdf_note_for(rel)
        parsed = len(pdf_field_cache.get(rel, {}))
        meta = metadata_for(rel, path, cache, no_hash=no_hash)
        lines += [
            f"### `{rel}`",
            "",
            f"- 内容：{note.title}",
            f"- 来源/怎么来的：{note.source} {note.how_obtained}",
            f"- 用来干什么：{note.purpose}",
            f"- 当前使用情况：{note.current_use}",
            f"- 抽取到的字段定义数：{parsed}",
            f"- 文件元数据：大小 {meta['size']}；SHA-256 `{meta['sha'] or '未计算'}`。",
            "",
        ]
    for path in py_paths:
        rel = path.relative_to(raw_dir).as_posix()
        note = helper_note_for(rel)
        digest = "未计算" if no_hash else sha256_file(path)
        lines += [
            f"### `{rel}`",
            "",
            f"- 内容：{note.title}",
            f"- 来源/怎么来的：{note.source} {note.how_obtained}",
            f"- 用来干什么：{note.purpose}",
            f"- 当前使用情况：{note.current_use}",
            f"- 质量备注：{note.quality_note}",
            f"- 文件元数据：大小 {fmt_bytes(path.stat().st_size)}；SHA-256 `{digest}`。",
            "",
        ]

    lines += [
        "## 七、边界结论",
        "",
        "- 当前 raw 目录已经保存了多个关键商业数据库导出的原始文件，足以支撑当前 Python 原型的数据审计、Markit 费用处理、CRSP 月度面板构建和 Markit-CRSP 匹配。",
        "- 当前项目尚未齐备官方论文/JKMP 风格完整复制所需的成品输入、信号面板、DGTW/因子收益、年度 Compustat/Pension Annual 和官方 R/HPC 运行环境。",
        "- 后续写论文或汇报时，应把“原始文件已取得”“Python 原型已跑通”“官方全量复现完成”三个说法分开，避免把数据盘点误表述为完整复现。",
        "",
    ]

    output.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines)
    if "\ufffd" in content:
        raise ValueError("generated report contains Unicode replacement characters")
    output.write_text(content, encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=root / "data" / "raw")
    parser.add_argument("--output", type=Path, default=root / "docs" / "raw_data_dictionary_and_reproduction_status.md")
    parser.add_argument("--inventory", type=Path, default=root / "docs" / "raw_data_inventory_report.md")
    parser.add_argument("--no-hash", action="store_true", help="do not compute hashes for PDFs/helper scripts missing from the cached inventory")
    args = parser.parse_args()
    raw_dir = args.raw_dir.resolve()
    if not raw_dir.is_dir():
        raise SystemExit(f"raw directory does not exist: {raw_dir}")
    build_report(
        raw_dir,
        args.output.resolve(),
        args.inventory.resolve(),
        args.no_hash,
        project_root=root,
    )
    print(f"wrote {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
