先说结论：20 G 的 CSV 不存在"双击就能流畅打开"的软件。能用的工具都不把整个文件读进内存，而是按需扫描。综合免费、本地、上手成本和统计能力，我最推荐的主力是 **DuckDB 自带的 Local UI**（浏览器里的 SQL notebook），配合一次性把 CSV 转成 Parquet。想像表格那样滚动翻看，再配一个 EmEditor（Windows）或 Modern CSV。要画图，就先让 DuckDB 把数据"算小"，再交给 Excel、Power BI 或 PyGWalker。

### 为什么它们都崩了

Excel 单个工作表最多只能容纳 1,048,576 行，记事本和 VS Code 则要把整个文件载入内存再渲染，20 G 必崩。能处理这种体量的工具分两类。一类给文件建索引，只读取屏幕上要显示的部分，比如 EmEditor 和 Modern CSV 的只读模式，适合"翻看"。另一类是列式分析引擎，流式扫描、只读用到的列，比如 DuckDB，适合"统计"。

### 主力方案：DuckDB Local UI

DuckDB 是 MIT 协议的开源列式数据库，嵌入式运行，不需要服务器。从 v1.2.1 起，命令行执行 `duckdb -ui` 就能打开一个本地的 notebook 界面。左侧是库表目录，中间写 SQL，界面能直观显示各列的分布、空值比例等统计，右侧的 Column Explorer 会按数据类型展示百分位、中位数等信息。

它有几个关键特性：
- 查询默认完全在本机执行，数据不离开电脑。
- 它是原生进程而非浏览器 Wasm，能用上本机全部 CPU 核心、内存和磁盘。
- 它支持超出内存的数据处理，会尽量把比内存大的任务跑完。有用户在 32 GB 内存的机器上处理一个 330 GB、约 12.7 亿行的 CSV，直接传文件名读取时内存占用保持恒定，并顺利跑完。

Windows 上安装和启动：

```powershell
winget install DuckDB.cli          # 装完重开一个终端
duckdb -ui D:\data\work.duckdb     # 用库文件启动，建的视图下次还在
```

启动前后注意三点：
- Windows 版需要先装 Microsoft Visual C++ Redistributable。
- 浏览器会打开 localhost:4213；启动它的终端窗口要一直开着，关掉 UI 就停止工作。
- UI 的前端页面默认从 ui.duckdb.org 拉取，所以启动时要能联网，数据本身不上传。

把下面这组 SQL 粘进 notebook，改一下路径和列名，就能覆盖你说的三件事：

```sql
-- ① 字段名 + 自动推断的类型（只采样一部分行，很快）
DESCRIBE SELECT * FROM 'D:/data/big.csv';

-- ② 看前 100 行
FROM 'D:/data/big.csv' LIMIT 100;

-- ③ 一次性转成 Parquet（最值得做的一步，只做一次）
COPY (FROM read_csv('D:/data/big.csv'))
  TO 'D:/data/big.parquet' (FORMAT parquet, COMPRESSION zstd);
CREATE VIEW t AS FROM 'D:/data/big.parquet';   -- 之后都查 t

-- ④ 随机抽样 / 条件抽查（中文或带空格的列名用双引号）
SELECT * FROM t USING SAMPLE 1000 ROWS;
SELECT * FROM t WHERE "城市" = '上海' LIMIT 50;

-- ⑤ 全表体检
SUMMARIZE t;

-- ⑥ 分组统计 + 直方图
SELECT "城市", count(*) AS n, avg(amount) AS avg_amount
FROM t GROUP BY ALL ORDER BY n DESC LIMIT 20;
FROM histogram(t, amount, bin_count := 20);

-- ⑦ 把算好的小结果导出成 xlsx 给 Excel 画图（避免 CSV 中文乱码）
COPY (SELECT "城市", count(*) AS n FROM t GROUP BY ALL)
  TO 'D:/data/city_count.xlsx' WITH (FORMAT xlsx, HEADER true);
```

`SUMMARIZE` 一条命令会对所有列算出 min、max、近似去重数、均值、标准差、四分位数、行数和空值占比；分位数是近似值。`histogram()` 表函数从 1.1.0 起提供，直接输出分箱、计数和字符条形图。在左侧目录里点开表，也能直接看到列级统计和取值分布。导出 xlsx 用的是 excel 扩展。

第③步最耗时，要完整扫一遍 20 G 文本。视硬盘和 CPU，一般是分钟级，机械硬盘会慢很多。但它只需做一次，之后查询只读 Parquet 里用到的列，会快得多。两个参照：Andrew Heiss 把 3.3 GB 的 CSV 导入 DuckDB 后，文件只占约 600 MB；MotherDuck 的演示里，一个约 10 GB、4270 万行的 Parquet，查询和全表聚合都在一秒内返回。

### 大 CSV 最常见的四个坑

**类型推断报错。** DuckDB 默认采样 20480 行来推断类型，文件后面冒出一个"异类"值就会报错。报错信息会建议把该列手动指定为 VARCHAR，或设 `sample_size=-1` 扫描更多数据再推断。

**脏行。** 可以加上 `store_rejects=true`，出错的行和原因会记进临时表 `reject_errors`。别盲目用 `ignore_errors=true`，曾有版本在该模式下悄悄丢掉了本来能正常解析的行。

**中文编码。** CSV 读取器原生只支持 UTF-8、UTF-16 和 Latin-1，其他编码需要 encodings 扩展或先转码。该扩展接受 Python 风格的编码名，可用名称能用 `duckdb_encodings()` 查。

**转换时内存不足。** 官方给的办法是先执行 `SET preserve_insertion_order = false;`，代价是允许系统打乱行顺序，对统计分析没有影响。

