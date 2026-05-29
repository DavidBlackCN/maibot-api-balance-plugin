"""配置模型 — maibot-api-balance-plugin v1.1.0

统一使用 [[api_instances]] 数组格式，通过 type 字段区分平台类型。
"""

from typing import List, Literal

from maibot_sdk import Field, PluginConfigBase

from .constants import CONFIG_SCHEMA_VERSION, DEFAULT_TIMEOUT


class PluginSection(PluginConfigBase):
    """插件基本配置。"""

    __ui_label__ = "插件设置"

    name: str = Field(
        default="maibot_api_balance_plugin",
        json_schema_extra={"disabled": True},
    )
    config_version: str = Field(
        default=CONFIG_SCHEMA_VERSION,
        json_schema_extra={"disabled": True},
    )
    enabled: bool = Field(
        default=True,
        description="是否启用插件",
        json_schema_extra={"label": "启用插件"},
    )


class SettingsSection(PluginConfigBase):
    """通用设置。"""

    __ui_label__ = "通用设置"

    timeout: int = Field(
        default=DEFAULT_TIMEOUT,
        description="单平台请求超时秒数",
        ge=1,
        le=60,
        json_schema_extra={"label": "请求超时（秒）"},
    )
    admin_only: bool = Field(
        default=True,
        description="是否仅允许管理员使用查询和管理命令",
        json_schema_extra={"label": "仅管理员可用"},
    )
    admin_user_ids: List[str] = Field(
        default_factory=list,
        description="允许使用命令的用户 QQ 号列表",
        json_schema_extra={
            "label": "管理员列表",
            "hint": '仅在「仅管理员可用」开启时生效',
        },
    )
    output_format: Literal["text", "image", "both"] = Field(
        default="image",
        description="输出格式：text 纯文本 / image HTML 卡片图片 / both 两者都发",
        json_schema_extra={
            "label": "输出格式",
            "hint": "text=纯文本；image=HTML 卡片图片；both=同时发送（image/both 需要 MaiBot 提供 render.html2png 能力）",
        },
    )


class APIInstanceSection(PluginConfigBase):
    """统一的 API 平台实例配置。所有平台共用此模型，通过 type 区分。"""
    __ui_label__ = "API 平台实例"
    type: str = Field(
        default="",
        json_schema_extra={"label": "平台类型", "hint": "deepseek / siliconflow / newapi / openrouter / moonshot / openai / onething / minimax"},
    )
    enabled: bool = Field(default=False, json_schema_extra={"label": "启用"})
    label: str = Field(
        default="",
        json_schema_extra={"label": "备注名", "hint": "用于区分多账户，如「DeepSeek个人号」"},
    )
    api_key: str = Field(
        default="",
        json_schema_extra={"label": "API Key / 令牌", "x-widget": "password"},
    )
    base_url: str = Field(
        default="",
        json_schema_extra={"label": "API 基地址（可选）", "hint": "留空使用默认地址"},
    )
    user_id: str = Field(
        default="",
        json_schema_extra={"label": "用户 ID（仅 NewAPI）", "hint": "NewAPI 站点用户管理页面的数字 ID"},
    )


class LLMBalanceConfig(PluginConfigBase):
    """插件完整配置。"""
    plugin: PluginSection = Field(default_factory=PluginSection)
    settings: SettingsSection = Field(default_factory=SettingsSection)
    api_instances: List[APIInstanceSection] = Field(
        default_factory=list, json_schema_extra={"label": "API 平台列表"}
    )
