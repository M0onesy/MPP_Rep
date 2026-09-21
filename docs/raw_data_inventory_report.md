# Raw 数据盘点与指南落实核对报告

- 扫描目录：`D:\Competition\ZY_Project\选题五\mainProj\data\raw`
- 扫描时间：2026-09-17T11:00:35+08:00 至 2026-09-17T11:04:16+08:00
- 脚本版本：`2.0.0`
- CSV 行数：物理换行计数；选定字段扫描上限：`1000`
- 处理方式：递归发现文件；CSV 不整体载入内存；文件哈希使用 SHA-256。
- 注意：文件总览中的日期范围只来自选定字段的 scan-limit 抽样，不代表超大 CSV 的全量覆盖期；Markit 完整覆盖请以专门处理输出为准。

## 文件总览

| 相对路径 | 类型 | 大小 | 行数 | 列数 | SHA-256 | 选定字段日期范围（scan-limit 内） | 状态 |
|---|---|---:|---:|---:|---|---|---|
| `13f/13ftype1.csv` | CSV | 38.14 MiB | 512,040 | 8 | `c092d7a256bd9813ce96d8d0bce65015d7e1f33e296dfeb923d980ac03176ba3` | - | 完成 |
| `13f/s34.csv` | CSV | 18.35 GiB | 127,142,721 | 22 | `88070eb7af9f264f0533d2719b0410a57531466439b356408c773cebbfc4ddc6` | - | 完成 |
| `13f/stock_ownership_summary_csv.csv` | CSV | 210.43 MiB | 1,813,910 | 18 | `f4de655051d1ad0ab32fd301549b941e9b228af2b1977721c5c6167797fdd005` | - | 完成 |
| `13f/stockownershipsummary.csv` | CSV | 210.43 MiB | 1,813,910 | 18 | `f4de655051d1ad0ab32fd301549b941e9b228af2b1977721c5c6167797fdd005` | - | 完成 |
| `13f/type1.csv` | CSV | 38.14 MiB | 512,040 | 8 | `c092d7a256bd9813ce96d8d0bce65015d7e1f33e296dfeb923d980ac03176ba3` | - | 完成 |
| `13f/type2.csv` | CSV | 133.23 MiB | 1,977,948 | 12 | `2702bd9a299864160febfd08a89c7177478fa9aa00398da9149f6fb97cab187c` | - | 完成 |
| `13f/type3.csv` | CSV | 5.10 GiB | 127,140,268 | 8 | `d20cb39fc790c0cc77979128c313ee9cdb4efb82b64ee3a3647f340354893df5` | - | 完成 |
| `13f/type4.csv` | CSV | 3.36 GiB | 107,264,129 | 5 | `b9ba9b31d42f9597047987b8477bee4bb90359c62ed187a1769f3e461e0a9fc6` | - | 完成 |
| `American Equities.csv` | CSV | 21.78 GiB | 64,161,557 | 57 | `9127d1833efa49490443ba753696c87997392e8306f8ded2bccd217b7f3de704` | datadate: 2002-05-22 ~ 2002-05-22 | 完成 |
| `compustat_supplemental_short_interest.csv.csv` | CSV | 411.98 MiB | 5,298,058 | 9 | `5aabd70be5e172ca02b43a26acb0cc96fd826e571a94a5bc5086e75657899c23` | datadate: 2006-07-14 ~ 2026-08-31 | 完成 |
| `keydevelopment.csv` | CSV | 44.01 GiB | 47,767,574 | 26 | `e8f21aec8be8652baa919be210e764cdc8acba292d7e097080a378bb4f7d5e4a` | - | 完成 |
| `link.csv` | CSV | 48.83 MiB | 110,053 | 47 | `fcec8fc3cb86e587fe89e9430519c2534d1b3e5049e87d2fd9d2ce88931da552` | LINKDT: 1949-07-01 ~ 2021-10-20; LINKENDDT: 1950-05-30 ~ 2024-08-30; dldte: 1967-12-31 ~ 2025-02-05 | 完成 |
| `stockownershipsummary.csv` | CSV | 210.43 MiB | 1,813,910 | 18 | `f4de655051d1ad0ab32fd301549b941e9b228af2b1977721c5c6167797fdd005` | - | 完成 |
| `属性/CRSP_Stock Header Information(new).csv` | CSV | 9.64 MiB | 40,518 | 36 | `d4c5880976f44067ce56df239fdafca3efc66ff420f24044f6e68abb253c5b59` | SecInfoStartDt: 1925-12-31 ~ 2025-11-11; SecInfoEndDt: 1926-02-24 ~ 2025-12-31; SecurityBegDt: 1925-12-31 ~ 2010-08-02; SecurityEndDt: 1926-02-24 ~ 2025-12-31 | 完成 |
| `日频/crsp0025(daily).csv` | CSV | 26.44 GiB | 49,886,907 | 94 | `9fc00f674babae26553a4d78a521bb84fb4df98a181d6cc6db499bd58f175ff8` | DlyCalDt: 2000-01-03 ~ 2003-12-24; SecurityBegDt: 1986-01-09 ~ 1986-01-09; SecurityEndDt: 2017-08-03 ~ 2017-08-03 | 完成 |
| `日频/crsp2599(daily).csv` | CSV | 29.78 GiB | 60,398,762 | 94 | `5e6148942c8fb66bb96075bac075d950faff5d5f4effae5af799ee0736c9562d` | DlyCalDt: 1986-01-07 ~ 1988-07-15; SecurityBegDt: 1986-01-07 ~ 1986-01-09; SecurityEndDt: 1987-06-11 ~ 2017-08-03 | 完成 |
| `月频/Comp_Quarterly6126.csv` | CSV | 4.25 GiB | 2,110,695 | 679 | `894a434adc17311ec00e7bbbd6ae576a5a18a48bc9ee6af0a9f70fd23763cf43` | datadate: 1962-07-31 ~ 2026-02-28; rdq: 1971-10-07 ~ 2026-03-24; ipodate: 1972-04-24 ~ 1983-03-21 | 完成 |
| `股利分配/CRSP_Distribution.csv` | CSV | 123.41 MiB | 1,101,681 | 22 | `6a978df83062f2e97538383d0927dcd41a386fa6375d47ba3aaa8d9da76c9287` | DisExDt: 1926-01-29 ~ 2025-12-16; DisDeclareDt: 1962-08-03 ~ 2025-11-20; DisRecordDt: 1926-01-29 ~ 2025-12-16; DisPayDt: 1926-01-29 ~ 2026-01-06 | 完成 |
| `退市/crsp_Delisting.csv` | CSV | 3.44 MiB | 29,833 | 22 | `a9800152e2a5a422a96f85deb138b0a24fe4afb5ab3f98c6c815d72977f0213f` | DelistingDt: 1926-02-24 ~ 2025-05-30; DelDtPrc: - ~ -; DelNextDt: 1926-02-27 ~ 2024-12-13 | 完成 |
| `属性/CRSP_Stock Header Information(new).pdf` | PDF | 47.73 KiB | — | — | `23cace5a6e602f1e7d0c22f8053494780c39943a5f97e1c29b7ab3479a09fec0` | 字段字典/说明 | 完成 |
| `日频/crsp2525(daily).pdf` | PDF | 69.41 KiB | — | — | `28c11082154c98ed2c6b33cabab5d3e732269c5944a6e952e80f9e5d5ba07a3d` | 字段字典/说明 | 完成 |
| `月频/Comp_Quarterly6126.pdf` | PDF | 400.37 KiB | — | — | `ff9337996434abdbfc24e77468530f2e3c2192ea7187e67900bda26cdd455396` | 字段字典/说明 | 完成 |
| `股利分配/CRSP_Distribution.pdf` | PDF | 593.10 KiB | — | — | `e21f15d78fbb88caf580b01ffdab0e8dbe2fdae71d1d6313cbe46db5c8a2a4bd` | 字段字典/说明 | 完成 |
| `退市/crsp_Delisting.pdf` | PDF | 44.39 KiB | — | — | `46a1fde4bd8cfe06da61a1cf1142365e41a10669cb486a79d336117e18c6d432` | 字段字典/说明 | 完成 |

