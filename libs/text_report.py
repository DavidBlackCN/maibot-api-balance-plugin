"""文本报告格式化 — maibot-api-balance-plugin

将查询结果汇总为纯文本消息。
"""

import logging
from typing import Any, List, Optional, Sequence, Tuple

from .constants import CURRENCY_SYMBOLS
from .providers import (
    _BalanceHTTPError,
    _BalanceBusinessError,
    _BalanceRequestError,
    _BalanceProvider,
    _BalanceRecord,
)

logger = logging.getLogger(__name__)


def format_text_report(
    records: Sequence[Tuple[_BalanceProvider, Any]],
) -> str:
    """把所有 Provider 的结果（record 或异常）汇总为发送给用户的文本。"""
    lines: List[str] = ["💰 API 平台余额"]
    for provider, item in records:
        lines.append("———")
        lines.append(f"【{provider.display_name}】")
        error_line = _format_error_line(provider, item)
        if error_line is not None:
            lines.append(error_line)
            continue
        assert isinstance(item, _BalanceRecord)
        lines.extend(_format_record_text_lines(item))
    return "\n".join(lines)


def _format_error_line(
    provider: _BalanceProvider, item: Any
) -> Optional[str]:
    """识别异常类型并返回单行错误描述；非异常返回 None。"""
    if isinstance(item, _BalanceHTTPError):
        logger.warning(
            "%s 查询 HTTP %s: %s",
            provider.display_name,
            item.status,
            item.detail,
        )
        if item.status in (401, 403):
            return "❌ API Key 无效或权限不足"
        return f"❌ HTTP {item.status}：{item.detail}"
    if isinstance(item, _BalanceBusinessError):
        logger.warning(
            "%s 业务失败: %s", provider.display_name, item
        )
        return f"❌ 业务失败：{item}"
    if isinstance(item, _BalanceRequestError):
        logger.warning(
            "%s 网络异常: %s", provider.display_name, item
        )
        return f"❌ 网络错误：{item}"
    if isinstance(item, Exception):
        return "❌ 内部错误（详见日志）"
    return None


def _format_record_text_lines(record: _BalanceRecord) -> List[str]:
    """将单个 _BalanceRecord 格式化为文本行列表。"""
    lines: List[str] = []
    if record.status:
        mark = "✅" if record.status_ok else "⚠️"
        lines.append(f"状态：{mark} {record.status}")
    if record.note:
        lines.append(f"（{record.note}）")
    for entry in record.entries:
        currency = entry.get("currency") or "?"
        symbol = CURRENCY_SYMBOLS.get(currency, "")
        labels = entry.get("labels") or {}
        total = entry.get("total")
        granted = entry.get("granted")
        topped = entry.get("topped")
        if total is not None:
            total_label = labels.get("total") or "总余额"
            lines.append(f"[{currency}] {total_label}：{symbol}{total}")
        if granted is not None:
            granted_label = labels.get("granted") or "赠金余额"
            lines.append(f"{granted_label}：{symbol}{granted}")
        if topped is not None:
            topped_label = labels.get("topped") or "充值余额"
            lines.append(f"{topped_label}：{symbol}{topped}")
    return lines
