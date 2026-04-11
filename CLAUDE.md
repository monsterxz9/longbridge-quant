# longbridge-quant

## 项目概述
基于长桥 OpenAPI 的美股量化交易工具集，使用 Python + pandas 做技术分析。

## 技术栈
- Python 3.14 + uv (虚拟环境在 `.venv/`)
- 依赖: `longbridge` (OpenAPI SDK), `pandas`, `pyarrow` (parquet 缓存)
- 运行: `uv run <script>.py`

## 本地缓存
- K线 / 市值数据缓存在项目内 `.cache/`（已加入 `.gitignore`）
- 日K线: `.cache/daily/{symbol}.parquet`，默认 12 小时过期
- 市值快照: `.cache/large_caps.parquet`，默认 24 小时过期
- 过期时间可通过环境变量 `LB_CACHE_MAX_AGE_HOURS` 覆盖
- 强制刷新: `rm -rf .cache/`

## 认证
- 使用 OAuth 2.0，默认 `client_id` 在 `lb_config.py` 作为 fallback
- 可用环境变量 `LB_CLIENT_ID` 覆盖默认值（参考 `.env.example`）
- token 缓存在 `~/.longbridge/openapi/tokens/`
- 如果 token 过期，运行脚本会自动弹浏览器重新授权
- 环境变量 `LONGBRIDGE_ENABLE_OVERNIGHT=true` 启用夜盘数据

## 项目结构
```
lb_config.py          # 集中配置 (CLIENT_ID / CACHE_DIR / get_config)
cache.py              # K线与市值的本地 parquet 缓存层
universe.py           # 动态美股股票池 (all/nasdaq/tech largecap + NYSE 科技白名单)
scanner.py            # EMA 回踩扫描器 + 持仓回测器 (find_ema_pullbacks / backtest_pullback / scan_universe)
sectors_data.py       # SECTORS 字典 (精选关注池)
ema_macd_strategy.py  # EMA 21/55/100/200 + MACD 策略 (日线+周线)
sector_analysis.py    # 基于 SECTORS 的板块批量扫描 + 强弱排名
pullback_scan.py      # EMA 回踩扫描 CLI (--universe / --window / --hold / --ema / --macd-filter / --no-trend-filter)
get_quote.py          # 基础行情示例
extended_hours.py     # 盘前/盘后/夜盘行情
```

## 核心模块关系
- `lb_config.py` 是叶子模块，提供 `get_config()`、`CACHE_DIR`、常量
- `ema_macd_strategy.py` 从 `lb_config` re-export `get_config()`，并提供 `fetch_daily()`, `calc_ema()`, `calc_macd()`, `detect_signals()` 等函数
- `cache.py` 包装 `ctx.candlesticks` 和 `ctx.calc_indexes`，写 parquet
- `universe.py` 基于 `cache.get_large_caps_cached()` 构建动态股票池
- `scanner.py` 组合 `cache + calc_ema/macd` 实现可复用的 EMA 回踩扫描
- `pullback_scan.py` 是 CLI 入口，调用 `universe + scanner`
- `sector_analysis.py` 改走 `cache.fetch_daily_cached`，第二次运行显著加速

## 策略逻辑
- **EMA 排列**: 21 > 55 > 100 > 200 = 多头，反之 = 空头，其他 = 交织
- **MACD**: DIF 上穿 DEA = 金叉，DIF 下穿 DEA = 死叉
- **综合信号**: EMA多头 + MACD金叉 = BUY，EMA空头 + MACD死叉 = SELL
- **EMA 回踩** (`scanner.py` / `pullback_scan.py`): 日线+周线均为 EMA 多头排列前提下，日内低点触及 EMA ±tolerance 且当日收盘回到 EMA 附近（容差内允许短暂跌破）。趋势过滤默认开启，可用 `--no-trend-filter` 关闭做对照。
- **板块评分**: EMA多头占比 × 50% + MACD多方占比 × 30% + 价格位置 × 20%

## 板块配置
`sector_analysis.py` 顶部 `SECTORS` 字典定义板块和标的，只看美股，覆盖:
- 科技细分: 消费电子、互联网广告、流媒体、电商云、企业软件、AI基础设施、AI应用、存储内存、传统半导体、网络安全、网络通信
- 非科技: 金融、支付Fintech、医疗、消费、能源、工业、公用防御、地产REITs、指数ETF

## 数据权限
- US: Nasdaq Basic
- USOption: 未开通

## 开发约定
- 长桥 SDK 的 `SecurityQuote` 没有 `change_rate` 属性，需用 `(last_done - prev_close) / prev_close` 手动计算
- K 线用 `ctx.candlesticks()` 方法，`history_candlesticks_by_offset()` 会报 symbol count out of limit
- 新增脚本如需认证，复用 `ema_macd_strategy.get_config()`