## 重复文件组

以下文件内容哈希完全相同；保留原文件，仅在后续代码中指定规范输入：
 - `13f/13ftype1.csv`；`13f/type1.csv`
 - `13f/stock_ownership_summary_csv.csv`；`13f/stockownershipsummary.csv`；`stockownershipsummary.csv`

## 重点文件摘要

### `American Equities.csv`

- 行数：**64,161,557**；列数：**57**；SHA-256：`9127d1833efa49490443ba753696c87997392e8306f8ded2bccd217b7f3de704`

| 日期字段 | 最小日期 | 最大日期 | 无效日期数（扫描部分） |
|---|---|---|---:|
| `datadate` | 2002-05-22 | 2002-05-22 | 0 |

分类字段 Top-N：
- `marketarea`：`US Equity (Others)` (531); `US Equity (S&P500)` (254); `US Equity (RUSSELL 2000)` (76); `CA Equity (TSX60)` (30); `CA Equity (Others)` (23); `UK Equity Others` (17); `DE Equity (Others)` (14); `BR Equity (Others)` (11); `MX Equity (Others)` (10); `CA Equity (TSX MidCap)` (8); `BR Equity (IBOV)` (7); `MX Equity (INMEX)` (6); `JP Equity (Others)` (2); `Other Equity (Others)` (2); `USD N.I.G. Conv Bond (Fixed Rate)` (2); `NL Receipt (Others)` (1); `DK Dom Govt Bond (Fixed Rate)` (1); `NL Equity (Others)` (1); `US ETF` (1); `GBP N.I.G. Conv Bond (Fixed Rate)` (1)

**字段清单**

