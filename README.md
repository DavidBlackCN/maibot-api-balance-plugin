# API 余额查询插件 (maibot-api-balance-plugin)

一键查询众多API平台的账号余额，支持配置热重载和 Web UI 配置。

## 支持的平台

| 平台 | 查询方式 | 说明 |
|------|----------|------|
| **DeepSeek** | API Key | `/user/balance`，多币种（CNY/USD） |
| **SiliconFlow（硅基流动）** | API Key | `/v1/user/info`，区分代金券和充值余额 |
| **NewAPI** | 系统访问令牌 + 用户ID | `/api/user/self`，多站点支持 |
| **OpenRouter** 🆕 | API Key | `/api/v1/credits` |
| **Moonshot（月之暗面）** 🆕 | API Key | `/v1/users/me/balance` |
| **OpenAI** 🆕 | API Key | `/v1/dashboard/billing/subscription` |
| **OneThing（网心云）** 🆕 | API Key | `/api/v1/account/wallet/detail` |
| **MiniMax** 🆕 | API Key | `/v1/api/openplatform/coding_plan/remains` |

## 安装

将整个插件目录放入 MaiBot 的 `plugins/` 文件夹：

```
plugins/
└── maibot-api-balance-plugin/
    ├── _manifest.json
    ├── plugin.py
    ├── config.toml
    ├── README.md
    ├── .gitignore
    └── libs/
        └── ...
```

启动 MaiBot 后插件会自动被发现和加载。

## 配置

### 方式一：WebUI（推荐）

在 MaiBot WebUI 的插件管理页面中找到「API 余额查询」，直接编辑配置。

### 方式二：编辑 config.toml

v1.1.0 起**统一使用 `[[api_instances]]` 数组格式**配置所有平台，通过 `type` 字段区分：

```toml
[[api_instances]]
type = "deepseek"
enabled = true
label = "个人号"
api_key = "sk-xxx"

[[api_instances]]
type = "openrouter"
enabled = true
api_key = "sk-or-v1-xxx"

[[api_instances]]
type = "newapi"
enabled = true
label = "自建站A"
api_key = "系统访问令牌"
base_url = "https://my-newapi.example.com"
user_id = "10001"
```

所有平台均支持多账户（多个同 type 的 `[[api_instances]]` 块），通过 `label` 区分。

