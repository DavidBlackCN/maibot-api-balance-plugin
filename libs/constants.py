"""常量定义 — maibot-api-balance-plugin"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# --- 版本号（从 _manifest.json 读取，保持单一来源） ---

def _load_manifest_version() -> str:
    """从 _manifest.json 读取版本号。"""
    try:
        manifest_path = Path(__file__).parent.parent / "_manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        version = data.get("version")
        if isinstance(version, str) and version.strip():
            return version.strip()
        logger.warning(
            "_manifest.json 中 version 字段缺失或非法 (%r)，回落到 0.0.0", version,
        )
    except Exception:
        logger.warning("读取 _manifest.json 失败，回落到 0.0.0", exc_info=True)
    return "0.0.0"


PLUGIN_VERSION = _load_manifest_version()
CONFIG_SCHEMA_VERSION = "1.0.0"
DEFAULT_TIMEOUT = 10  # 秒

# --- 平台默认端点 ---

DEEPSEEK_DEFAULT_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_BALANCE_PATH = "/user/balance"

SILICONFLOW_DEFAULT_BASE_URL = "https://api.siliconflow.cn"
SILICONFLOW_USER_INFO_PATH = "/v1/user/info"

NEWAPI_DEFAULT_BASE_URL = "https://api.newapi.pro"
NEWAPI_USER_SELF_PATH = "/api/user/self"

# --- 币种符号 ---

CURRENCY_SYMBOLS = {"CNY": "￥", "USD": "$", "EUR": "€", "JPY": "¥"}

# --- 输出格式 ---

OUTPUT_FORMAT_TEXT = "text"
OUTPUT_FORMAT_IMAGE = "image"
OUTPUT_FORMAT_BOTH = "both"
OUTPUT_FORMATS = (OUTPUT_FORMAT_TEXT, OUTPUT_FORMAT_IMAGE, OUTPUT_FORMAT_BOTH)