`dxlid`, `datadate`, `isin`, `sedol`, `cusip`, `quick`, `instrumentname`, `marketarea`, `bbgid`, `bb_ticker`, `valueonloan`, `quantityonloan`, `lendervalueonloan`, `lenderquantityonloan`, `utilisation`, `averagetenure`, `transactioncount`, `activeutilisation`, `activeutilisationbyquantity`, `utilisationbyquantity`, `lenderconcentration`, `lendermarketshare1`, `lendermarketshare2`, `borrowerconcentration`, `borrowermarketshare1`, `borrowermarketshare2`, `shortloanquantity`, `shortloanvalue`, `lenderquantityonloanstability`, `lendervalueonloanstability`, `lendablevalue`, `lendablequantity`, `activelendablevalue`, `activelendablequantity`, `activeavailablevalue`, `activeavailablequantity`, `inventoryconcentration`, `inventorymarketshare1`, `inventorymarketshare2`, `availablequantitystability`, `availablevaluestability`, `lendablequantitystability`, `lendablevaluestability`, `indicativefee`, `indicativerebate`, `dcbs`, `indicativefee1day`, `indicativefee7day`, `indicativerebate1day`, `indicativerebate7day`, `saf`, `sar`, `dns`, `dips`, `dimv`, `dps`, `dss`

### `compustat_supplemental_short_interest.csv.csv`

- 行数：**5,298,058**；列数：**9**；SHA-256：`5aabd70be5e172ca02b43a26acb0cc96fd826e571a94a5bc5086e75657899c23`

| 日期字段 | 最小日期 | 最大日期 | 无效日期数（扫描部分） |
|---|---|---|---:|
| `datadate` | 2006-07-14 | 2026-08-31 | 0 |

**字段清单**

`tic`, `datadate`, `gvkey`, `conm`, `cik`, `iid`, `shortint`, `shortintadj`, `splitadjdate`

### `link.csv`

- 行数：**110,053**；列数：**47**；SHA-256：`fcec8fc3cb86e587fe89e9430519c2534d1b3e5049e87d2fd9d2ce88931da552`

| 日期字段 | 最小日期 | 最大日期 | 无效日期数（扫描部分） |
|---|---|---|---:|
| `LINKDT` | 1949-07-01 | 2021-10-20 | 0 |
| `LINKENDDT` | 1950-05-30 | 2024-08-30 | 51 |
| `dldte` | 1967-12-31 | 2025-02-05 | 0 |

分类字段 Top-N：
- `LINKPRIM`：`C` (596); `P` (365); `N` (23); `J` (16)
- `LINKTYPE`：`NU` (379); `NR` (227); `LU` (225); `LC` (158); `LX` (7); `LN` (2); `LD` (1); `LS` (1)

**字段清单**

`gvkey`, `conm`, `tic`, `cusip`, `cik`, `sic`, `naics`, `LINKPRIM`, `LIID`, `LINKTYPE`, `LPERMNO`, `LPERMCO`, `LINKDT`, `LINKENDDT`, `EIN`, `COSTAT`, `DLRSN`, `PRIUSA`, `PRICAN`, `PRIROW`, `IDBFLAG`, `FIC`, `LOC`, `INCORP`, `STATE`, `COUNTY`, `CITY`, `CONML`, `WEBURL`, `PHONE`, `FAX`, `ADD1`, `ADD2`, `ADD3`, `ADD4`, `ADDZIP`, `BUSDESC`, `ipodate`, `dldte`, `STKO`, `FYRC`, `GSECTOR`, `GGROUP`, `GIND`, `GSUBIND`, `SPCINDCD`, `SPCSECCD`

### `属性/CRSP_Stock Header Information(new).csv`

- 行数：**40,518**；列数：**36**；SHA-256：`d4c5880976f44067ce56df239fdafca3efc66ff420f24044f6e68abb253c5b59`

| 日期字段 | 最小日期 | 最大日期 | 无效日期数（扫描部分） |
|---|---|---|---:|
| `SecInfoStartDt` | 1925-12-31 | 2025-11-11 | 0 |
| `SecInfoEndDt` | 1926-02-24 | 2025-12-31 | 0 |
| `SecurityBegDt` | 1925-12-31 | 2010-08-02 | 0 |
| `SecurityEndDt` | 1926-02-24 | 2025-12-31 | 0 |

分类字段 Top-N：
- `SecurityType`：`EQTY` (996); `FUND` (4)
- `SecuritySubType`：`COM` (996); `CEF` (2); `ETF` (2)
- `ShareType`：`NS` (990); `AD` (7); `SB` (3)

**字段清单**

`PERMNO`, `SecInfoStartDt`, `SecInfoEndDt`, `SecurityBegDt`, `SecurityEndDt`, `SecurityHdrFlg`, `HdrCUSIP`, `HdrCUSIP9`, `CUSIP`, `CUSIP9`, `PrimaryExch`, `ConditionalType`, `ExchangeTier`, `TradingStatusFlg`, `SecurityNm`, `ShareClass`, `USIncFlg`, `IssuerType`, `SecurityType`, `SecuritySubType`, `ShareType`, `SecurityActiveFlg`, `DelActionType`, `DelStatusType`, `DelReasonType`, `DelPaymentType`, `Ticker`, `TradingSymbol`, `PERMCO`, `SICCD`, `NAICS`, `ICBIndustry`, `UESIndustry`, `NASDCompno`, `NASDIssuno`, `IssuerNm`

