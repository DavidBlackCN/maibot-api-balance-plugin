"""平台 Provider 实现 — maibot-api-balance-plugin

提供各 LLM 平台的余额查询能力。
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from .constants import (
    DEEPSEEK_BALANCE_PATH,
    DEEPSEEK_DEFAULT_BASE_URL,
    NEWAPI_DEFAULT_BASE_URL,
    NEWAPI_USER_SELF_PATH,
    PLUGIN_VERSION,
    SILICONFLOW_DEFAULT_BASE_URL,
    SILICONFLOW_USER_INFO_PATH,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# 自定义异常
# ═══════════════════════════════════════════════════════════════════════


class _BalanceRequestError(RuntimeError):
    """网络层异常（连接失败、超时、JSON 解析失败等）。"""


class _BalanceHTTPError(RuntimeError):
    """HTTP 非 2xx 异常，携带状态码与可读详情。"""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"HTTP {status}: {detail}")
        self.status = status
        self.detail = detail


class _BalanceBusinessError(RuntimeError):
    """业务层异常（接口返回 2xx 但 body 表示失败）。"""


# ═══════════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════════


class _BalanceRecord:
    """单个平台余额的结构化结果，供文本/HTML 两种输出复用。

    一个 record 可能携带多条 entries（如 DeepSeek 同时返回 CNY/USD）。
    """

    def __init__(
        self,
        display_name: str,
        status: Optional[str] = None,
        status_ok: bool = True,
        entries: Optional[List[Dict[str, Optional[str]]]] = None,
        note: Optional[str] = None,
    ) -> None:
        self.display_name = display_name
        self.status = status  # 已格式化的状态描述
        self.status_ok = status_ok
        self.entries = entries or []  # [{currency, total, granted, topped}]
        self.note = note  # 额外说明（如解析失败、空响应）


# ═══════════════════════════════════════════════════════════════════════
# 抽象基类
# ═══════════════════════════════════════════════════════════════════════


class _BalanceProvider:
    """单个 LLM 平台余额查询的抽象基类。

    子类需要：
      - 设置 display_name
      - 覆盖 default_base_url（属性）
      - 设置 path 或覆盖 _build_url
      - 实现 to_record(payload) 返回结构化 _BalanceRecord
    """

    display_name: str = ""
    path: str = ""
    user_agent: str = f"MaiBot-APIBalance/{PLUGIN_VERSION}"

    def __init__(self, api_key: str, base_url: str, timeout: int) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") or self.default_base_url
        self.timeout = timeout

    @property
    def default_base_url(self) -> str:
        raise NotImplementedError

    def _build_url(self) -> str:
        return self.base_url + self.path

    def fetch_sync(self) -> Dict[str, Any]:
        url = self._build_url()
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", self.user_agent)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise _BalanceHTTPError(exc.code, self._extract_http_error_detail(exc))
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise _BalanceRequestError(f"请求超时：{exc.reason}")
            raise _BalanceRequestError(str(exc.reason or exc))

        try:
            return json.loads(body)
        except ValueError as exc:
            raise _BalanceRequestError(f"响应不是合法 JSON：{exc}")

    @staticmethod
    def _extract_http_error_detail(exc: urllib.error.HTTPError) -> str:
        try:
            raw = exc.read().decode("utf-8", errors="replace")
        except OSError:
            return str(exc.reason or "未知错误")[:200]
        if not raw:
            return str(exc.reason or "未知错误")[:200]
        try:
            parsed = json.loads(raw)
        except ValueError:
            return raw[:200]
        if isinstance(parsed, dict):
            err = parsed.get("error")
            if isinstance(err, dict):
                msg = str(err.get("message") or "")
                if msg:
                    return msg[:200]
            msg = str(parsed.get("message") or "")
            if msg:
                return msg[:200]
        return raw[:200]

    def to_record(self, payload: Dict[str, Any]) -> _BalanceRecord:
        """把原始响应转换为结构化 _BalanceRecord，由子类实现。"""
        raise NotImplementedError

    @staticmethod
    def _format_amount(value: Any) -> Optional[str]:
        if value is None:
            return None
        try:
            return f"{float(value):.2f}"
        except (TypeError, ValueError):
            return str(value)


# ═══════════════════════════════════════════════════════════════════════
# DeepSeek Provider
# ═══════════════════════════════════════════════════════════════════════


class _DeepSeekProvider(_BalanceProvider):
    display_name = "DeepSeek"
    path = DEEPSEEK_BALANCE_PATH

    @property
    def default_base_url(self) -> str:
        return DEEPSEEK_DEFAULT_BASE_URL

    def to_record(self, payload: Dict[str, Any]) -> _BalanceRecord:
        is_available = bool(payload.get("is_available", False))
        infos = payload.get("balance_infos") or []
        if not isinstance(infos, list):
            infos = []

        record = _BalanceRecord(
            display_name=self.display_name,
            status="正常" if is_available else "不可用（余额不足或被限制）",
            status_ok=is_available,
        )
        for info in infos:
            if not isinstance(info, dict):
                continue
            currency = str(info.get("currency") or "?").upper()
            record.entries.append(
                {
                    "currency": currency,
                    "total": self._format_amount(info.get("total_balance")),
                    "granted": self._format_amount(info.get("granted_balance")),
                    "topped": self._format_amount(info.get("topped_up_balance")),
                }
            )
        if not record.entries:
            record.note = "未返回任何币种余额信息"
        return record


# ═══════════════════════════════════════════════════════════════════════
# SiliconFlow Provider
# ═══════════════════════════════════════════════════════════════════════


class _SiliconFlowProvider(_BalanceProvider):
    display_name = "硅基流动"
    path = SILICONFLOW_USER_INFO_PATH

    @property
    def default_base_url(self) -> str:
        return SILICONFLOW_DEFAULT_BASE_URL

    def fetch_sync(self) -> Dict[str, Any]:
        payload = super().fetch_sync()
        # SiliconFlow 即使 HTTP 200 也可能在 body 里返回业务失败
        if isinstance(payload, dict) and payload.get("status") is False:
            msg = str(payload.get("message") or "硅基流动返回业务失败")
            raise _BalanceBusinessError(msg)
        return payload

    def to_record(self, payload: Dict[str, Any]) -> _BalanceRecord:
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return _BalanceRecord(
                self.display_name,
                note="响应缺少 data 字段，无法解析",
                status_ok=False,
            )
        status = str(data.get("status") or "").lower()
        return _BalanceRecord(
            display_name=self.display_name,
            status="正常" if status == "normal" else (status or "未知"),
            status_ok=(status == "normal"),
            note="数据来自官方 API，与控制台显示口径可能略有差异",
            entries=[
                {
                    "currency": "CNY",
                    "total": self._format_amount(data.get("totalBalance")),
                    # SiliconFlow API 字段命名：balance 实际是代金券/赠金，
                    # chargeBalance 才是真正的充值余额。
                    "granted": self._format_amount(data.get("balance")),
                    "topped": self._format_amount(data.get("chargeBalance")),
                    "labels": {"granted": "代金券", "topped": "余额"},
                }
            ],
        )


# ═══════════════════════════════════════════════════════════════════════
# NewAPI Provider
# ═══════════════════════════════════════════════════════════════════════


class _NewAPIProvider(_BalanceProvider):
    """NewAPI 站点余额查询。

    使用系统访问令牌 + 用户 ID 鉴权，调用 /api/user/self 端点。
    注意：使用的是「系统访问令牌」（access_token），而非 sk- 开头的 API Key。
    请求头：
      - Authorization: Bearer {access_token}
      - New-API-User: {user_id}
    """

    display_name = "NewAPI"
    path = NEWAPI_USER_SELF_PATH

    def __init__(
        self, api_key: str, base_url: str, timeout: int, user_id: str = ""
    ) -> None:
        super().__init__(api_key, base_url, timeout)
        self.user_id = user_id

    @property
    def default_base_url(self) -> str:
        return NEWAPI_DEFAULT_BASE_URL

    def fetch_sync(self) -> Dict[str, Any]:
        # 重写以添加 New-API-User 请求头
        url = self._build_url()
        req = urllib.request.Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", self.user_agent)
        if self.user_id:
            req.add_header("New-API-User", self.user_id)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise _BalanceHTTPError(exc.code, self._extract_http_error_detail(exc))
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise _BalanceRequestError(f"请求超时：{exc.reason}")
            raise _BalanceRequestError(str(exc.reason or exc))

        try:
            payload = json.loads(body)
        except ValueError as exc:
            raise _BalanceRequestError(f"响应不是合法 JSON：{exc}")

        # NewAPI 即使 HTTP 200，也可能返回 success: false
        if isinstance(payload, dict) and payload.get("success") is False:
            msg = str(payload.get("message") or "NewAPI 返回业务失败")
            raise _BalanceBusinessError(msg)
        return payload

    def to_record(self, payload: Dict[str, Any]) -> _BalanceRecord:
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict):
            return _BalanceRecord(
                self.display_name,
                note="响应缺少 data 字段，无法解析",
                status_ok=False,
            )

        quota = data.get("quota")
        used_quota = data.get("used_quota")
        request_count = data.get("request_count")

        if quota is None and used_quota is None:
            return _BalanceRecord(
                self.display_name,
                status="未知",
                status_ok=False,
                note="响应中未包含余额字段（quota/used_quota），请确认 API Key 是否正确",
            )

        # NewAPI 内部以点数计价：500,000 点 = $1 USD
        CONVERSION = 500000

        quota_usd = None
        used_usd = None
        if quota is not None:
            try:
                quota_usd = float(quota) / CONVERSION
            except (TypeError, ValueError):
                pass
        if used_quota is not None:
            try:
                used_usd = float(used_quota) / CONVERSION
            except (TypeError, ValueError):
                pass

        record = _BalanceRecord(
            display_name=self.display_name,
            status="正常",
            status_ok=True,
            entries=[
                {
                    "currency": "USD",
                    "total": self._format_amount(quota_usd),
                    "topped": self._format_amount(used_usd),
                    "labels": {"total": "剩余 ($)", "topped": "已用 ($)"},
                }
            ],
        )

        if request_count is not None:
            record.note = f"累计请求 {request_count} 次"

        return record
