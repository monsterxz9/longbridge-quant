# longbridge-quant

基于 [长桥 OpenAPI SDK](https://github.com/longbridge/openapi) 的量化交易工具集。

## 环境

- Python 3.14 + uv
- 依赖: `longbridge`, `pandas`

## 认证

使用 OAuth 2.0 认证。`client_id` 默认内置在 `lb_config.py`，首次运行会弹出浏览器授权，token 缓存在 `~/.longbridge/openapi/tokens/`。

如需使用自己的 `client_id`，可以通过环境变量 `LB_CLIENT_ID` 覆盖：

```bash
export LB_CLIENT_ID=your-longbridge-oauth-client-id
```

或者把仓库根目录下的 `.env.example` 复制为 `.env` 后填入值（需要搭配 `direnv` / `dotenv-cli` 等工具加载，项目本身不依赖 `python-dotenv`）。

如需重新注册 client:

```bash
curl -X POST https://openapi.longbridge.com/oauth2/register \
  -H "Content-Type: application/json" \
  -d '{
    "app_key": "YOUR_APP_KEY",
    "app_secret": "YOUR_APP_SECRET",
    "client_name": "longbridge-quant",
    "redirect_uris": ["http://localhost:60355/callback"],
    "grant_types": ["authorization_code", "refresh_token"]
  }'
```

## 脚本说明

### `get_quote.py` — 基础行情

获取实时行情、标的基本信息、历史日 K 线。入门验证 SDK 连通性。

```bash
uv run get_quote.py
```

### `ema_macd_strategy.py` — EMA + MACD 策略分析

对单个标的做日线 + 周线的技术分析:

- **EMA**: 21 / 55 / 100 / 200 日均线，判断多头/空头/交织排列
- **MACD**: DIF / DEA / 柱状图，检测金叉/死叉
- **综合信号**: EMA 多头排列 + MACD 金叉 = BUY，EMA 空头排列 + MACD 死叉 = SELL

```bash
uv run ema_macd_strategy.py
```

可直接 import 使用:

```python
from ema_macd_strategy import get_config, analyze
from longbridge.openapi import QuoteContext

config = get_config()
ctx = QuoteContext(config)
analyze(ctx, "AAPL.US")
```

### `sector_analysis.py` — 板块分类扫描

对美股 20 个细分板块做批量扫描，输出每只标的的 EMA/MACD 状态，并按综合评分排名。

覆盖板块:
- 指数 ETF / 消费电子 / 互联网广告 / 流媒体 / 电商云
- 企业软件 / AI 基础设施 / AI 应用 / 存储内存 / 传统半导体
- 网络安全 / 网络通信 / 金融 / 支付 Fintech / 医疗保健
- 消费 / 能源 / 工业 / 公用防御 / 地产 REITs

评分公式: `EMA多头占比 * 50% + MACD多方占比 * 30% + 价格位置 * 20%`

```bash
uv run sector_analysis.py
```

编辑文件顶部的 `SECTORS` 字典可自定义板块和标的。

### `extended_hours.py` — 盘前/盘后/夜盘行情

查看美股盘前 (pre-market)、盘后 (post-market)、夜盘 (overnight) 实时报价。

```bash
uv run extended_hours.py
```

## 数据权限

当前账户权限:
- US: Nasdaq Basic
- HK: LV1 Real-time Quotes
- CN: LV1 Real-time Quotes
- USOption: 未开通