### `日频/crsp0025(daily).csv`

- 行数：**49,886,907**；列数：**94**；SHA-256：`9fc00f674babae26553a4d78a521bb84fb4df98a181d6cc6db499bd58f175ff8`

| 日期字段 | 最小日期 | 最大日期 | 无效日期数（扫描部分） |
|---|---|---|---:|
| `DlyCalDt` | 2000-01-03 | 2003-12-24 | 0 |
| `SecurityBegDt` | 1986-01-09 | 1986-01-09 | 0 |
| `SecurityEndDt` | 2017-08-03 | 2017-08-03 | 0 |

分类字段 Top-N：
- `SecurityType`：`EQTY` (1,000)
- `SecuritySubType`：`COM` (1,000)
- `ShareType`：`NS` (1,000)
- `PrimaryExch`：`Q` (1,000)

**字段清单**

`PERMNO`, `SecInfoStartDt`, `SecInfoEndDt`, `SecurityBegDt`, `SecurityEndDt`, `SecurityHdrFlg`, `HdrCUSIP`, `HdrCUSIP9`, `CUSIP`, `CUSIP9`, `PrimaryExch`, `ConditionalType`, `ExchangeTier`, `TradingStatusFlg`, `SecurityNm`, `ShareClass`, `USIncFlg`, `IssuerType`, `SecurityType`, `SecuritySubType`, `ShareType`, `SecurityActiveFlg`, `DelActionType`, `DelStatusType`, `DelReasonType`, `DelPaymentType`, `Ticker`, `TradingSymbol`, `PERMCO`, `SICCD`, `NAICS`, `ICBIndustry`, `NASDCompno`, `NASDIssuno`, `IssuerNm`, `YYYYMMDD`, `DlyCalDt`, `DlyDelFlg`, `DlyPrc`, `DlyPrcFlg`, `DlyCap`, `DlyCapFlg`, `DlyPrevPrc`, `DlyPrevPrcFlg`, `DlyPrevDt`, `DlyPrevCap`, `DlyPrevCapFlg`, `DlyRet`, `DlyRetx`, `DlyRetI`, `DlyRetMissFlg`, `DlyRetDurFlg`, `DlyOrdDivAmt`, `DlyNonOrdDivAmt`, `DlyFacPrc`, `DlyDistRetFlg`, `DlyVol`, `DlyClose`, `DlyLow`, `DlyHigh`, `DlyBid`, `DlyAsk`, `DlyOpen`, `DlyNumTrd`, `DlyMMCnt`, `DlyPrcVol`, `ShrStartDt`, `ShrEndDt`, `ShrOut`, `ShrSource`, `ShrFacType`, `ShrAdrFlg`, `DisExDt`, `DisSeqNbr`, `DisOrdinaryFlg`, `DisType`, `DisFreqType`, `DisPaymentType`, `DisDetailType`, `DisTaxType`, `DisOrigCurType`, `DisDivAmt`, `DisFacPr`, `DisFacShr`, `DisDeclareDt`, `DisRecordDt`, `DisPayDt`, `DisPERMNO`, `DisPERMCO`, `vwretd`, `vwretx`, `ewretd`, `ewretx`, `sprtrn`

### `日频/crsp2599(daily).csv`

- 行数：**60,398,762**；列数：**94**；SHA-256：`5e6148942c8fb66bb96075bac075d950faff5d5f4effae5af799ee0736c9562d`

| 日期字段 | 最小日期 | 最大日期 | 无效日期数（扫描部分） |
|---|---|---|---:|
| `DlyCalDt` | 1986-01-07 | 1988-07-15 | 0 |
| `SecurityBegDt` | 1986-01-07 | 1986-01-09 | 0 |
| `SecurityEndDt` | 1987-06-11 | 2017-08-03 | 0 |

分类字段 Top-N：
- `SecurityType`：`EQTY` (999)
- `SecuritySubType`：`COM` (999); `UNK` (1)
- `ShareType`：`NS` (999)
- `PrimaryExch`：`Q` (999); `X` (1)

**字段清单**