**各平台 API Key 获取方式：**
- **DeepSeek**：[platform.deepseek.com](https://platform.deepseek.com/api_keys) → API Keys
- **SiliconFlow**：[siliconflow.cn](https://siliconflow.cn/account/ak) → API 密钥
- **NewAPI**：站点「个人设置」→「生成系统访问令牌」（不是 sk- 开头！）+ 记下用户 ID
- **OpenRouter**：[openrouter.ai/keys](https://openrouter.ai/keys) → Create Key
- **Moonshot**：[platform.moonshot.cn](https://platform.moonshot.cn) → API Keys
- **OpenAI**：[platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **OneThing**：[onethingai.com](https://onethingai.com) → API 密钥
- **MiniMax**：[minimaxi.com](https://www.minimaxi.com) → API 密钥

## 命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/余额` | 并行查询所有已启用平台的余额 | `/余额` |
| `/添加平台` | 在线添加平台配置 | `/添加平台 deepseek sk-xxx` |
| `/删除平台` | 移除平台配置 | `/删除平台 newapi 自建站A` |
| `/平台列表` | 查看所有已配置平台及状态 | `/平台列表` |

### 添加平台详细用法

```bash
# 通用格式：/添加平台 <类型> <Key> [备注名] [URL]
/添加平台 deepseek sk-xxx 个人号
/添加平台 openrouter sk-or-v1-xxx
/添加平台 moonshot sk-xxx
/添加平台 openai sk-xxx
/添加平台 onething sk-xxx
/添加平台 minimax sk-xxx

# NewAPI 特殊格式：/添加平台 newapi <令牌> <用户ID> [备注名] [URL]
/添加平台 newapi access-token 10001 自建站A https://my.example.com
```

### 权限控制

默认仅管理员可使用以上命令。在配置中设置：
- `settings.admin_only = true`：仅管理员可用
- `settings.admin_user_ids = ["你的QQ号"]`：指定管理员列表

## 输出格式

| 设置值 | 效果 |
|--------|------|
| `text` | 发送纯文本汇总 |
| `image` | 渲染 HTML 卡片并发送图片（需 MaiBot 有 Playwright Chromium） |
| `both` | 同时发送图片和文本 |

图片渲染失败时会自动降级为文本模式。

## 依赖

- `maibot-plugin-sdk`：MaiBot 插件开发 SDK（自动安装）
- `tomli` / `tomli_w`：用于在线管理命令读写 config.toml（已在 `_manifest.json` 中声明，插件加载时自动安装）

## 常见问题

### Q: 图片卡片渲染失败？
A: 确认 MaiBot 环境中已安装 Playwright Chromium。失败后会自动回退为文本模式，不影响使用。

<details>

<summary>关于uv环境下安装Playwright Chromium的一些说明</summary>
Chromium 不需要在全局环境安装，需要让其出现在 MaiBot 渲染服务查找的路径下。

``` bash
# 设置 MaiBot 期望的浏览器安装路径
export PLAYWRIGHT_BROWSERS_PATH=/your-maibot-path/data/playwright-browsers

# 在 MaiBot 的 uv 环境中安装 playwright
uv pip install playwright

# 在 MaiBot 的 uv 环境中安装 Chromium
uv run playwright install chromium
```
<details>

### Q: NewAPI 查询显示「业务失败：Unauthorized」？
A: NewAPI 需要的是 **系统访问令牌**（在站点「个人设置」→「生成系统访问令牌」获取），
**不是** sk- 开头的 API Key！两者是不同的：
- API Key（sk-xxx）：用于调用 LLM 模型接口
- 系统访问令牌：用于管理 API（余额查询等）
请确认配置中填写的是正确的令牌类型，同时确保 user_id 与令牌所属用户一致。

### Q: 修改 config.toml 后需要重启吗？
A: 不需要。在线命令修改后自动重载；手动编辑后插件会自动检测并应用新配置。

## 鸣谢

- [TAIY2020/llm_balance_plugin](https://github.com/TAIY2020/llm_balance_plugin) - 插件参考
- [BUGJI/astrbot_plugin_balance](https://github.com/BUGJI/astrbot_plugin_balance) - 插件参考
- [DeepSeek V4 Pro](https://chat.deepseek.com/) - 辅助编写了此插件

## 更新日志

### v1.1.0 (2026-05-29)

**新增平台：** OpenRouter / Moonshot（月之暗面）/ OpenAI / OneThing（网心云）/ MiniMax

**重大变更：**
- 统一配置格式：所有平台使用 `[[api_instances]]` 数组，通过 `type` 字段区分，不再使用独立 Section
- 所有平台均支持多账户（多实例）配置
- `/平台列表` 新增 HTML 图片卡片输出，附命令用法

### v1.0.0 (2026-05-29)

首次发布。

**支持的平台：**
- DeepSeek — 查询 `/user/balance`，支持 CNY/USD 多币种显示
- SiliconFlow（硅基流动）— 查询 `/v1/user/info`，区分代金券与充值余额
- NewAPI — 查询 `/api/user/self`，支持多站点独立配置，自动换算 USD

**主要功能：**
- `/余额` — 一键并行查询所有已启用平台的余额
- `/添加平台` — 在线添加平台配置，自动写入 config.toml 并热重载
- `/删除平台` — 在线移除平台配置
- `/平台列表` — 查看所有已配置平台及启用状态
- 图片卡片输出 — HTML 渲染为精美卡片图片（需 Playwright Chromium）
- 纯文本输出 — 作为图片渲染失败时的降级方案
- 权限控制 — 支持仅管理员可用 + 自定义管理员列表
- 配置热重载 — WebUI 或命令行修改配置后自动生效
