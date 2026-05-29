"""常量定义 — maibot-api-balance-plugin v1.1.0"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def _load_manifest_version() -> str:
    try:
        manifest_path = Path(__file__).parent.parent / "_manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        version = data.get("version")
        if isinstance(version, str) and version.strip():
            return version.strip()
    except Exception:
        logger.warning("读取 _manifest.json 失败，回落到 0.0.0", exc_info=True)
    return "0.0.0"

PLUGIN_VERSION = _load_manifest_version()
CONFIG_SCHEMA_VERSION = "1.1.0"
DEFAULT_TIMEOUT = 10

# --- 平台端点注册表 ---
ENDPOINTS = {
    "deepseek":    ("https://api.deepseek.com", "/user/balance"),
    "siliconflow": ("https://api.siliconflow.cn", "/v1/user/info"),
    "newapi":      ("https://api.newapi.pro", "/api/user/self"),
    "openrouter":  ("https://openrouter.ai", "/api/v1/credits"),
    "moonshot":    ("https://api.moonshot.cn", "/v1/users/me/balance"),
    "openai":      ("https://api.openai.com", "/v1/dashboard/billing/subscription"),
    "onething":    ("https://api-lab.onethingai.com", "/api/v1/account/wallet/detail"),
    "minimax":     ("https://www.minimaxi.com", "/v1/api/openplatform/coding_plan/remains"),
}

PLATFORM_TYPES = list(ENDPOINTS.keys())

# --- 币种符号 ---
CURRENCY_SYMBOLS = {"CNY": "￥", "USD": "$", "EUR": "€", "JPY": "¥"}

# --- 输出格式 ---
OUTPUT_FORMAT_TEXT = "text"
OUTPUT_FORMAT_IMAGE = "image"
OUTPUT_FORMAT_BOTH = "both"
OUTPUT_FORMATS = (OUTPUT_FORMAT_TEXT, OUTPUT_FORMAT_IMAGE, OUTPUT_FORMAT_BOTH)