`PERMNO`, `SecInfoStartDt`, `SecInfoEndDt`, `SecurityBegDt`, `SecurityEndDt`, `SecurityHdrFlg`, `HdrCUSIP`, `HdrCUSIP9`, `CUSIP`, `CUSIP9`, `PrimaryExch`, `ConditionalType`, `ExchangeTier`, `TradingStatusFlg`, `SecurityNm`, `ShareClass`, `USIncFlg`, `IssuerType`, `SecurityType`, `SecuritySubType`, `ShareType`, `SecurityActiveFlg`, `DelActionType`, `DelStatusType`, `DelReasonType`, `DelPaymentType`, `Ticker`, `TradingSymbol`, `PERMCO`, `SICCD`, `NAICS`, `ICBIndustry`, `NASDCompno`, `NASDIssuno`, `IssuerNm`, `YYYYMMDD`, `DlyCalDt`, `DlyDelFlg`, `DlyPrc`, `DlyPrcFlg`, `DlyCap`, `DlyCapFlg`, `DlyPrevPrc`, `DlyPrevPrcFlg`, `DlyPrevDt`, `DlyPrevCap`, `DlyPrevCapFlg`, `DlyRet`, `DlyRetx`, `DlyRetI`, `DlyRetMissFlg`, `DlyRetDurFlg`, `DlyOrdDivAmt`, `DlyNonOrdDivAmt`, `DlyFacPrc`, `DlyDistRetFlg`, `DlyVol`, `DlyClose`, `DlyLow`, `DlyHigh`, `DlyBid`, `DlyAsk`, `DlyOpen`, `DlyNumTrd`, `DlyMMCnt`, `DlyPrcVol`, `ShrStartDt`, `ShrEndDt`, `ShrOut`, `ShrSource`, `ShrFacType`, `ShrAdrFlg`, `DisExDt`, `DisSeqNbr`, `DisOrdinaryFlg`, `DisType`, `DisFreqType`, `DisPaymentType`, `DisDetailType`, `DisTaxType`, `DisOrigCurType`, `DisDivAmt`, `DisFacPr`, `DisFacShr`, `DisDeclareDt`, `DisRecordDt`, `DisPayDt`, `DisPERMNO`, `DisPERMCO`, `vwretd`, `vwretx`, `ewretd`, `ewretx`, `sprtrn`

### `月频/Comp_Quarterly6126.csv`

- 行数：**2,110,695**；列数：**679**；SHA-256：`894a434adc17311ec00e7bbbd6ae576a5a18a48bc9ee6af0a9f70fd23763cf43`

| 日期字段 | 最小日期 | 最大日期 | 无效日期数（扫描部分） |
|---|---|---|---:|
| `datadate` | 1962-07-31 | 2026-02-28 | 0 |
| `rdq` | 1971-10-07 | 2026-03-24 | 0 |
| `ipodate` | 1972-04-24 | 1983-03-21 | 0 |

分类字段 Top-N：
- `indfmt`：`INDL` (1,000)
- `datafmt`：`STD` (1,000)
- `consol`：`C` (1,000)
- `fic`：`USA` (999); `BMU` (1)
- `exchg`：`11` (245); `14` (232); `0` (172); `19` (125); `1` (86); `12` (79); `13` (61)

**字段清单**

