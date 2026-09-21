# MPP_Rep：借券费用与因子研究复刻项目

本仓库是一个面向论文复刻、数据审计和机制验证的 Python 研究项目。项目围绕美国股票借券数据、CRSP 匹配、借券费描述性统计，以及 M0-M3 组合成本原型展开。

仓库公开保留可复现脚本、数据字典、目录说明、描述性统计图表和小型成品统计表；不包含受供应商许可限制的原始商业数据库文件。

## 项目定位

- 提供当前 `mainProj` 研究工作区的公开代码和文档版本。
- 处理 Markit/S&P Securities Finance 风格的借券数据、CRSP 日频和证券属性数据、证券匹配结果，以及 M0-M3 成本处理组合实验。
- 提供一套可复现的项目骨架：目录结构、`.gitkeep` 占位文件、报告、图表和脚本均已保留。用户在本地放入具有合法使用权限的原始数据后，可以按流程重新生成中间数据和分析结果。

## 非项目范围

- 本仓库不是官方 JKMP 完整复刻包。
- 本仓库不包含 CRSP、Compustat、Markit/S&P、Capital IQ、13F 或其他供应商的授权原始数据。
- 本仓库不包含 `data/mid` 中的大型中间 Parquet 文件，也不包含 `data/prod` 中的大型面板 Parquet 文件。
- 本仓库不声称已经齐备完整的官方异象/因子信号面板、DGTW/因子收益、R/HPC 环境或论文所需的全部输入。

## 数据公开策略

**Tips:**

- 不要直接传超过100MB的大型数据文件！！！会把仓库撑爆，后续恢复较麻烦。
  
- 尽量统一按照本仓库的文件结构组织及进行对应文件命名便于成员之间协作同步。

原始数据被有意排除在 Git 仓库之外：

- `data/raw/**` 全部忽略，仅保留 `.gitkeep` 占位文件。
- `data/mid/**` 全部忽略，仅保留 `.gitkeep` 占位文件，因为该目录包含由原始数据生成的中间 Parquet 分区。
- `data/prod/**/*.parquet` 全部忽略。
- `data/prod/*.csv` 和 `data/prod/*.json` 中规模较小的汇总结果予以保留，便于读者了解当前原型结果，同时避免发布供应商原始数据。

这样既保留了项目的目录结构，也避免意外公开受许可限制的数据或超过 GitHub 文件限制的大型文件。

## 仓库目录

```text
.
├── data/
│   ├── raw/       # 本地放置有权限使用的原始供应商数据；公开仓库仅保留 .gitkeep
│   ├── mid/       # 生成的中间分区数据；公开仓库仅保留 .gitkeep
│   └── prod/      # 跟踪小型 CSV/JSON 结果；大型 Parquet 文件被忽略
├── docs/          # 数据字典、库存报告、复现状态和目录结构说明
├── reports/
│   └── figures/   # 描述性统计图和原型分析图
└── scripts/       # 数据处理、分析和报告生成脚本
```

详细目录职责和文件放置规则见 [`docs/project_structure_report.md`](docs/project_structure_report.md)。

## 重要文档

- [`docs/raw_data_dictionary_and_reproduction_status.md`](docs/raw_data_dictionary_and_reproduction_status.md)
  原始数据字典、字段解释、复现状态矩阵，以及现有全部图表的来源和解读。

- [`docs/raw_data_inventory_report.md`](docs/raw_data_inventory_report.md)
  私有工作区原始文件库存报告，包括文件大小、行数、哈希和重复文件说明。

- [`docs/research_pipeline_readme.md`](docs/research_pipeline_readme.md)
  处理流程、主要输出、模型口径、图表包和当前限制。

- [`docs/project_structure_report.md`](docs/project_structure_report.md)
  推荐目录结构、规范输出、测试输出和文件放置规则。

## 主要脚本

| 脚本 | 作用 |
|---|---|
| `scripts/raw_data_inventory.py` | 递归盘点 `data/raw`，避免将超大 CSV 整体载入内存。 |
| `scripts/markit_coverage.py` | 处理借券数据，生成 Markit 覆盖率、月度费用表和 Markit 图表。 |
| `scripts/build_crsp_panel.py` | 构建 CRSP 月度普通股面板，并匹配 Markit 借券费信息。 |
| `scripts/run_m0_m3_prototype.py` | 运行 M0-M3 成本处理组合原型。 |
| `scripts/make_research_reports.py` | 生成研究汇总表和相关说明报告。 |
| `scripts/make_presentation_visuals.py` | 基于 `data/prod` 生成汇报型图表。 |
| `scripts/raw_data_dictionary_report.py` | 生成原始数据字典、复现状态和图表解读报告。 |
| `scripts/project_structure_report.py` | 生成项目目录结构报告。 |

## 建议运行环境

