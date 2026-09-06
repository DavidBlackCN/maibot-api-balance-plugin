"""MaiBot API 余额查询插件 — 入口文件

通过聊天命令 /余额 并行查询多个 API 平台的账号余额，统一汇总输出
（文本或 HTML 图片卡片）。支持在线命令管理平台配置、自动重载和每日群播报。

装饰器：优先使用 @Command（斜杠命令）
配置：PluginConfigBase + Field，用户可见文本全部简体中文
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

# 确保插件目录在 sys.path 中，以便子模块（libs/）可被导入
_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

from maibot_sdk import Command, MaiBotPlugin

from libs.config import LLMBalanceConfig
from libs.constants import (
    OUTPUT_FORMAT_BOTH,
    OUTPUT_FORMAT_IMAGE,
    OUTPUT_FORMAT_TEXT,
    OUTPUT_FORMATS,
    PLATFORM_TYPES,
    KNOWN_PLATFORM_TYPES,
    PLUGIN_VERSION,
)
from libs.html_card import render_html_card, render_platform_list_card
from libs.providers import (
    _BalanceProvider,
    _DeepSeekProvider,
    _MiniMaxProvider,
    _MoonshotProvider,
    _NewAPIProvider,
    _OneThingProvider,
    _OpenAIProvider,
    _OpenRouterProvider,
    _SiliconFlowProvider,
    _VolcEngineProvider,
    _BalanceRecord,
)
from libs.text_report import format_text_report

logger = logging.getLogger(__name__)

# 平台 type → Provider 类映射
_PROVIDER_MAP = {
    "deepseek": _DeepSeekProvider,
    "siliconflow": _SiliconFlowProvider,
    "newapi": _NewAPIProvider,
    "openrouter": _OpenRouterProvider,
    "moonshot": _MoonshotProvider,
    "openai": _OpenAIProvider,
    "onething": _OneThingProvider,
    "minimax": _MiniMaxProvider,
    "volcengine": _VolcEngineProvider,
}

# 平台 type → 中文显示名
_PLATFORM_DISPLAY_NAMES = {
    "deepseek": "DeepSeek",
    "siliconflow": "硅基流动",
    "newapi": "NewAPI",
    "openrouter": "OpenRouter",
    "moonshot": "月之暗面",
    "openai": "OpenAI",
    "onething": "OneThing",
    "minimax": "MiniMax",
    "volcengine": "火山方舟",
}

_CHINA_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
_BROADCAST_STATE_PATH = _PLUGIN_DIR / ".broadcast_state.json"

# ═══════════════════════════════════════════════════════════════════════
# TOML 读写工具（用于在线管理命令写回 config.toml）
# ═══════════════════════════════════════════════════════════════════════

def _read_config_toml() -> Dict[str, Any]:
    """读取本插件目录下的 config.toml 为 dict。"""
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib
        except ImportError:
            raise RuntimeError(
                "需要 tomli 库来读取 config.toml。"
                "请执行: pip install tomli"
            )

    config_path = Path(__file__).parent / "config.toml"
    if not config_path.exists():
        return {}
    return tomllib.loads(config_path.read_text(encoding="utf-8"))


def _write_config_toml(data: Dict[str, Any]) -> None:
    """将 dict 写回本插件目录下的 config.toml。"""
    config_path = Path(__file__).parent / "config.toml"

    # 尝试使用 tomli_w
    try:
        import tomli_w

        config_path.write_text(tomli_w.dumps(data), encoding="utf-8")
        return
    except ImportError:
        pass

    # 尝试使用 toml 库
    try:
        import toml

        config_path.write_text(toml.dumps(data), encoding="utf-8")
        return
    except ImportError:
        pass

    # 回退：手动序列化（支持常见结构）
    config_path.write_text(_simple_toml_dumps(data), encoding="utf-8")


def _simple_toml_dumps(data: Dict[str, Any], prefix: str = "") -> str:
    """简易 TOML 序列化器，支持 dict / list[dict] / 标量。"""
    lines: List[str] = []
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            lines.append(f"\n[{full_key}]")
            for k, v in value.items():
                lines.append(f"{k} = {_toml_value(v)}")
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # 数组表（如 [[newapi_instances]]）
            for item in value:
                lines.append(f"\n[[{full_key}]]")
                for k, v in item.items():
                    lines.append(f"{k} = {_toml_value(v)}")
        elif isinstance(value, list):
            lines.append(f"{key} = {_toml_value(value)}")
        else:
            lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines).strip() + "\n"


def _toml_value(v: Any) -> str:
    """将 Python 值转为 TOML 字面量。"""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        items = ", ".join(_toml_value(i) for i in v)
        return f"[{items}]"
    if isinstance(v, str):
        # 简单转义
        escaped = v.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return f'"{v}"'


# ═══════════════════════════════════════════════════════════════════════
# 主插件类
# ═══════════════════════════════════════════════════════════════════════


class APIBalancePlugin(MaiBotPlugin):
    """API 平台余额查询插件。

    通过 /余额 命令并行查询多个平台并汇总输出。
    """

    config_model = LLMBalanceConfig

    def __init__(self) -> None:
        super().__init__()
        self._admin_set: set[str] = set()
        self._broadcast_task: Optional[asyncio.Task] = None

    # ── 生命周期 ──────────────────────────────────────────────────────

    async def on_load(self) -> None:
        self._refresh_admin_cache()
        self._start_broadcast_task()
        logger.info(
            "API 余额查询插件(v%s) 初始化完成。", PLUGIN_VERSION
        )

    async def on_unload(self) -> None:
        await self._stop_broadcast_task()
        logger.info("API 余额查询插件已卸载。")

    async def on_config_update(
        self, scope: str, config_data: dict, version: str
    ) -> None:
        if scope == "self":
            self._refresh_admin_cache()
            await self._stop_broadcast_task()
            self._start_broadcast_task()
            logger.info("API 余额查询插件配置已更新: version=%s", version)

    # ── 内部辅助 ──────────────────────────────────────────────────────

    def _refresh_admin_cache(self) -> None:
        self._admin_set = {
            str(uid) for uid in self.config.settings.admin_user_ids
        }

    def _check_admin(self, user_id: str) -> bool:
        return str(user_id) in self._admin_set

    def _collect_providers(self) -> List[_BalanceProvider]:
        """根据当前配置构造所有启用的 Provider 实例。"""
        settings = self.config.settings
        result: List[_BalanceProvider] = []

        for inst in self.config.api_instances:
            if not inst.enabled:
                continue
            ptype = inst.type.strip().lower()
            if ptype == "siliconflow":
                logger.info("硅基流动接口暂不可用，跳过实例「%s」", inst.label or "(未命名)")
                continue
            if ptype not in _PROVIDER_MAP:
                logger.warning("未知平台类型「%s」，已跳过", ptype)
                continue

            if ptype == "volcengine":
                access_key_id = inst.access_key_id.strip()
                secret_access_key = inst.secret_access_key.strip()
                if not access_key_id or not secret_access_key:
                    logger.warning("火山方舟「%s」缺少 AK/SK，已跳过", inst.label or "(未命名)")
                    continue
                provider = _VolcEngineProvider(
                    access_key_id=access_key_id,
                    secret_access_key=secret_access_key,
                    base_url=inst.base_url.strip(),
                    timeout=settings.timeout,
                )
                label = inst.label.strip()
                if label:
                    provider.display_name = f"火山方舟 ({label})"
                result.append(provider)
                continue

            api_key = inst.api_key.strip()
            if not api_key:
                plat_name = _PLATFORM_DISPLAY_NAMES.get(ptype, ptype)
                logger.warning(
                    "%s「%s」已启用但 api_key 为空，已跳过",
                    plat_name, inst.label or "(未命名)",
                )
                continue

            base_url = inst.base_url.strip()
            provider_cls = _PROVIDER_MAP[ptype]

            # NewAPI 特殊处理：需要 user_id
            if ptype == "newapi":
                user_id = inst.user_id.strip()
                if not user_id:
                    logger.warning(
                        "NewAPI「%s」已启用但 user_id 为空，已跳过",
                        inst.label or "(未命名)",
                    )
                    continue
                provider = provider_cls(
                    api_key=api_key,
                    base_url=base_url,
                    timeout=settings.timeout,
                    user_id=user_id,
                )
            else:
                provider = provider_cls(
                    api_key=api_key,
                    base_url=base_url,
                    timeout=settings.timeout,
                )

            # 使用 label 作为展示名
            label = inst.label.strip()
            if label:
                provider.display_name = (
                    f"{_PLATFORM_DISPLAY_NAMES.get(ptype, ptype)} ({label})"
                )
            result.append(provider)

        return result

    async def _query_records(self, providers: Sequence[_BalanceProvider]) -> List[Tuple[_BalanceProvider, Any]]:
        """并行查询 Provider，并统一转换为展示记录。"""
        async def _run(provider: _BalanceProvider) -> Tuple[_BalanceProvider, Any]:
            try:
                return provider, await asyncio.to_thread(provider.fetch_sync)
            except Exception as exc:
                return provider, exc

        results = await asyncio.gather(*[_run(p) for p in providers])
        records: List[Tuple[_BalanceProvider, Any]] = []
        for provider, item in results:
            if isinstance(item, Exception):
                records.append((provider, item))
                continue
            try:
                records.append((provider, provider.to_record(item)))
            except Exception as exc:
                logger.error("%s 解析响应失败: %s", provider.display_name, exc, exc_info=True)
                records.append((provider, exc))
        return records

    @staticmethod
    def _parse_broadcast_time(value: str) -> Optional[Tuple[int, int]]:
        match = re.fullmatch(r"(\d{2}):(\d{2})", (value or "").strip())
        if not match:
            return None
        hour, minute = int(match.group(1)), int(match.group(2))
        return (hour, minute) if hour < 24 and minute < 60 else None

    def _broadcast_groups(self) -> List[str]:
        return list(dict.fromkeys(
            str(value).strip() for value in self.config.broadcast.group_ids if str(value).strip()
        ))

    def _start_broadcast_task(self) -> None:
        broadcast = self.config.broadcast
        if not broadcast.enabled:
            return
        if not self._broadcast_groups():
            logger.warning("定时播报已启用，但群聊列表为空")
            return
        if self._parse_broadcast_time(broadcast.time) is None:
            logger.error("定时播报时间无效：%r（应为 HH:MM）", broadcast.time)
            return
        self._broadcast_task = asyncio.create_task(self._broadcast_loop(), name="api-balance-broadcast")

    async def _stop_broadcast_task(self) -> None:
        task, self._broadcast_task = self._broadcast_task, None
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def _load_broadcast_state(self) -> Dict[str, str]:
        try:
            data = json.loads(_BROADCAST_STATE_PATH.read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
        except FileNotFoundError:
            return {}
        except Exception as exc:
            logger.warning("读取定时播报状态失败，将按无记录处理: %s", exc)
            return {}

    def _save_broadcast_state(self, state: Dict[str, str]) -> None:
        try:
            _BROADCAST_STATE_PATH.write_text(
                json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.error("保存定时播报状态失败: %s", exc, exc_info=True)

    async def _broadcast_loop(self) -> None:
        while True:
            try:
                await self._run_scheduled_broadcast(datetime.now(_CHINA_TZ))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("定时播报任务执行失败: %s", exc, exc_info=True)
            now = datetime.now(_CHINA_TZ)
            await asyncio.sleep(max(1.0, 60.0 - now.second - now.microsecond / 1_000_000))

    async def _run_scheduled_broadcast(self, now: datetime) -> bool:
        if not self.config.broadcast.enabled:
            return False
        target = self._parse_broadcast_time(self.config.broadcast.time)
        if target is None or (now.hour, now.minute) != target:
            return False
        date_key = now.date().isoformat()
        state = self._load_broadcast_state()
        pending = [group for group in self._broadcast_groups() if state.get(group) != date_key]
        if not pending:
            return False
        for group in pending:
            state[group] = date_key
        self._save_broadcast_state(state)

        providers = self._collect_providers()
        records = await self._query_records(providers) if providers else []
        text_report = format_text_report(records) if providers else "💰 API 平台余额\n———\n暂无可查询的平台"
        success = sum(isinstance(item, _BalanceRecord) and item.status_ok for _, item in records)
        failed = len(records) - success
        header = (self.config.broadcast.header or "每日 API 平台余额播报").strip()
        heading = f"{header}\n北京时间：{now:%Y-%m-%d %H:%M}\n查询结果：成功 {success}，失败 {failed}"
        nodes = [{"user_id": "0", "nickname": "余额播报", "segments": [{"type": "text", "content": heading}]}]
        fmt = self._output_format()
        image_b64 = (
            await self._render_records_image(records, now)
            if providers and fmt in (OUTPUT_FORMAT_IMAGE, OUTPUT_FORMAT_BOTH)
            else None
        )
        if image_b64 and fmt in (OUTPUT_FORMAT_IMAGE, OUTPUT_FORMAT_BOTH):
            nodes.append({"user_id": "0", "nickname": "余额播报", "segments": [{"type": "image", "content": image_b64}]})
        if fmt in (OUTPUT_FORMAT_TEXT, OUTPUT_FORMAT_BOTH) or not image_b64:
            nodes.append({"user_id": "0", "nickname": "余额播报", "segments": [{"type": "text", "content": text_report}]})
        for group in pending:
            await self._send_broadcast_to_group(group, nodes)
        return True

    def _output_format(self) -> str:
        fmt = (self.config.settings.output_format or OUTPUT_FORMAT_TEXT).lower()
        return fmt if fmt in OUTPUT_FORMATS else OUTPUT_FORMAT_TEXT

    async def _render_records_image(self, records, queried_at: Optional[datetime] = None) -> Optional[str]:
        try:
            rendered = await self.ctx.render.html2png(
                render_html_card(records, queried_at=queried_at), selector="#card",
                viewport={"width": 720, "height": 480}, device_scale_factor=2.0,
            )
            return (rendered or {}).get("image_base64")
        except Exception as exc:
            logger.warning("余额卡片渲染失败，回退文本: %s", exc)
            return None

    async def _send_broadcast_to_group(self, group_id: str, nodes: List[Dict[str, Any]]) -> None:
        try:
            try:
                stream = await self.ctx.chat.get_stream_by_group_id(group_id, platform="qq")
            except TypeError:
                stream = await self.ctx.chat.get_stream_by_group_id(group_id)
            if not stream:
                logger.warning("未找到群聊 %s 的聊天流，跳过播报", group_id)
                return
            stream_id = self._extract_stream_id(stream)
            if not stream_id:
                logger.warning("群聊 %s 的聊天流缺少 stream_id", group_id)
                return
            sent = await self.ctx.send.forward(nodes, stream_id)
            if sent is False:
                logger.error("向群聊 %s 发送合并播报失败：send.forward 返回 False", group_id)
        except Exception as exc:
            logger.error("向群聊 %s 发送定时播报失败: %s", group_id, exc, exc_info=True)

    @staticmethod
    def _extract_stream_id(stream: Any) -> str:
        if isinstance(stream, (str, int)):
            return str(stream).strip()
        if isinstance(stream, dict):
            direct = stream.get("stream_id") or stream.get("session_id")
            if direct:
                return str(direct).strip()
            nested = stream.get("stream")
            if isinstance(nested, dict):
                return str(nested.get("stream_id") or nested.get("session_id") or "").strip()
        return str(getattr(stream, "stream_id", None) or getattr(stream, "session_id", None) or "").strip()

    # ── 命令：查询余额 ────────────────────────────────────────────────

    @Command(
        "api_balance_query",
        description="查询所有已启用 API 平台的账号余额。格式：/余额",
        pattern=r"^\/余额$",
    )
    async def handle_balance(
        self,
        stream_id: str = "",
        group_id: str = "",
        user_id: str = "",
        text: str = "",
        plugin_config: Optional[dict] = None,
        **kwargs,
    ):
        """查询余额：/余额"""
        if self.config.settings.admin_only and not self._check_admin(user_id):
            await self.ctx.send.text(
                "❌ 你没有权限查询 API 平台余额", stream_id
            )
            return False, f"用户 {user_id} 无权限", 1

        providers = self._collect_providers()
        if not providers:
            await self.ctx.send.text(
                "❌ 未启用任何可查询平台。请启用至少一个平台并配置有效访问凭证。",
                stream_id,
            )
            return False, "无可用平台", 1

        await self.ctx.send.text(
            f"⏳ 正在并行查询 {len(providers)} 个平台…", stream_id,
        )

        records = await self._query_records(providers)
        fmt = self._output_format()
        image_b64 = None
        if fmt in (OUTPUT_FORMAT_IMAGE, OUTPUT_FORMAT_BOTH):
            image_b64 = await self._render_records_image(records, datetime.now(_CHINA_TZ))
            if image_b64:
                try:
                    await self.ctx.send.image(image_b64, stream_id)
                except Exception as exc:
                    logger.error("图片发送失败，回退文本模式: %s", exc, exc_info=True)
                    image_b64 = None
        if fmt in (OUTPUT_FORMAT_TEXT, OUTPUT_FORMAT_BOTH) or not image_b64:
            await self.ctx.send.text(format_text_report(records), stream_id)

        return True, "余额查询完成", 1

    # ── 命令：添加平台 ────────────────────────────────────────────────

    @Command(
        "api_balance_add_platform",
        description="在线添加 API 平台配置并写入 config.toml。格式：/添加平台 <类型> <参数…>",
        pattern=r"^\/添加平台\s+(\S+)\s+(.+)$",
    )
    async def handle_add_platform(
        self,
        stream_id: str = "",
        user_id: str = "",
        text: str = "",
        **kwargs,
    ):
        """添加平台：/添加平台 <类型> <API Key/实例名> [参数…]

        - /添加平台 <类型> <API Key> [备注名] [URL]
        - /添加平台 newapi <API Key> <用户ID> [备注名] [URL]
        """
        if self.config.settings.admin_only and not self._check_admin(user_id):
            await self.ctx.send.text(
                "❌ 你没有权限管理平台配置", stream_id
            )
            return False, f"用户 {user_id} 无权限", 1

        match = re.match(
            r"^\/添加平台\s+(\S+)\s+(.+)$", text.strip()
        )
        if not match:
            await self.ctx.send.text(
                "❌ 格式错误。\n"
                "用法：\n"
                "/添加平台 <类型> <API Key> [备注名] [URL]\n"
                f"类型：{' / '.join(PLATFORM_TYPES)}\n"
                "NewAPI：/添加平台 newapi <令牌> <用户ID> [备注名] [URL]\n"
                "火山方舟：/添加平台 volcengine <AK> <SK> [备注名]",
                stream_id,
            )
            return False, "格式错误", 1

        platform_type = match.group(1).lower()
        rest = match.group(2).strip()

        if platform_type not in PLATFORM_TYPES:
            await self.ctx.send.text(
                f"❌ 不支持的平台类型「{platform_type}」。"
                f"支持：{', '.join(PLATFORM_TYPES)}",
                stream_id,
            )
            return False, "不支持的平台类型", 1

        try:
            data = _read_config_toml()
        except Exception as exc:
            logger.error("读取 config.toml 失败: %s", exc, exc_info=True)
            await self.ctx.send.text(
                "❌ 读取 config.toml 失败，请检查文件格式或日志", stream_id
            )
            return False, "读取配置失败", 1

        if platform_type == "newapi":
            # /添加平台 newapi <系统访问令牌> <用户ID> [备注名] [URL]
            parts = rest.split(maxsplit=3)
            if len(parts) < 2:
                await self.ctx.send.text(
                    "❌ NewAPI 格式：/添加平台 newapi <令牌> <用户ID> [备注名] [URL]\n"
                    "令牌在站点「个人设置」→「生成系统访问令牌」获取。",
                    stream_id,
                )
                return False, "参数不足", 1
            api_key = parts[0]
            user_id = parts[1]
            label = parts[2] if len(parts) > 2 else ""
            base_url = parts[3] if len(parts) > 3 else ""
            new_inst = {"type": "newapi", "enabled": True, "api_key": api_key, "user_id": user_id}
            if label:
                new_inst["label"] = label
            if base_url:
                new_inst["base_url"] = base_url
            await self.ctx.send.text(
                f"✅ 已添加 NewAPI（用户ID:{user_id}）" + (f"「{label}」" if label else ""),
                stream_id,
            )
        elif platform_type == "volcengine":
            parts = rest.split(maxsplit=2)
            if len(parts) < 2:
                await self.ctx.send.text(
                    "❌ 火山方舟格式：/添加平台 volcengine <Access Key ID> <Secret Access Key> [备注名]",
                    stream_id,
                )
                return False, "参数不足", 1
            access_key_id, secret_access_key = parts[0], parts[1]
            label = parts[2] if len(parts) > 2 else ""
            new_inst = {
                "type": "volcengine", "enabled": True,
                "access_key_id": access_key_id, "secret_access_key": secret_access_key,
            }
            if label:
                new_inst["label"] = label
            await self.ctx.send.text(
                "✅ 已添加火山方舟" + (f"「{label}」" if label else ""), stream_id
            )
        else:
            # 通用格式: /添加平台 <类型> <API Key> [备注名] [URL]
            parts = rest.split(maxsplit=2)
            api_key = parts[0]
            label = parts[1] if len(parts) > 1 else ""
            base_url = parts[2] if len(parts) > 2 else ""
            new_inst = {"type": platform_type, "enabled": True, "api_key": api_key}
            if label:
                new_inst["label"] = label
            if base_url:
                new_inst["base_url"] = base_url
            display_name = _PLATFORM_DISPLAY_NAMES.get(platform_type, platform_type)
            await self.ctx.send.text(
                f"✅ 已添加 {display_name}" + (f"「{label}」" if label else ""),
                stream_id,
            )

        # 添加到 api_instances 列表
        instances = data.get("api_instances", [])
        if not isinstance(instances, list):
            instances = []
        instances.append(new_inst)
        data["api_instances"] = instances

        # 确保基础 Section 存在
        data.setdefault("plugin", {}).setdefault("enabled", True)
        data.setdefault("settings", {})

        try:
            _write_config_toml(data)
        except Exception as exc:
            logger.error("写入 config.toml 失败: %s", exc, exc_info=True)
            await self.ctx.send.text(
                "❌ 写入 config.toml 失败，请检查日志", stream_id
            )
            return False, "写入配置失败", 1

        # 自动重载
        try:
            await self.ctx.component.reload_plugin(
                "maibot-api-balance-plugin"
            )
        except Exception as exc:
            logger.warning("自动重载插件失败: %s", exc)

        return True, "添加平台成功", 1

    # ── 命令：删除平台 ────────────────────────────────────────────────

    @Command(
        "api_balance_remove_platform",
        description="在线删除 API 平台配置。格式：/删除平台 <类型> [实例名]",
        pattern=r"^\/删除平台\s+(\S+)(?:\s+(.+))?$",
    )
    async def handle_remove_platform(
        self,
        stream_id: str = "",
        user_id: str = "",
        text: str = "",
        **kwargs,
    ):
        """删除平台：/删除平台 <类型> [NewAPI实例名]"""
        if self.config.settings.admin_only and not self._check_admin(user_id):
            await self.ctx.send.text(
                "❌ 你没有权限管理平台配置", stream_id
            )
            return False, f"用户 {user_id} 无权限", 1

        match = re.match(
            r"^\/删除平台\s+(\S+)(?:\s+(.+))?$", text.strip()
        )
        if not match:
            await self.ctx.send.text(
                "❌ 格式错误。\n"
                "用法：\n"
                "/删除平台 deepseek\n"
                "/删除平台 siliconflow\n"
                "/删除平台 newapi <实例名>",
                stream_id,
            )
            return False, "格式错误", 1

        platform_type = match.group(1).lower()
        instance_name = (match.group(2) or "").strip()

        if platform_type not in KNOWN_PLATFORM_TYPES:
            await self.ctx.send.text(
                f"❌ 不支持的平台类型「{platform_type}」。"
                f"支持删除：{', '.join(KNOWN_PLATFORM_TYPES)}",
                stream_id,
            )
            return False, "不支持的平台类型", 1

        try:
            data = _read_config_toml()
        except Exception as exc:
            logger.error("读取 config.toml 失败: %s", exc, exc_info=True)
            await self.ctx.send.text(
                "❌ 读取 config.toml 失败", stream_id
            )
            return False, "读取配置失败", 1

        instances = data.get("api_instances", [])
        if not isinstance(instances, list):
            instances = []

        removed = []
        new_instances = []
        for inst in instances:
            if isinstance(inst, dict) and inst.get("type") == platform_type:
                if instance_name:
                    if inst.get("label") == instance_name:
                        removed.append(inst)
                        continue
                else:
                    removed.append(inst)
                    continue
            new_instances.append(inst)

        if not removed:
            hint = f"「{instance_name}」" if instance_name else "所有实例"
            await self.ctx.send.text(
                f"❌ 未找到类型为「{platform_type}」的{hint}", stream_id
            )
            return False, "未找到匹配项", 1

        data["api_instances"] = new_instances
        display_name = _PLATFORM_DISPLAY_NAMES.get(platform_type, platform_type)
        await self.ctx.send.text(
            f"✅ 已删除 {len(removed)} 个 {display_name} 实例", stream_id
        )

        try:
            _write_config_toml(data)
        except Exception as exc:
            logger.error("写入 config.toml 失败: %s", exc, exc_info=True)
            await self.ctx.send.text(
                "❌ 写入 config.toml 失败", stream_id
            )
            return False, "写入配置失败", 1

        # 自动重载
        try:
            await self.ctx.component.reload_plugin(
                "maibot-api-balance-plugin"
            )
        except Exception as exc:
            logger.warning("自动重载插件失败: %s", exc)

        return True, "删除平台成功", 1

    # ── 命令：平台列表 ────────────────────────────────────────────────

    @Command(
        "api_balance_list_platforms",
        description="列出当前所有已配置的 API 平台及状态",
        pattern=r"^\/平台列表$",
    )
    async def handle_list_platforms(
        self,
        stream_id: str = "",
        user_id: str = "",
        **kwargs,
    ):
        """列出平台：/平台列表"""
        if self.config.settings.admin_only and not self._check_admin(user_id):
            await self.ctx.send.text(
                "❌ 你没有权限查看平台配置", stream_id
            )
            return False, f"用户 {user_id} 无权限", 1

        instances = self.config.api_instances
        fmt = (self.config.settings.output_format or OUTPUT_FORMAT_TEXT).lower()

        # 构建文本行
        lines: List[str] = ["📋 已配置的 API 平台"]
        if instances:
            for i, inst in enumerate(instances, 1):
                ptype = inst.type or "未知"
                plat_name = _PLATFORM_DISPLAY_NAMES.get(ptype, ptype)
                status = "✅" if inst.enabled else "⭕"
                label = f"「{inst.label}」" if inst.label else ""
                if ptype == "volcengine":
                    key_ok = "AK/SK 已配置" if inst.access_key_id.strip() and inst.secret_access_key.strip() else "⚠️ AK/SK 不完整"
                else:
                    key_ok = "已配置" if inst.api_key.strip() else "⚠️ 未配置 Key"
                url = inst.base_url or "(默认)"
                extra = ""
                if ptype == "newapi" and inst.user_id:
                    extra = f" UID:{inst.user_id}"
                if ptype == "siliconflow":
                    status = "⏸️"
                    extra += " 接口暂不可用"
                lines.append(
                    f"{i}. [{ptype}] {plat_name}{label} {status} | {key_ok} | {url}{extra}"
                )
        else:
            lines.append("  （未配置任何平台）")

        lines.append("———")
        lines.append("命令：/余额 | /添加平台 <类型> <Key> | /删除平台 <类型>")
        lines.append(f"可用类型：{', '.join(PLATFORM_TYPES)}")

        text_output = "\n".join(lines)

        # 图片输出
        if fmt in (OUTPUT_FORMAT_IMAGE, OUTPUT_FORMAT_BOTH):
            try:
                html = render_platform_list_card(instances, PLUGIN_VERSION)
                rendered = await self.ctx.render.html2png(
                    html,
                    selector="#card",
                    viewport={"width": 680, "height": 480},
                    device_scale_factor=2.0,
                )
                image_b64 = (rendered or {}).get("image_base64")
                if image_b64:
                    await self.ctx.send.image(image_b64, stream_id)
                else:
                    await self.ctx.send.text(text_output, stream_id)
            except Exception as exc:
                logger.warning("平台列表图片渲染失败: %s", exc)
                await self.ctx.send.text(text_output, stream_id)
        else:
            await self.ctx.send.text(text_output, stream_id)

        return True, "平台列表", 1


# ═══════════════════════════════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════════════════════════════


def create_plugin() -> APIBalancePlugin:
    """创建 API 余额查询插件实例。"""
    return APIBalancePlugin()