`costat`, `curcdq`, `datafmt`, `indfmt`, `consol`, `gvkey`, `datadate`, `conm`, `tic`, `cusip`, `cik`, `exchg`, `fyr`, `fic`, `add1`, `add2`, `add3`, `add4`, `addzip`, `busdesc`, `city`, `conml`, `county`, `dldte`, `dlrsn`, `ein`, `fax`, `fyrc`, `ggroup`, `gind`, `gsector`, `gsubind`, `idbflag`, `incorp`, `ipodate`, `loc`, `naics`, `phone`, `prican`, `prirow`, `priusa`, `sic`, `spcindcd`, `spcseccd`, `spcsrc`, `state`, `stko`, `weburl`, `acctchgq`, `acctstdq`, `adrrq`, `ajexq`, `ajpq`, `apdedateq`, `bsprq`, `compstq`, `curncdq`, `currtrq`, `curuscnq`, `datacqtr`, `datafqtr`, `fdateq`, `finalq`, `fqtr`, `fyearq`, `ogmq`, `pdateq`, `rdq`, `rp`, `scfq`, `srcq`, `staltq`, `updq`, `acchgq`, `acomincq`, `acoq`, `actq`, `altoq`, `ancq`, `anoq`, `aociderglq`, `aociotherq`, `aocipenq`, `aocisecglq`, `aol2q`, `aoq`, `apq`, `aqaq`, `aqdq`, `aqepsq`, `aqpl1q`, `aqpq`, `arcedq`, `arceepsq`, `arceq`, `atq`, `aul3q`, `billexceq`, `capr1q`, `capr2q`, `capr3q`, `capsftq`, `capsq`, `ceiexbillq`, `ceqq`, `cheq`, `chq`, `cibegniq`, `cicurrq`, `ciderglq`, `cimiiq`, `ciotherq`, `cipenq`, `ciq`, `cisecglq`, `citotalq`, `cogsq`, `csh12q`, `cshfd12`, `cshfdq`, `cshiq`, `cshopq`, `cshoq`, `cshprq`, `cstkcvq`, `cstkeq`, `cstkq`, `dcomq`, `dd1q`, `deracq`, `deraltq`, `derhedglq`, `derlcq`, `derlltq`, `diladq`, `dilavq`, `dlcq`, `dlttq`, `doq`, `dpacreq`, `dpactq`, `dpq`, `dpretq`, `drcq`, `drltq`, `dteaq`, `dtedq`, `dteepsq`, `dtepq`, `dvintfq`, `dvpq`, `epsf12`, `epsfi12`, `epsfiq`, `epsfxq`, `epspi12`, `epspiq`, `epspxq`, `epsx12`, `esopctq`, `esopnrq`, `esoprq`, `esoptq`, `esubq`, `fcaq`, `ffoq`, `finacoq`, `finaoq`, `finchq`, `findlcq`, `findltq`, `finivstq`, `finlcoq`, `finltoq`, `finnpq`, `finreccq`, `finrecltq`, `finrevq`, `finxintq`, `finxoprq`, `gdwlamq`, `gdwlia12`, `gdwliaq`, `gdwlid12`, `gdwlidq`, `gdwlieps12`, `gdwliepsq`, `gdwlipq`, `gdwlq`, `glaq`, `glcea12`, `glceaq`, `glced12`, `glcedq`, `glceeps12`, `glceepsq`, `glcepq`, `gldq`, `glepsq`, `glivq`, `glpq`, `hedgeglq`, `ibadj12`, `ibadjq`, `ibcomq`, `ibmiiq`, `ibq`, `icaptq`, `intaccq`, `intanoq`, `intanq`, `invfgq`, `invoq`, `invrmq`, `invtq`, `invwipq`, `ivaeqq`, `ivaoq`, `ivltq`, `ivstq`, `lcoq`, `lctq`, `lltq`, `lnoq`, `lol2q`, `loq`, `loxdrq`, `lqpl1q`, `lseq`, `ltmibq`, `ltq`, `lul3q`, `mibnq`, `mibq`, `mibtq`, `miiq`, `msaq`, `ncoq`, `niitq`, `nimq`, `niq`, `nopiq`, `npatq`, `npq`, `nrtxtdq`, `nrtxtepsq`, `nrtxtq`, `obkq`, `oepf12`, `oeps12`, `oepsxq`, `oiadpq`, `oibdpq`, `opepsq`, `optdrq`, `optfvgrq`, `optlifeq`, `optrfrq`, `optvolq`, `piq`, `pllq`, `pnc12`, `pncd12`, `pncdq`, `pnceps12`, `pncepsq`, `pnciapq`, `pnciaq`, `pncidpq`, `pncidq`, `pnciepspq`, `pnciepsq`, `pncippq`, `pncipq`, `pncpd12`, `pncpdq`, `pncpeps12`, `pncpepsq`, `pncpq`, `pncq`, `pncwiapq`, `pncwiaq`, `pncwidpq`, `pncwidq`, `pncwiepq`, `pncwiepsq`, `pncwippq`, `pncwipq`, `pnrshoq`, `ppegtq`, `ppentq`, `prcaq`, `prcd12`, `prcdq`, `prce12`, `prceps12`, `prcepsq`, `prcpd12`, `prcpdq`, `prcpeps12`, `prcpepsq`, `prcpq`, `prcraq`, `prshoq`, `pstknq`, `pstkq`, `pstkrq`, `rcaq`, `rcdq`, `rcepsq`, `rcpq`, `rdipaq`, `rdipdq`, `rdipepsq`, `rdipq`, `recdq`, `rectaq`, `rectoq`, `rectq`, `rectrq`, `recubq`, `req`, `retq`, `reunaq`, `revtq`, `rllq`, `rra12`, `rraq`, `rrd12`, `rrdq`, `rreps12`, `rrepsq`, `rrpq`, `rstcheltq`, `rstcheq`, `saleq`, `seqoq`, `seqq`, `seta12`, `setaq`, `setd12`, `setdq`, `seteps12`, `setepsq`, `setpq`, `spce12`, `spced12`, `spcedpq`, `spcedq`, `spceeps12`, `spceepsp12`, `spceepspq`, `spceepsq`, `spcep12`, `spcepd12`, `spcepq`, `spceq`, `spidq`, `spiepsq`, `spioaq`, `spiopq`, `spiq`, `sretq`, `stkcoq`, `stkcpaq`, `teqq`, `tfvaq`, `tfvceq`, `tfvlq`, `tieq`, `tiiq`, `tstknq`, `tstkq`, `txdbaq`, `txdbcaq`, `txdbclq`, `txdbq`, `txdiq`, `txditcq`, `txpq`, `txtq`, `txwq`, `uacoq`, `uaoq`, `uaptq`, `ucapsq`, `ucconsq`, `uceqq`, `uddq`, `udmbq`, `udoltq`, `udpcoq`, `udvpq`, `ugiq`, `uinvq`, `ulcoq`, `uniamiq`, `unopincq`, `uopiq`, `updvpq`, `upmcstkq`, `upmpfq`, `upmpfsq`, `upmsubpq`, `upstkcq`, `upstkq`, `urectq`, `uspiq`, `usubdvpq`, `usubpcvq`, `utemq`, `wcapq`, `wdaq`, `wddq`, `wdepsq`, `wdpq`, `xaccq`, `xidoq`, `xintq`, `xiq`, `xoprq`, `xopt12`, `xoptd12`, `xoptd12p`, `xoptdq`, `xoptdqp`, `xopteps12`, `xoptepsp12`, `xoptepsq`, `xoptepsqp`, `xoptq`, `xoptqp`, `xrdq`, `xsgaq`, `acchgy`, `afudccy`, `afudciy`, `amcy`, `aolochy`, `apalchy`, `aqay`, `aqcy`, `aqdy`, `aqepsy`, `aqpy`, `arcedy`, `arceepsy`, `arcey`, `capxy`, `cdvcy`, `chechy`, `cibegniy`, `cicurry`, `cidergly`, `cimiiy`, `ciothery`, `cipeny`, `cisecgly`, `citotaly`, `ciy`, `cogsy`, `cshfdy`, `cshpry`, `cstkey`, `depcy`, `derhedgly`, `dilady`, `dilavy`, `dlcchy`, `dltisy`, `dltry`, `doy`, `dpcy`, `dprety`, `dpy`, `dteay`, `dtedy`, `dteepsy`, `dtepy`, `dvpy`, `dvy`, `epsfiy`, `epsfxy`, `epspiy`, `epspxy`, `esubcy`, `esuby`, `exrey`, `fcay`, `ffoy`, `fiaoy`, `fincfy`, `finrevy`, `finxinty`, `finxopry`, `fopoxy`, `fopoy`, `fopty`, `fsrcoy`, `fsrcty`, `fuseoy`, `fusety`, `gdwlamy`, `gdwliay`, `gdwlidy`, `gdwliepsy`, `gdwlipy`, `glay`, `glceay`, `glcedy`, `glceepsy`, `glcepy`, `gldy`, `glepsy`, `glivy`, `glpy`, `hedgegly`, `ibadjy`, `ibcomy`, `ibcy`, `ibmiiy`, `iby`, `intpny`, `invchy`, `itccy`, `ivacoy`, `ivchy`, `ivncfy`, `ivstchy`, `miiy`, `ncoy`, `niity`, `nimy`, `niy`, `nopiy`, `nrtxtdy`, `nrtxtepsy`, `nrtxty`, `oancfy`, `oepsxy`, `oiadpy`, `oibdpy`, `opepsy`, `optdry`, `optfvgry`, `optlifey`, `optrfry`, `optvoly`, `pdvcy`, `piy`, `plly`, `pncdy`, `pncepsy`, `pnciapy`, `pnciay`, `pncidpy`, `pncidy`, `pnciepspy`, `pnciepsy`, `pncippy`, `pncipy`, `pncpdy`, `pncpepsy`, `pncpy`, `pncwiapy`, `pncwiay`, `pncwidpy`, `pncwidy`, `pncwiepsy`, `pncwiepy`, `pncwippy`, `pncwipy`, `pncy`, `prcay`, `prcdy`, `prcepsy`, `prcpdy`, `prcpepsy`, `prcpy`, `prstkccy`, `prstkcy`, `prstkpcy`, `rcay`, `rcdy`, `rcepsy`, `rcpy`, `rdipay`, `rdipdy`, `rdipepsy`, `rdipy`, `recchy`, `revty`, `rray`, `rrdy`, `rrepsy`, `rrpy`, `saley`, `scstkcy`, `setay`, `setdy`, `setepsy`, `setpy`, `sivy`, `spcedpy`, `spcedy`, `spceepspy`, `spceepsy`, `spcepy`, `spcey`, `spidy`, `spiepsy`, `spioay`, `spiopy`, `spiy`, `sppey`, `sppivy`, `spstkcy`, `srety`, `sstky`, `stkcoy`, `stkcpay`, `tdcy`, `tfvcey`, `tiey`, `tiiy`, `tsafcy`, `txachy`, `txbcofy`, `txbcoy`, `txdcy`, `txdiy`, `txpdy`, `txty`, `txwy`, `uaolochy`, `udfccy`, `udvpy`, `ufretsdy`, `ugiy`, `uniamiy`, `unopincy`, `unwccy`, `uoisy`, `updvpy`, `uptacy`, `uspiy`, `ustdncy`, `usubdvpy`, `utfdocy`, `utfoscy`, `utmey`, `uwkcapcy`, `wcapchy`, `wcapcy`, `wday`, `wddy`, `wdepsy`, `wdpy`, `xidocy`, `xidoy`, `xinty`, `xiy`, `xopry`, `xoptdqpy`, `xoptdy`, `xoptepsqpy`, `xoptepsy`, `xoptqpy`, `xopty`, `xrdy`, `xsgay`, `adjex`, `cshtrq`, `dvpspq`, `dvpsxq`, `mkvaltq`, `prccq`, `prchq`, `prclq`

