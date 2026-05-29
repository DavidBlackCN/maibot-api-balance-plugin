"""配置模型 — maibot-api-balance-plugin

所有用户可见文本使用简体中文，通过 PluginConfigBase + Field 声明强类型配置。
"""

from typing import List, Literal

from maibot_sdk import Field, PluginConfigBase

from .constants import (
    CONFIG_SCHEMA_VERSION,
    DEFAULT_TIMEOUT,
    DEEPSEEK_DEFAULT_BASE_URL,
    NEWAPI_DEFAULT_BASE_URL,
    SILICONFLOW_DEFAULT_BASE_URL,
)


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


class DeepSeekProviderSection(PluginConfigBase):
    """DeepSeek 平台配置。"""

    __ui_label__ = "DeepSeek"

    enabled: bool = Field(
        default=False,
        json_schema_extra={"label": "启用 DeepSeek"},
    )
    api_key: str = Field(
        default="",
        json_schema_extra={"label": "API Key", "x-widget": "password"},
    )
    base_url: str = Field(
        default=DEEPSEEK_DEFAULT_BASE_URL,
        json_schema_extra={"label": "API 基地址"},
    )


class SiliconFlowProviderSection(PluginConfigBase):
    """硅基流动平台配置。"""

    __ui_label__ = "SiliconFlow（硅基流动）"

    enabled: bool = Field(
        default=False,
        json_schema_extra={"label": "启用硅基流动"},
    )
    api_key: str = Field(
        default="",
        json_schema_extra={"label": "API Key", "x-widget": "password"},
    )
    base_url: str = Field(
        default=SILICONFLOW_DEFAULT_BASE_URL,
        json_schema_extra={"label": "API 基地址"},
    )


class NewAPIInstanceSection(PluginConfigBase):
    """单个 NewAPI 站点配置。支持配置多个实例分别查询。"""

    __ui_label__ = "NewAPI 实例"

    enabled: bool = Field(
        default=False,
        json_schema_extra={"label": "启用此实例"},
    )
    label: str = Field(
        default="",
        description="用于区分多个 NewAPI 站点的名称",
        json_schema_extra={"label": "实例名称", "hint": "例如：自建站A、公益站B"},
    )
    user_id: str = Field(
        default="",
        description="NewAPI 站点的用户数字 ID（在站点用户管理页面可查看）",
        json_schema_extra={"label": "用户 ID", "hint": "纯数字，如 10001"},
    )
    api_key: str = Field(
        default="",
        json_schema_extra={"label": "系统访问令牌", "x-widget": "password", "hint": "在站点「个人设置」→「生成系统访问令牌」获取，不是 sk- 开头的 API Key"},
    )
    base_url: str = Field(
        default=NEWAPI_DEFAULT_BASE_URL,
        json_schema_extra={"label": "站点地址", "hint": "NewAPI 站点的完整 URL"},
    )


class LLMBalanceConfig(PluginConfigBase):
    """插件完整配置。

    各平台 Section 提升到顶层，以便 WebUI 正确渲染。
    """

    plugin: PluginSection = Field(default_factory=PluginSection)
    settings: SettingsSection = Field(default_factory=SettingsSection)
    deepseek: DeepSeekProviderSection = Field(default_factory=DeepSeekProviderSection)
    siliconflow: SiliconFlowProviderSection = Field(
        default_factory=SiliconFlowProviderSection
    )
    newapi_instances: List[NewAPIInstanceSection] = Field(
        default_factory=list,
        description="NewAPI 站点列表，可配置多个",
        json_schema_extra={"label": "NewAPI 多站点"},
    )
