# longbridge-quant

基于 Longbridge CLI 的美股数据适配与基本面筛选底座。

当前定位不是自动交易系统，也不把纯技术指标作为买卖建议。项目保留少量
EMA/MACD 逻辑作为实验性辅助，主要价值在于拉取/缓存长桥数据、构建股票池、
做基本面筛选，并为后续的持仓体检或候选股研究日报提供底座。

## 环境

- Python 3.14 + uv
- 系统工具: `longbridge` CLI
- Python 依赖: `pandas`, `pyarrow`

## 认证

认证由 Longbridge CLI 管理。首次使用前运行：

```bash
longbridge auth login
longbridge check --format json
```

token 缓存在 `~/.longbridge/openapi/tokens/`。项目里的 Python 代码只调用
`longbridge ... --format json`，不直接持有 `client_id`，也不依赖 Python SDK。

## 项目结构

```
longbridge_cli.py  # Longbridge CLI JSON adapter
lb_config.py / cache.py / universe.py / sectors_data.py   # 共享基础设施
fundamental/     # 基本面分析 (估值/资金流/多周期动量/筛选)
technical/       # 实验性技术辅助 (EMA/MACD/回踩扫描)
scripts/         # CLI 入口
```

## 运行方式

所有脚本以模块模式运行：

```bash
uv run python -m scripts.<script_name> [args...]
```

## 核心功能

### 1. 基本面筛选 — `scripts/fundamental_scan.py`

一次 `longbridge calc-index ... --format json` 批量拉取 PE/PB/股息率/资金流/多周期动量等 13 个指标，按条件筛选。

```bash
# 低 PE 筛选（自动排除亏损）
uv run python -m scripts.fundamental_scan --universe tech_largecap --pe-max 25 --sort pe_ttm

# 高股息
uv run python -m scripts.fundamental_scan --universe all_largecap --dividend-min 3.0

# 资金流入 + YTD 领涨
uv run python -m scripts.fundamental_scan --universe tech_largecap \
    --capital-flow-positive --sort ytd_return --desc

# 单股详情 (含日内资金流和大小单分布)
uv run python -m scripts.fundamental_scan --symbol AAPL.US --detail
```

### 2. 实验性 EMA 回踩扫描 — `scripts/pullback_scan.py`

日线+周线均为 EMA 多头排列前提下，扫描日内低点回踩 EMA 的股票并做持仓回测。
这只适合做辅助观察，不应单独当成交易信号。

```bash
# 默认: 科技大盘股池 + 最近 10 个自然日窗口 + 持有到最新收盘
uv run python -m scripts.pullback_scan

# 指定股票池和日期窗口
uv run python -m scripts.pullback_scan --universe nasdaq_largecap --window 2026-03-27:2026-04-02

# 指定 EMA 级别 + 持有天数 + MACD 过滤
uv run python -m scripts.pullback_scan --window 2026-03-27:2026-04-02 --hold 10 --ema 55,100 --macd-filter

# 关闭趋势过滤做对照
uv run python -m scripts.pullback_scan --window 2026-03-27:2026-04-02 --no-trend-filter
```

### 3. 实验性技术 + 基本面组合扫描 — `scripts/combo_scan.py`

管道式组合：universe → 基本面筛选 → EMA 回踩扫描 → 合并排序。
这个入口仍然保留，但定位是研究候选排序实验，不是买卖建议。

```bash
# 低估值 + 资金流入 + EMA 回踩
uv run python -m scripts.combo_scan --universe tech_largecap \
    --pe-max 30 --capital-flow-positive \
    --window 2026-04-01:2026-04-10 --ema 55,100

# 价值 + 高股息 + 回踩
uv run python -m scripts.combo_scan --universe all_largecap \
    --pe-max 15 --dividend-min 2.0 \
    --window 2026-04-01:2026-04-10
```

## 数据权限

当前账户权限:
- US: Nasdaq Basic
- HK: LV1 Real-time Quotes
- CN: LV1 Real-time Quotes
- USOption: 未开通

## 缓存

本地 parquet 缓存在 `.cache/`（已加入 `.gitignore`）。可通过 `LB_CACHE_MAX_AGE_HOURS` 覆盖过期时间，`rm -rf .cache/` 强制刷新。