脚本使用普通 Python 运行。当前本地开发环境为 Python 3.12。

安装主要依赖：

```bash
pip install numpy pandas pyarrow matplotlib scipy
```

可选组件：

- 安装 `pdftotext` 后，可以更好地抽取本地 WRDS PDF 字段字典。
- 需要安装 Git 才能进行版本控制。
- 运行大数据处理流程时，需要为原始文件、临时文件和 Parquet 输出预留足够的磁盘空间和内存。

## 复现流程

克隆公开仓库后，将具有合法使用权限的原始数据放入预期的 `data/raw` 路径。公开仓库通过 `.gitkeep` 保留目录骨架，但不提供原始文件。

推荐的本地执行顺序如下：

```bash
python scripts/raw_data_inventory.py --raw-dir data/raw --output docs/raw_data_inventory_report.md
python scripts/markit_coverage.py --input "data/raw/American Equities.csv" --rebuild
python scripts/build_crsp_panel.py --rebuild
python scripts/run_m0_m3_prototype.py
python scripts/make_research_reports.py
python scripts/make_presentation_visuals.py
python scripts/raw_data_dictionary_report.py --no-hash
python scripts/project_structure_report.py
```

前四个计算步骤依赖未随仓库发布的原始数据。文档生成步骤也需要相应的本地中间数据或成品数据已经存在。

## 预期的本地原始数据

私有工作区使用过以下类别的源文件：

- Markit/S&P Securities Finance American Equities 借券数据。
- CRSP 日频股票文件和 Stock Header Information。
- CRSP 分配事件和退市文件。
- Compustat 季度基本面数据。
- CCM-like 公司与证券链接表。
- Compustat Supplemental Short Interest 空头兴趣数据。
- 13F 机构持仓文件。
- Capital IQ Key Developments 公司事件数据。

具体文件库存、字段解释和当前复现状态见 [`docs/raw_data_dictionary_and_reproduction_status.md`](docs/raw_data_dictionary_and_reproduction_status.md)。

## 仓库中保留的成品

公开仓库保留以下小型结果，用于帮助读者理解当前研究原型：

- `data/prod/*.csv` 和 `data/prod/*.json` 中的 Markit、CRSP 覆盖率和匹配汇总。
- 原型汇总、月度指标、敏感性分析和元数据文件。
- `reports/figures` 下的描述性统计图和汇报图。
- `docs` 下的数据字典、复现说明和目录结构文档。

本地的大型输出，例如 `markit_stock_monthly.parquet`、`crsp_monthly_panel.parquet` 和按年份生成的中间 Parquet 分区，均不会上传到公开仓库。

## 图表

仓库中包含 17 张 PNG 图表：

- `reports/figures/markit`：Markit 借券费描述性统计图。
- `reports/figures/presentation`：覆盖率、样本匹配、费用动态和原型结果汇报图。
- `reports/figures/prototype`：完整研究区间的 M0-M3 累计收益图。
- `reports/figures/prototype_test3`：历史短样本测试图，已在文档中标明不属于规范主结果。

每张图的来源数据、生成脚本、阅读方法、主要含义和解释边界，均记录在 [`docs/raw_data_dictionary_and_reproduction_status.md`](docs/raw_data_dictionary_and_reproduction_status.md) 的图表章节中。

## 当前研究范围

当前 Python 原型主要研究：

- 借券费的覆盖率和横截面分布。
- Markit-CRSP 匹配和样本构建。
- 借券费的持续性和横截面异质性。
- 简化的 M0-M3 机制比较：
  - M0：不考虑交易成本和借券费。
  - M1：将交易成本纳入处理。
  - M2：使用 M1 权重，事后扣除空头借券费。
  - M3：同时将交易成本和空头借券费纳入优化目标函数。

M0-M3 输出用于检查机制和代码链路，不应直接解释为官方论文的最终复刻结果。

## 当前限制

- 官方 JKMP 输入，例如 `usa.csv`、`usa_dsf.csv`、完整信号面板、因子收益文件及相关元数据，不包含在本仓库中。
- 官方 R/Rscript 和 HPC/SLURM 运行环境没有在本仓库中复现。
- 部分非 CRSP/Compustat 字段是根据字段名和项目用法解释的，最终仍需要供应商字段字典核验。
- 仓库中的小型派生汇总可以帮助理解当前原型，但完整重跑仍要求本地具备有权限使用的原始数据。

## 引用与数据访问

如果将本仓库用于研究，请按照数据供应商和原论文的许可及学术引用要求进行引用。本仓库不再分发供应商原始数据，也不授予任何数据访问权限。

## 许可证

目前尚未添加明确的开源许可证。在正式添加许可证之前，代码和文档虽然公开可见，但不应默认理解为已经授予不受限制的再发布、修改或商业使用权。
