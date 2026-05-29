"""MaiBot API 余额查询插件 — 入口文件

通过聊天命令 /余额 并行查询 DeepSeek / SiliconFlow / NewAPI 平台的账号余额，
统一汇总输出（文本或 HTML 图片卡片）。支持在线命令管理平台配置并自动重载。

装饰器：优先使用 @Command（斜杠命令）
配置：PluginConfigBase + Field，用户可见文本全部简体中文
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
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
}

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

    支持 DeepSeek / SiliconFlow / NewAPI 三大平台，
    通过 /余额 命令并行查询并汇总输出。
    """

    config_model = LLMBalanceConfig

    def __init__(self) -> None:
        super().__init__()
        self._admin_set: set[str] = set()

    # ── 生命周期 ──────────────────────────────────────────────────────

    async def on_load(self) -> None:
        self._refresh_admin_cache()
        logger.info(
            "API 余额查询插件(v%s) 初始化完成。", PLUGIN_VERSION
        )

    async def on_unload(self) -> None:
        logger.info("API 余额查询插件已卸载。")

    async def on_config_update(
        self, scope: str, config_data: dict, version: str
    ) -> None:
        if scope == "self":
            self._refresh_admin_cache()
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
            if ptype not in _PROVIDER_MAP:
                logger.warning("未知平台类型「%s」，已跳过", ptype)
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
                "❌ 未启用任何平台。请在配置中启用至少一个平台并填入 API Key。",
                stream_id,
            )
            return False, "无可用平台", 1

        await self.ctx.send.text(
            f"⏳ 正在并行查询 {len(providers)} 个平台…", stream_id,
        )

        # 并行查询
        async def _run(
            provider: _BalanceProvider,
        ) -> Tuple[_BalanceProvider, Any]:
            try:
                payload = await asyncio.to_thread(provider.fetch_sync)
                return provider, payload
            except Exception as exc:
                return provider, exc

        results = await asyncio.gather(*[_run(p) for p in providers])

        # 转换为结构化记录
        records: List[Tuple[_BalanceProvider, Any]] = []
        for provider, payload_or_exc in results:
            if isinstance(payload_or_exc, Exception):
                records.append((provider, payload_or_exc))
                continue
            try:
                records.append(
                    (provider, provider.to_record(payload_or_exc))
                )
            except Exception as exc:
                logger.error(
                    "%s 解析响应失败: %s",
                    provider.display_name,
                    exc,
                    exc_info=True,
                )
                records.append((provider, exc))

        # 按 output_format 输出
        fmt = (
            self.config.settings.output_format or OUTPUT_FORMAT_TEXT
        ).lower()
        if fmt not in OUTPUT_FORMATS:
            fmt = OUTPUT_FORMAT_TEXT

        if fmt in (OUTPUT_FORMAT_IMAGE, OUTPUT_FORMAT_BOTH):
            image_b64: Optional[str] = None
            failure_stage: str = ""
            failure_exc: Optional[Exception] = None

            try:
                html_doc = render_html_card(records)
            except Exception as exc:
                failure_stage = "html_compose"
                failure_exc = exc
            else:
                try:
                    rendered = await self.ctx.render.html2png(
                        html_doc,
                        selector="#card",
                        viewport={"width": 720, "height": 480},
                        device_scale_factor=2.0,
                    )
                except Exception as exc:
                    failure_stage = "html2png"
                    failure_exc = exc
                else:
                    image_b64 = (rendered or {}).get("image_base64")
                    if not image_b64:
                        failure_stage = "html2png_empty"

            if image_b64:
                try:
                    await self.ctx.send.image(image_b64, stream_id)
                except Exception as exc:
                    failure_stage = "send_image"
                    failure_exc = exc

            if failure_stage:
                stage_msg = {
                    "html_compose": (
                        "HTML 卡片组装失败",
                        "⚠️ 卡片组装失败，已回退为文本模式",
                    ),
                    "html2png": (
                        "html2png 渲染失败",
                        "⚠️ 卡片渲染失败，已回退为文本模式",
                    ),
                    "html2png_empty": (
                        "html2png 未返回 image_base64",
                        "⚠️ 渲染结果为空，已回退为文本模式",
                    ),
                    "send_image": (
                        "图片发送失败",
                        "⚠️ 图片发送失败，已回退为文本模式",
                    ),
                }[failure_stage]
                if failure_exc is not None:
                    logger.error(
                        "%s，回退文本模式: %s",
                        stage_msg[0],
                        failure_exc,
                        exc_info=True,
                    )
                else:
                    logger.warning("%s，回退文本模式", stage_msg[0])
                await self.ctx.send.text(stage_msg[1], stream_id)
                fmt = OUTPUT_FORMAT_TEXT

        if fmt in (OUTPUT_FORMAT_TEXT, OUTPUT_FORMAT_BOTH):
            await self.ctx.send.text(
                format_text_report(records), stream_id
            )

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
                "类型：deepseek / siliconflow / newapi / openrouter / moonshot / openai / onething / minimax\n"
                "NewAPI 需额外提供用户ID：/添加平台 newapi <令牌> <用户ID> [备注名] [URL]",
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
                key_ok = "已配置" if inst.api_key.strip() else "⚠️ 未配置 Key"
                url = inst.base_url or "(默认)"
                extra = ""
                if ptype == "newapi" and inst.user_id:
                    extra = f" UID:{inst.user_id}"
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
