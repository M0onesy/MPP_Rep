#!/usr/bin/env python3
"""Generate a concise, reproducible project-structure report.

The report is metadata-only: it walks directory entries and file sizes but
never loads the contents of source CSV or Parquet files.
"""

from __future__ import annotations

import argparse
import datetime as dt
from collections import Counter
from pathlib import Path


SCRIPT_VERSION = "1.0.0"


def fmt_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def file_stats(directory: Path) -> tuple[int, int, Counter[str]]:
    count = 0
    total_size = 0
    extensions: Counter[str] = Counter()
    if not directory.exists():
        return count, total_size, extensions
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        count += 1
        total_size += path.stat().st_size
        suffix = path.suffix.lower() or "[no extension]"
        extensions[suffix] += 1
    return count, total_size, extensions


def immediate_children(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))


def tree_lines(root: Path, max_depth: int = 3) -> list[str]:
    lines: list[str] = [f"`{root.name}/`"]

    def walk(directory: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        children = immediate_children(directory)
        for index, child in enumerate(children):
            is_last = index == len(children) - 1
            branch = "└── " if is_last else "├── "
            suffix = "/" if child.is_dir() else ""
            lines.append(f"{prefix}{branch}{child.name}{suffix}")
            if child.is_dir():
                walk(child, prefix + ("    " if is_last else "│   "), depth + 1)

    walk(root, "", 1)
    return lines


def section_summary(root: Path, relative_dir: str) -> tuple[int, int, str]:
    directory = root / relative_dir
    count, total_size, extensions = file_stats(directory)
    extension_text = ", ".join(
        f"{extension}: {number}" for extension, number in sorted(extensions.items())
    ) or "空目录"
    return count, total_size, extension_text


def build_report(root: Path, output: Path) -> None:
    root = root.resolve()
    lines: list[str] = [
        "# mainProj 项目目录结构与使用规范",
        "",
        f"- 生成时间：{dt.datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"- 项目根目录：`{root}`",
        f"- 生成脚本：`scripts/project_structure_report.py`，版本 `{SCRIPT_VERSION}`",
        "- 扫描方式：只读取目录项、文件扩展名和文件大小，不加载原始 CSV、Parquet 或 PDF 正文。",
        "",
        "## 一、总体判断",
        "",
        "当前项目采用“原始数据 → 中间数据 → 成品数据 → 报告”的四段式结构，已经足够支撑当前 Python 研究原型。"
        "本报告不新增复杂的软件包层级，也不搬动超大原始文件；测试文件和辅助文件通过规范状态进行区分。",
        "",
        "推荐把以下目录视为日常使用的规范入口：",
        "",
        "- `data/raw/`：供应商原始导出和字段字典，只读保存。",
        "- `data/mid/`：由脚本生成的分区中间数据，不手工修改。",
        "- `data/prod/`：研究分析直接使用的成品表、面板和原型结果。",
        "- `scripts/`：按流程运行的数据处理、分析和报告生成脚本。",
        "- `docs/`：数据字典、复现状态、目录说明和运行说明。",
        "- `reports/figures/`：由成品数据生成的图表，不作为原始数据输入。",
        "",
        "## 二、推荐结构",
        "",
        "```text",
        "mainProj/",
        "├── data/",
        "│   ├── raw/       供应商原始文件、PDF 字典和少量历史辅助文件",
        "│   ├── mid/       Markit/CRSP 分区 Parquet 等中间数据",
        "│   └── prod/      覆盖率、匹配、费用统计、面板和原型结果",
        "├── scripts/       可复现处理脚本",
        "├── docs/          数据字典、复现状态和项目结构说明",
        "└── reports/",
        "    └── figures/  markit、presentation、prototype 图表",
        "```",
        "",
        "## 三、当前目录扫描摘要",
        "",
        "| 目录 | 文件数量 | 总大小 | 扩展名分布 | 当前角色 |",
        "|---|---:|---:|---|---|",
    ]

    for directory, role in (
        ("data/raw", "原始供应商文件与字段字典"),
        ("data/mid", "脚本生成的中间数据"),
        ("data/prod", "分析成品与原型输出"),
        ("scripts", "处理与报告生成脚本"),
        ("docs", "说明文档"),
        ("reports/figures", "生成图表"),
    ):
        count, total_size, extensions = section_summary(root, directory)
        lines.append(
            f"| `{directory}/` | {count} | {fmt_bytes(total_size)} | {extensions} | {role} |"
        )

    lines += [
        "",
        "## 四、数据流与运行顺序",
        "",
        "| 顺序 | 脚本/阶段 | 主要输入 | 主要输出 | 状态说明 |",
        "|---:|---|---|---|---|",
        "| 1 | `raw_data_inventory.py` | `data/raw/` | `docs/raw_data_inventory_report.md` | 原始文件盘点，不整体载入大文件 |",
        "| 2 | `markit_coverage.py` | `data/raw/American Equities.csv` | `data/mid/markit/`、Markit 成品表和图 | 已跑通的 Markit 分块处理 |",
        "| 3 | `build_crsp_panel.py` | CRSP 日频、属性、Markit 中间数据 | `data/mid/crsp/`、`data/prod/crsp_monthly_panel.parquet` | 已跑通的 CRSP 月度面板 |",
        "| 4 | `run_m0_m3_prototype.py` | CRSP-Markit 面板 | `data/prod/prototype_*`、`reports/figures/prototype/` | Python 机制原型，不是官方 JKMP 全量复现 |",
        "| 5 | `make_research_reports.py` | `data/prod/` | 费用统计、流程说明和研究报告 | 生成成品描述统计 |",
        "| 6 | `make_presentation_visuals.py` | `data/prod/` | `reports/figures/presentation/` | 生成汇报型可视化，不重跑主流程 |",
        "| 7 | `raw_data_dictionary_report.py` | `data/raw/`、库存报告、图表目录 | `docs/raw_data_dictionary_and_reproduction_status.md` | 生成总数据字典、复现状态和图表解读 |",
        "| 8 | `project_structure_report.py` | 项目目录元数据 | `docs/project_structure_report.md` | 生成目录规范报告 |",
    ]

    lines += [
        "",
        "## 五、规范输出与非规范文件",
        "",
        "| 路径或文件组 | 状态 | 处理原则 |",
        "|---|---|---|",
        "| `data/raw/` 中的供应商 CSV/PDF | 规范原始输入 | 只读保存，不在原文件上做清洗覆盖 |",
        "| `data/raw/output_head.csv` | 样例/调试文件 | 仅用于查看 Markit 表头和样例行，不作为独立数据源 |",
        "| `data/raw/peek_line.py`、`peek_row.py` | 辅助脚本 | 记录在数据报告中，但不计入论文数据输入 |",
        "| `scripts/__pycache__/` | Python 运行缓存 | 可自动重建，不属于研究脚本、研究输入或研究输出 |",
        "| `data/mid/markit/`、`data/mid/crsp/` | 规范中间输出 | 由对应脚本重建，不手工修改 |",
        "| `data/prod/` 根目录成品表和 Parquet | 规范分析输出 | 供报告、图表和原型读取 |",
        "| `data/prod/test_proto*` | 测试输出 | 不进入主结果；保留用于调试和回归检查 |",
        "| `reports/figures/markit/` | 规范描述性图表 | 费用分布、时间序列和市值分组图 |",
        "| `reports/figures/presentation/` | 规范汇报图表 | 覆盖率、匹配、费用动态和原型分析图 |",
        "| `reports/figures/prototype/` | 规范原型图表 | 全样本 M0-M3 累计结果图 |",
        "| `reports/figures/prototype_test*` | 历史/测试图表 | 在总报告中说明，但不用于主结论 |",
        "",
        "重复原始文件暂不删除。`13f/13ftype1.csv` 与 `13f/type1.csv`，以及多个 `stockownershipsummary.csv` 文件应继续以原始库存报告中记录的哈希和规范输入建议为准。",
        "",
        "## 六、未来文件放置规则",
        "",
        "- 新下载的供应商原始文件放入 `data/raw/`，不要直接放入 `data/prod/`。",
        "- 新的分块、清洗或连接结果放入 `data/mid/<source>/`。",
        "- 可供分析脚本直接读取的稳定结果放入 `data/prod/`。",
        "- 新脚本放入 `scripts/`；一次性诊断脚本也应放在这里，不放入 `data/raw/`。",
        "- 新图表放入 `reports/figures/<topic>/`，并在总数据报告的图表字典中登记。",
        "- 数据定义、复现状态和运行方法放入 `docs/`，不要把说明散落在数据目录中。",
        "",
        "## 七、目录树快照",
        "",
    ]
    lines.extend(["```text", *tree_lines(root, max_depth=3), "```", ""])

    lines += [
        "## 八、使用边界",
        "",
        "- 当前目录结构适合继续推进 Python 原型和数据审计，但不能仅凭目录齐全宣称官方 JKMP 完整复现。",
        "- `data/prod/` 中的原型结果和 `reports/figures/prototype/` 中的图表应在论文或汇报中明确标注为机制验证结果。",
        "- 目录报告只描述位置和职责；字段含义、数据来源、重复文件和复现缺口以 `docs/raw_data_dictionary_and_reproduction_status.md` 为准。",
        "",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=root)
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "docs" / "project_structure_report.md",
    )
    args = parser.parse_args()
    project_root = args.root.resolve()
    if not project_root.is_dir():
        raise SystemExit(f"project root does not exist: {project_root}")
    build_report(project_root, args.output.resolve())
    print(f"wrote {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
