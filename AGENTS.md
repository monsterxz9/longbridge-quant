# longbridge-quant

## 项目概述
基于 Longbridge CLI 的美股数据适配与基本面筛选底座，使用 Python + pandas 拉取、缓存、筛选美股数据。
当前不把纯技术指标定位为买卖建议；EMA/MACD 相关代码只作为实验性辅助。

## 技术栈
- Python 3.14 + uv (虚拟环境在 `.venv/`)
- 系统工具: `longbridge` CLI（先运行 `longbridge auth login`）
- Python 依赖: `pandas`, `pyarrow` (parquet 缓存)
- 运行: `uv run python -m scripts.<script_name>` (使用模块模式，保证 import 路径正确)

## 本地缓存
- K线 / 市值 / 基本面数据缓存在项目内 `.cache/`（已加入 `.gitignore`）
- 日K线: `.cache/daily/{symbol}.parquet`，默认 12 小时过期
- 市值快照: `.cache/large_caps.parquet`，默认 24 小时过期
- 基本面数据: `.cache/fundamentals.parquet`，默认 24 小时过期
- 过期时间可通过环境变量 `LB_CACHE_MAX_AGE_HOURS` 覆盖
- 强制刷新: `rm -rf .cache/`

## 认证
- 认证由 Longbridge CLI 管理，先运行 `longbridge auth login`
- 可用 `longbridge check --format json` 检查 token 和连通性
- token 缓存在 `~/.longbridge/openapi/tokens/`
- 如果 token 过期，重新运行 `longbridge auth login`
- 可用环境变量 `LONGBRIDGE_CLI` 覆盖 CLI 二进制路径

## 项目结构
```
longbridge_cli.py          # Longbridge CLI JSON adapter
lb_config.py               # 集中配置 (LONGBRIDGE_CLI / CACHE_DIR / get_client)
cache.py                   # K线 / 市值 / 基本面的本地 parquet 缓存层
universe.py                # 动态美股股票池 (all/nasdaq/tech largecap + NYSE 科技白名单)
sectors_data.py            # SECTORS 字典 (精选关注池)

technical/                 # 实验性技术辅助
    __init__.py            # re-export calc_ema / calc_macd / detect_signals / resample_weekly
    indicators.py          # EMA / MACD / 信号检测 纯计算函数
    scanner.py             # EMA 回踩扫描器 + 持仓回测 (PullbackEvent / find_ema_pullbacks / backtest_pullback / scan_universe)
    sector_scan.py         # 基于 SECTORS 的板块批量扫描 + 强弱排名

fundamental/               # 基本面分析
    __init__.py
    data.py                # 基本面数据获取 (get_universe_fundamentals / get_single_fundamental)
    screen.py              # ScreenCriteria dataclass + screen() 筛选引擎
    report.py              # print_fundamental_table / print_fundamental_report

scripts/                   # CLI 入口
    __init__.py
    fundamental_scan.py    # 基本面筛选 CLI (--pe-max / --dividend-min / --capital-flow-positive / --sort / --detail)
    pullback_scan.py       # 实验性 EMA 回踩扫描 CLI
    combo_scan.py          # 实验性技术+基本面组合扫描 CLI
```

## 核心模块关系
- `lb_config.py` 是叶子模块，提供 `get_client()`、`CACHE_DIR`、常量
- `longbridge_cli.py` 封装 `longbridge ... --format json`，策略层不直接依赖 SDK 对象
- `cache.py` 包装 Longbridge CLI 的 `kline` / `calc-index` / `security-list` / `static`，提供三组缓存：
  - `fetch_daily_cached()` / `fetch_daily_batch()` — 日线 K 线
  - `get_large_caps_cached()` — 全美股市值快照
  - `fetch_fundamentals_cached()` — 基本面批量指标 (PE/PB/股息/资金流/多周期动量等 13 项)
- `universe.py` 基于 `cache.get_large_caps_cached()` 构建动态股票池
- `technical/scanner.py` 组合 `cache + technical.indicators` 实现实验性 EMA 回踩扫描
- `fundamental/data.py` 封装 `cache.fetch_fundamentals_cached()` + universe 加载
- `fundamental/screen.py` 提供 `ScreenCriteria` + `screen()` 做 pandas 筛选
- `scripts/combo_scan.py` 管道：universe → 基本面筛选 → 技术面扫描 → 合并排序（实验性）