### `股利分配/CRSP_Distribution.csv`

- 行数：**1,101,681**；列数：**22**；SHA-256：`6a978df83062f2e97538383d0927dcd41a386fa6375d47ba3aaa8d9da76c9287`

| 日期字段 | 最小日期 | 最大日期 | 无效日期数（扫描部分） |
|---|---|---|---:|
| `DisExDt` | 1926-01-29 | 2025-12-16 | 0 |
| `DisDeclareDt` | 1962-08-03 | 2025-11-20 | 0 |
| `DisRecordDt` | 1926-01-29 | 2025-12-16 | 0 |
| `DisPayDt` | 1926-01-29 | 2026-01-06 | 0 |

分类字段 Top-N：
- `DisType`：`CD` (872); `SD` (59); `FRS` (39); `SP` (13); `CP` (10); `TSOO` (7)
- `DisOrdinaryFlg`：`Y` (931); `N` (69)

**字段清单**

`PERMNO`, `DisExDt`, `DisSeqNbr`, `DisOrdinaryFlg`, `DisType`, `DisFreqType`, `DisPaymentType`, `DisDetailType`, `DisTaxType`, `DisOrigCurType`, `DisDivAmt`, `DisFacPr`, `DisFacShr`, `DisDeclareDt`, `DisRecordDt`, `DisPayDt`, `DisPERMNO`, `DisPERMCO`, `DisAmountSourceType`, `PrimaryExch`, `SICCD`, `NASDIssuno`