建议先加 `LIMIT 100` 试参数，没问题再跑完整转换。前三个坑的参数可以一起加进第③步：

```sql
INSTALL encodings; LOAD encodings;
COPY (FROM read_csv('D:/data/big.csv',
        encoding = 'gbk',                  -- 国内系统导出的常见编码
        types = {'身份证号': 'VARCHAR'},    -- 按需手动指定列类型
        store_rejects = true))             -- 记录解析失败的行
  TO 'D:/data/big.parquet' (FORMAT parquet, COMPRESSION zstd);
FROM reject_errors;                        -- 查看被跳过的脏行
```

### 可视化：先"算小"，再画图

20 G 的原始行没必要逐点画出来，屏幕像素都不够。实际做法是用第⑥、⑦步把数据聚合或抽样到几百到几十万行，再交给顺手的工具。DuckDB UI 的 Column Explorer 加上 `histogram()`，已经能满足"看每列分布"的大部分需求。据我查到的资料，它定位是结果概览，没有拖拽式制图。需要正式图表时，按习惯选下面几种。

**习惯 Excel 的**，把第⑦步导出的 xlsx 用数据透视图，或用免费的 Power BI Desktop 做就行。重度 Power BI 用户还可以直连 DuckDB：MotherDuck 有一个开源的 DuckDB Power Query 连接器，基于 ODBC 驱动，能连本地 DuckDB 文件，并支持 DirectQuery。不过要装 ODBC 驱动和 .mez 文件，并在 Power BI 安全设置里允许加载未验证的扩展，MotherDuck 文档也已把它标为 legacy，折腾程度偏高。

**不想写代码、点开就要统计的**，推荐 Positron（Posit 出的免费 IDE，界面和 VS Code 很像）。它的 Data Explorer 可以在文件面板里直接点开 CSV、Parquet、xlsx（底层用 DuckDB），提供表格视图、每列统计摘要面板和筛选栏，2026 年 7 月的版本起由原生 DuckDB 引擎支撑。我没找到它处理 20 G 原始 CSV 的性能说明，建议点开第③步转好的 Parquet。

**想要 Tableau 式拖拽的**，PyGWalker 是最接近的免费方案。设 `computation="kernel"` 就会在本地用 DuckDB 计算，代价是要在 Jupyter 里写三行：

```python
import duckdb, pygwalker as pyg
df = duckdb.sql("SELECT * FROM 'D:/data/big.parquet' USING SAMPLE 2000000 ROWS").df()
pyg.walk(df, computation="kernel")   # 在抽样的 200 万行上拖拽探索，精确数字以 SQL 为准
```

还有两个备选：
- **Rill Developer**：能即时生成列统计和分布，并在本地预览交互式仪表盘，官方建议 DuckDB 中的数据量控制在 50 GB 以内，但在 Windows 上要先装 WSL。
- **DuckDB 社区扩展 dash**：装好后执行 `PRAGMA dash;` 就能打开带交互图表和仪表盘的界面，9 月 5 日刚更新到 0.4.1，适合愿意尝鲜的人。

### 只想像表格一样翻看、筛选（不写 SQL）

**EmEditor（仅 Windows）是这一类里最强的。**
- 64 位版能打开最大 16 TB 的文件。
- 打开大文件、查找筛选、CSV 解析和排序都用了多线程和 SIMD 加速。
- CSV 模式支持按列筛选、类似 SQL 的 JOIN 和数据透视，透视可以做计数、求和、平均、最大、最小。
- 缺点是处理多 GB 文件需要付费版。

**Modern CSV 支持 Windows、Mac、Linux。** 它的只读模式不把文件载入内存，而是建索引后按需从磁盘读取，内存占用只有文件大小的零头；排序筛选仍可用，只是比编辑模式慢。它有免费版，部分高级功能需要购买授权。

**Tad** 是免费的 DuckDB 驱动透视表浏览器，但作者自称是业余项目。而且它内部用的是内存中的 DuckDB 实例，打开 20 G CSV 会很吃内存，更适合打开 Parquet。

完全不装软件、只想瞄一眼开头结尾，PowerShell 就够，它只读取指定行数：

```powershell
Get-Content D:\data\big.csv -TotalCount 20   # 前 20 行
Get-Content D:\data\big.csv -Tail 20         # 最后 20 行
```

### 按场景速查

| 需求 | 推荐 | 费用 |
|---|---|---|
| 看字段、抽样、全表统计、看分布 | DuckDB Local UI | 免费 |
| 像 Excel 一样滚动、筛选、透视 | EmEditor（Windows）/ Modern CSV | 付费（Modern CSV 有免费版） |
| 点开文件就有每列统计 | Positron 打开 Parquet | 免费 |
| 正式图表 | DuckDB 聚合后导出 → Excel / Power BI | 免费 |
| Tableau 式拖拽探索 | PyGWalker（DuckDB 计算） | 免费 |
| 自动仪表盘 | Rill Developer（Windows 需 WSL） | 本地免费 |

### 考察过但不建议当主力的

- **Excel 的 Power Query**：把数据加载到数据模型可以绕过行数上限，但仍重度依赖内存，数百万行级别就可能变慢、卡死甚至崩溃。
- **VisiData**：会把数据读进内存，入门教程也建议大文件只加载开头部分做预览。
- **Gigasheet 等云端工具**：能处理最大 100 GB 的文件，但 20 G 要先上传，速度和数据隐私都是代价。

如果方便把表头和几行样例（可以脱敏）贴过来，再说说最想看哪些统计，我可以按你的列名和编码把整套 SQL 写好。