## 运行方式

所有脚本使用模块模式运行（项目根目录必须在 sys.path）：

```bash
# 基本面筛选
uv run python -m scripts.fundamental_scan --universe tech_largecap --pe-max 25 --sort pe_ttm
uv run python -m scripts.fundamental_scan --symbol AAPL.US --detail

# 实验性 EMA 回踩扫描
uv run python -m scripts.pullback_scan --universe tech_largecap --window 2026-04-01:2026-04-10

# 实验性技术+基本面组合扫描
uv run python -m scripts.combo_scan --universe tech_largecap --pe-max 30 --window 2026-04-01:2026-04-10
```

## 策略/筛选逻辑
- **基本面筛选**: `ScreenCriteria` 包含 PE/PB/股息率/资金流/YTD/市值等字段，pandas boolean mask 实现。默认跳过 NaN 值（不因缺数据而排除股票）。PE 上限过滤会自动排除亏损（PE<=0）。
- **EMA 排列**: 21 > 55 > 100 > 200 = 多头，反之 = 空头，其他 = 交织
- **MACD**: DIF 上穿 DEA = 金叉，DIF 下穿 DEA = 死叉
- **EMA 回踩** (`technical/scanner.py`): 日线+周线均为 EMA 多头排列前提下，日内低点触及 EMA ±tolerance 且当日收盘回到 EMA 附近（容差内允许短暂跌破）。趋势过滤默认开启，可用 `--no-trend-filter` 关闭做对照。
- **板块评分**: EMA多头占比 × 50% + MACD多方占比 × 30% + 价格位置 × 20%
- **组合扫描管道**: universe → 基本面筛选得到 filtered_symbols → 技术面 `scan_universe(filtered_symbols)` → merge 基本面列 → 按 return_pct 排序。
- 技术相关输出只作为辅助观察，不作为买卖建议。

## 基本面数据指标

`longbridge_cli.FUNDAMENTAL_FIELDS` 定义了 `longbridge calc-index` 批量拉取的 13 个字段，返回 DataFrame 列：

| 列名 | CLI 字段 | 含义 |
|------|-----------|------|
| `pe_ttm` | `pe` | 市盈率 TTM |
| `pb` | `pb` | 市净率 |
| `dividend_yield` | `dps_rate` | 股息率 (%) |
| `turnover_rate` | `turnover_rate` | 换手率 (%) |
| `volume_ratio` | `volume_ratio` | 量比 |
| `amplitude` | `amplitude` | 振幅 (%) |
| `capital_flow` | `capital_flow` | 净资金流 |
| `ytd_return` | `ytd_change_rate` | YTD 涨幅 (%) |
| `half_year_return` | `half_year_change_rate` | 半年涨幅 (%) |
| `five_day_return` / `ten_day_return` | `five_day_change_rate` / `ten_day_change_rate` | 短期动量 |
| `market_cap` | `mktcap` | 总市值 |
| `last_done` | `last_done` | 最新价 |

单股详细报告 (`get_single_fundamental` + `--detail`) 额外调用 `longbridge capital --flow` 取时序资金流、`longbridge capital` 取大小单分布。

## 板块配置
`sectors_data.py` 的 `SECTORS` 字典定义板块和标的，只看美股，覆盖:
- 科技细分: 消费电子、互联网广告、流媒体、电商云、企业软件、AI基础设施、AI应用、存储内存、传统半导体、网络安全、网络通信
- 非科技: 金融、支付Fintech、医疗、消费、能源、工业、公用防御、地产REITs、指数ETF

## 数据权限
- US: Nasdaq Basic
- USOption: 未开通

## 开发约定
- 数据接入默认走 `longbridge ... --format json`，不要再新增 Python SDK 依赖
- 新增脚本如需长桥数据，直接 `from lb_config import get_client`
- 新增脚本放 `scripts/`，使用 `uv run python -m scripts.xxx` 运行
- argparse help 字符串里的 `%` 需要写成 `%%`（Python 3.14 会校验 help 模板格式）
- CLI 返回的数值多为字符串，字段转换统一放在 `longbridge_cli.py` / `cache._safe_float()`