### `退市/crsp_Delisting.csv`

- 行数：**29,833**；列数：**22**；SHA-256：`a9800152e2a5a422a96f85deb138b0a24fe4afb5ab3f98c6c815d72977f0213f`

| 日期字段 | 最小日期 | 最大日期 | 无效日期数（扫描部分） |
|---|---|---|---:|
| `DelistingDt` | 1926-02-24 | 2025-05-30 | 0 |
| `DelDtPrc` | - | - | 1,000 |
| `DelNextDt` | 1926-02-27 | 2024-12-13 | 0 |

分类字段 Top-N：
- `DelActionType`：`MER` (485); `GDR` (483); `GEX` (18); `GLI` (14)
- `DelStatusType`：`FPAY` (514); `VCL` (483); `UNAV` (2); `NDC` (1)
- `DelReasonType`：`UNAV` (549); `INSC` (134); `DELQ` (67); `MTMK` (58); `LP` (37); `INSF` (37); `FING` (26); `CORQ` (23); `BKPY` (21); `SHLD` (16); `FARG` (11); `MVOT` (9); `EQRQ` (4); `OFFRE` (3); `DERE` (2); `MVPAC` (1); `PUBI` (1); `SERQ` (1)

**字段清单**

`PERMNO`, `DelistingDt`, `DelDtPrc`, `DelDtPrcFlg`, `DelActionType`, `DelStatusType`, `DelReasonType`, `DelPaymentType`, `DelPERMNO`, `DelPERMCO`, `DelRet`, `DelRetMissType`, `DelNextDt`, `DelNextPrc`, `DelNextPrcFlg`, `DelAmtDt`, `DelDivAmt`, `DelDisType`, `DelDlyDt`, `PrimaryExch`, `SICCD`, `NASDIssuno`

## 指南第一部分逐项落实核对

| 指南项目 | 当前本地证据 | 当前状态 | 对照结论与复刻影响 |
|---|---|---|---|
| Markit 买方口径借券费 | `American Equities.csv` | **已获取** | 文件存在，但仍需核对字段单位、覆盖期和证券匹配。 |
| CRSP 日频股票文件 | `日频/crsp0025(daily).csv`；`日频/crsp2599(daily).csv` | **已获取** | 可用于普通股筛选、价量信号和收益构造。 |
| CRSP 分配表 | `股利分配/CRSP_Distribution.csv` | **已获取** | 用于显式股利事件核验。 |
| CRSP 退市文件 | `退市/crsp_Delisting.csv`；`退市/crsp_Delisting.pdf` | **已获取** | 用于退市收益处理；原型中单独记录退市限制。 |
| CRSP 证券属性表 | `属性/CRSP_Stock Header Information(new).csv`；`属性/CRSP_Stock Header Information(new).pdf` | **已获取** | 用于 CIZ 普通股映射和历史 CUSIP。 |
| CRSP 月频 | `月频/Comp_Quarterly6126.csv`；`月频/Comp_Quarterly6126.pdf` | **已获取** | 当前月频面板由日频 CRSP 聚合。 |
| Compustat 年度与 Pension Annual | （未发现对应文件） | **未获取** | 当前只有季度 Compustat，不能替代年度点时财务数据。 |
| CCM 链接表 | `link.csv` | **基本具备** | 按有效日期使用；不等同于完整 JKMP 输入。 |
| 月度空头兴趣 | `compustat_supplemental_short_interest.csv.csv` | **已获取** | 字段定义和覆盖期仍需核对。 |
| Chen-Zimmermann 信号面板 | （未发现对应文件） | **未获取** | 当前检测到相关代码/文件，是否为可执行成品面板需另行确认。 |
| DGTW/因子收益 | （未发现对应文件） | **未获取** | 成品 DGTW/因子文件未发现，后续可自建。 |
| 课表 | 用户说明已发送；证据和日期待补充 | **已发送（待补证）** | 本次记录不伪造发送凭证。 |

## 研究复现边界

- 文件存在不等于研究输入已经完成；仍需逐字段确认口径、单位、许可证和点时可得性。
- CRSP CIZ 普通股筛选采用 `SecurityType=EQTY`、`SecuritySubType=COM`、`ShareType=NS` 的近似映射，不直接声称等于旧版 `shrcd=10/11`。
- 官方 JKMP 全量复现仍受官方数据文件、R/Rscript、因子面板和集群运行环境限制。
- 课表按用户说明记录为已发送，具体证据和日期留待补充。
