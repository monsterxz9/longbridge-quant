"""集中配置：认证、缓存路径、策略常量。

所有需要长桥 OAuth 配置的脚本都应 `from lb_config import get_config`，
避免 CLIENT_ID 和 OAuth 初始化代码的重复。
"""

import os
from pathlib import Path

from longbridge.openapi import Config, OAuthBuilder

# OAuth 认证 — 首次运行会打开浏览器授权，之后自动使用缓存 token
# 注册时的 client_id（见 get_quote.py 历史说明）
# 优先从环境变量 LB_CLIENT_ID 读取，未设置时回退到默认值（仅个人本地使用）。
# 公开仓库 / 多人协作 / CI 场景请删除默认值并强制通过环境变量注入。
CLIENT_ID = os.environ.get(
    "LB_CLIENT_ID", "891f2a46-d6d0-4302-a0a0-a2297b02a4e4"
)

# 项目内 .cache/ 缓存目录（已加入 .gitignore）
# 可通过 LB_CACHE_DIR 环境变量覆盖
PROJECT_ROOT = Path(__file__).resolve().parent
CACHE_DIR = Path(os.environ.get("LB_CACHE_DIR", PROJECT_ROOT / ".cache"))
CACHE_DIR.mkdir(parents=True, exist_ok=True)
(CACHE_DIR / "daily").mkdir(exist_ok=True)

# 缓存过期时间（小时），可通过环境变量覆盖
CACHE_MAX_AGE_HOURS = float(os.environ.get("LB_CACHE_MAX_AGE_HOURS", "12"))

# 策略默认值
DEFAULT_EMA_PERIODS: list[int] = [21, 55, 100, 200]
DEFAULT_MACD: tuple[int, int, int] = (12, 26, 9)

# 大盘股市值阈值（美元）
LARGE_CAP_THRESHOLD: float = 10_000_000_000  # 100 亿美元


def get_config() -> Config:
    """构建 OAuth 认证配置。首次调用会弹浏览器，之后使用 SDK 缓存的 token。"""
    oauth = OAuthBuilder(CLIENT_ID).build(
        lambda url: print(f"\n请在浏览器中打开此链接完成授权:\n  {url}\n")
    )
    return Config.from_oauth(oauth)
