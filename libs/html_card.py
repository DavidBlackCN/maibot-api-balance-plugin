"""HTML 卡片渲染 — maibot-api-balance-plugin

将各平台的余额查询结果渲染为一张漂亮的 HTML 卡片，供 render.html2png 截图。
"""

import html
from typing import Any, List, Sequence, Tuple

from .constants import CURRENCY_SYMBOLS, PLUGIN_VERSION
from .providers import _BalanceProvider, _BalanceRecord


def render_html_card(
    records: Sequence[Tuple[_BalanceProvider, Any]],
) -> str:
    """把所有平台的结果渲染为单张 HTML 卡片。"""
    sections: List[str] = []
    for provider, item in records:
        sections.append(_render_provider_section(provider, item))

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
  background: linear-gradient(135deg, #f6f7fb 0%, #e9edf7 100%);
  padding: 24px;
  color: #1f2937;
}}
#card {{
  width: 672px;
  background: #ffffff;
  border-radius: 16px;
  padding: 24px 28px;
  box-shadow: 0 16px 48px -16px rgba(20, 30, 60, 0.18);
}}
.card-title {{
  font-size: 22px;
  font-weight: 600;
  margin: 0 0 4px 0;
  letter-spacing: 0.5px;
}}
.card-subtitle {{
  font-size: 13px;
  color: #6b7280;
  margin: 0 0 18px 0;
}}
.provider {{
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px 16px 12px 16px;
  margin-bottom: 12px;
  background: #fafbff;
}}
.provider:last-child {{ margin-bottom: 0; }}
.provider-head {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}}
.provider-name {{
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}}
.status-pill {{
  font-size: 12px;
  padding: 2px 10px;
  border-radius: 999px;
  font-weight: 500;
}}
.status-ok    {{ background: #dcfce7; color: #166534; }}
.status-warn  {{ background: #fee2e2; color: #991b1b; }}
.status-info  {{ background: #e0e7ff; color: #3730a3; }}
.entry {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  padding: 8px 0 0 0;
  border-top: 1px dashed #e5e7eb;
  margin-top: 8px;
}}
.entry:first-of-type {{ border-top: 0; margin-top: 0; padding-top: 0; }}
.entry-cell .label {{
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 2px;
}}
.entry-cell .value {{
  font-size: 16px;
  font-weight: 600;
  color: #111827;
  font-variant-numeric: tabular-nums;
}}
.entry-cell .value.total {{ color: #2563eb; }}
.entry-currency {{
  font-size: 11px;
  color: #6b7280;
  margin-bottom: 6px;
  letter-spacing: 0.5px;
}}
.error-text {{
  color: #991b1b;
  font-size: 13px;
  padding: 4px 0;
}}
.note-text {{
  color: #6b7280;
  font-size: 12px;
  padding: 2px 0 6px 0;
}}
.footer {{
  text-align: right;
  font-size: 11px;
  color: #9ca3af;
  margin-top: 16px;
}}
</style></head>
<body>
<div id="card">
  <h1 class="card-title">💰 API 平台余额</h1>
  <p class="card-subtitle">共 {len(records)} 个平台</p>
  {''.join(sections)}
  <div class="footer">MaiBot · API Balance Plugin v{PLUGIN_VERSION}</div>
</div>
</body></html>"""


def _render_provider_section(
    provider: _BalanceProvider, item: Any
) -> str:
    """渲染单个平台的 HTML 卡片区块。"""
    from .providers import _BalanceHTTPError, _BalanceBusinessError, _BalanceRequestError

    name_esc = html.escape(provider.display_name)

    # --- 错误处理 ---
    if isinstance(item, _BalanceHTTPError):
        if item.status in (401, 403):
            err_text = "❌ API Key 无效或权限不足"
        else:
            err_text = f"❌ HTTP {item.status}：{html.escape(item.detail)}"
        return (
            f'<div class="provider">'
            f'  <div class="provider-head">'
            f'    <span class="provider-name">{name_esc}</span>'
            f'    <span class="status-pill status-warn">错误</span>'
            f'  </div>'
            f'  <div class="error-text">{err_text}</div>'
            f'</div>'
        )

    if isinstance(item, _BalanceBusinessError):
        return (
            f'<div class="provider">'
            f'  <div class="provider-head">'
            f'    <span class="provider-name">{name_esc}</span>'
            f'    <span class="status-pill status-warn">业务失败</span>'
            f'  </div>'
            f'  <div class="error-text">❌ 业务失败：{html.escape(str(item))}</div>'
            f'</div>'
        )

    if isinstance(item, _BalanceRequestError):
        return (
            f'<div class="provider">'
            f'  <div class="provider-head">'
            f'    <span class="provider-name">{name_esc}</span>'
            f'    <span class="status-pill status-warn">网络错误</span>'
            f'  </div>'
            f'  <div class="error-text">❌ 网络错误：{html.escape(str(item))}</div>'
            f'</div>'
        )

    if isinstance(item, Exception):
        return (
            f'<div class="provider">'
            f'  <div class="provider-head">'
            f'    <span class="provider-name">{name_esc}</span>'
            f'    <span class="status-pill status-warn">错误</span>'
            f'  </div>'
            f'  <div class="error-text">❌ 内部错误（详见日志）</div>'
            f'</div>'
        )

    # --- 正常记录 ---
    assert isinstance(item, _BalanceRecord)
    pill_cls = "status-ok" if item.status_ok else "status-warn"
    pill_text = html.escape(
        item.status or ("正常" if item.status_ok else "异常")
    )
    note_html = (
        f'<div class="note-text">{html.escape(item.note)}</div>'
        if item.note
        else ""
    )

    entry_blocks: List[str] = []
    for entry in item.entries:
        currency = (entry.get("currency") or "?").upper()
        symbol = CURRENCY_SYMBOLS.get(currency, "")
        labels = entry.get("labels") or {}
        cells: List[str] = []
        for default_label, key, klass in (
            ("总余额", "total", "value total"),
            ("赠金", "granted", "value"),
            ("充值", "topped", "value"),
        ):
            v = entry.get(key)
            if v is None:
                continue
            label = labels.get(key) or default_label
            cells.append(
                f'<div class="entry-cell">'
                f'  <div class="label">{html.escape(label)}</div>'
                f'  <div class="{klass}">{html.escape(symbol + str(v))}</div>'
                f'</div>'
            )
        if not cells:
            continue
        entry_blocks.append(
            f'<div class="entry-currency">{html.escape(currency)}</div>'
            f'<div class="entry">{"".join(cells)}</div>'
        )

    entries_html = "".join(entry_blocks) or (
        '<div class="note-text">无可展示的余额条目</div>'
    )

    return (
        f'<div class="provider">'
        f'  <div class="provider-head">'
        f'    <span class="provider-name">{name_esc}</span>'
        f'    <span class="status-pill {pill_cls}">{pill_text}</span>'
        f'  </div>'
        f'  {note_html}'
        f'  {entries_html}'
        f'</div>'
    )
