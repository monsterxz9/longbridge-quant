"""集中配置：CLI、缓存路径、策略常量。

所有需要长桥数据的脚本都应 `from lb_config import get_client`，避免
Longbridge CLI 初始化代码重复。
"""

import os
from pathlib import Path

from longbridge_cli import LongbridgeCLI

# Longbridge CLI 二进制。认证由 `longbridge auth login` 管理。
LONGBRIDGE_CLI = os.environ.get("LONGBRIDGE_CLI", "longbridge")

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


def get_client() -> LongbridgeCLI:
    """构建 Longbridge CLI adapter。"""
    return LongbridgeCLI(binary=LONGBRIDGE_CLI)
