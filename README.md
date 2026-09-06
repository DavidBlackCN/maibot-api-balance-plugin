# API 余额查询插件 (maibot-api-balance-plugin)

一键查询众多API平台的账号余额，支持配置热重载和 Web UI 配置。

![余额查询](https://cdn.jsdelivr.net/gh/DavidBlackCN/maibot-api-balance-plugin@main/image/余额.png)

---

![平台列表](https://cdn.jsdelivr.net/gh/DavidBlackCN/maibot-api-balance-plugin@main/image/平台列表.png)

## 支持的平台

| 平台 | 查询方式 | 说明 |
|------|----------|------|
| **DeepSeek** | API Key | `/user/balance`，多币种（CNY/USD） |
| **SiliconFlow（硅基流动）** | 暂停查询 | 官方余额接口暂不可用；保留兼容代码和旧配置删除能力 |
| **NewAPI** | 系统访问令牌 + 用户ID | `/api/user/self`，多站点支持 |
| **OpenRouter** 🆕 | API Key | `/api/v1/credits` |
| **Moonshot（月之暗面）** 🆕 | API Key | `/v1/users/me/balance` |
| **OpenAI** 🆕 | API Key | `/v1/dashboard/billing/subscription` |
| **OneThing（网心云）** 🆕 | API Key | `/api/v1/account/wallet/detail` |
| **MiniMax** 🆕 | API Key | `/v1/api/openplatform/coding_plan/remains` |
| **火山方舟** 🆕 | 火山引擎 AK/SK | 费用中心 `QueryBalanceAcct`，查询方舟扣费账户余额 |

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

[[api_instances]]
type = "volcengine"
enabled = true
label = "主账户"
access_key_id = "AKLT..."
secret_access_key = "..."
```

所有平台均支持多账户（多个同 type 的 `[[api_instances]]` 块），通过 `label` 区分。

**各平台访问凭证获取方式：**
- **DeepSeek**：[platform.deepseek.com](https://platform.deepseek.com/api_keys) → API Keys
- **NewAPI**：站点「个人设置」→「安全设置」→「系统访问令牌」，同时记下当前账号的用户 ID
- **OpenRouter**：[openrouter.ai/keys](https://openrouter.ai/keys) → Create Key
- **Moonshot**：[platform.moonshot.cn](https://platform.moonshot.cn) → API Keys
- **OpenAI**：[platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **OneThing**：[onethingai.com](https://onethingai.com) → API 密钥
- **MiniMax**：[minimaxi.com](https://www.minimaxi.com) → API 密钥
- **火山方舟**：[火山引擎访问控制](https://console.volcengine.com/iam/) → 创建 IAM 用户、授权费用中心只读策略并创建访问密钥

### NewAPI：获取凭证与添加平台

NewAPI 的余额查询调用站点管理接口 `/api/user/self`，需要的是**系统访问令牌**，不是用于调用模型的 `sk-...` API Key。

1. 登录需要查询余额的 NewAPI 站点。不同站点的界面名称可能略有差异。
2. 打开「个人设置」→「安全设置」→「系统访问令牌」，生成并复制系统访问令牌。
3. 在个人资料或账户信息页面找到当前账号的数字用户 ID。该 ID 必须与生成令牌的登录用户一致。
4. 自建或第三方站点还要记下站点根地址，例如 `https://newapi.example.com`。不要填写 `/api/user/self` 路径。

命令格式：

```text
/添加平台 newapi <系统访问令牌> <用户ID> [备注名] [站点地址]
```

参数说明：

| 参数 | 是否必填 | 内容 |
|------|----------|------|
| `newapi` | 是 | 固定的平台类型，必须原样输入 |
| `系统访问令牌` | 是 | 在 NewAPI「个人设置 / 安全设置」中生成的管理令牌，写入配置的 `api_key` 字段 |
| `用户ID` | 是 | 当前 NewAPI 账号的数字 ID，写入 `user_id`；必须与令牌所属用户一致 |
| `备注名` | 否 | 用于区分多个站点或账号，例如 `自建站A`；填写站点地址时必须同时填写该位置 |
| `站点地址` | 否 | NewAPI 站点根地址，写入 `base_url`；不填时使用插件默认地址 |

命令通过空格区分参数。需要同时填写站点地址时，`备注名` 请使用不含空格的短名称；如果只填写备注名且不填写地址，备注名可以包含空格。

示例：

```text
# 使用自建站点；access-token、10001 和域名均为示例
/添加平台 newapi access-token 10001 自建站A https://newapi.example.com
```

对应的 TOML 配置如下：

```toml
[[api_instances]]
type = "newapi"
enabled = true
label = "自建站A"
api_key = "系统访问令牌"
user_id = "10001"
base_url = "https://newapi.example.com"
```

### 火山方舟：创建 IAM 用户、获取 AK/SK 与添加平台

插件查询的是火山方舟消费所使用的**火山引擎资金账户余额**。推荐为插件单独创建 IAM 用户并授予系统策略 `BillingCenterReadOnlyAccess`，避免使用主账号密钥或授予写入权限。该策略提供费用中心全部只读权限，包括账户余额页面及相关查询 OpenAPI。

1. 使用火山引擎主账号或有 IAM 管理权限的账号打开[访问控制控制台](https://console.volcengine.com/iam/)。
2. 进入「身份管理」→「用户」，创建一个供本插件专用的 IAM 用户，例如 `maibot-balance`。插件只调用 API，不要求开启控制台登录。
3. 在用户授权页面添加系统预设策略 `BillingCenterReadOnlyAccess`。
4. 打开该 IAM 用户的详情页，进入「密钥」页签并创建访问密钥。创建结果页会列出用户名、`Access Key ID` 和 `Secret Access Key`；未开启控制台登录时，密码位置可能显示为 `-`，这是正常现象。
5. 立即复制两项内容或保存 CSV。`Secret Access Key` 通常只在创建时完整展示。

命令格式：

```text
/添加平台 volcengine <Access Key ID> <Secret Access Key> [备注名]
```

参数说明：

| 参数 | 是否必填 | 内容 |
|------|----------|------|
| `volcengine` | 是 | 固定的平台类型，必须原样输入 |
| `Access Key ID` | 是 | IAM 用户密钥页面生成的 AK，通常以 `AKLT` 开头，写入 `access_key_id` |
| `Secret Access Key` | 是 | 与该 AK 配套的 SK，写入 `secret_access_key` |
| `备注名` | 否 | 仅用于卡片和平台列表显示，例如 `方舟主账户`；不参与鉴权，可以包含空格 |

示例：

```text
# 以下凭证均为占位符，请替换为新建 IAM 用户的真实 AK/SK
/添加平台 volcengine AKLTxxxxxxxxxxxxxxxx xxxxxxxxxxxxxxxxxxxxxxxx 方舟主账户
```

对应的 TOML 配置如下：

```toml
[[api_instances]]
type = "volcengine"
enabled = true
label = "方舟主账户"
access_key_id = "AKLTxxxxxxxxxxxxxxxx"
secret_access_key = "xxxxxxxxxxxxxxxxxxxxxxxx"
```

配置后可先执行 `/平台列表` 检查凭证是否完整，再执行 `/余额` 验证查询。如果返回权限不足，请确认策略授予的是 `BillingCenterReadOnlyAccess`，并等待刚完成的 IAM 授权生效。

费用中心虽然通过通用地址 `open.volcengineapi.com` 提供服务，但签名区域固定使用 `cn-north-1`；插件会自动处理该参数，无需在配置中填写。

`/添加平台` 消息本身包含明文凭证。优先通过 MaiBot WebUI 的密码输入框或直接编辑 `config.toml` 配置；如需使用命令，请在受控的私聊中执行并及时删除包含凭证的聊天记录。

### 定时播报

定时播报默认关闭。多个群共用一个北京时间，播报使用“说明头 + 余额总览”的合并消息：

```toml
[broadcast]
enabled = true
group_ids = ["123456789", "987654321"]
time = "09:00"
header = "每日 API 平台余额播报"
```

`time` 必须为 24 小时制 `HH:MM`。插件停机期间错过的播报不会补发；每个群每天最多尝试一次，某个群发送失败不会影响其他群。

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

# NewAPI：详细参数和获取方法见上文
/添加平台 newapi access-token 10001 自建站A https://my.example.com

# 火山方舟：详细参数和 IAM 授权方法见上文
/添加平台 volcengine AKLTxxxxxxxx xxxxxxxxxxxxxxxx 方舟主账户
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

<summary>关于 uv 环境下安装 Playwright Chromium 的一些说明</summary>

Chromium 不需要在全局环境安装，需要让其出现在 MaiBot 渲染服务查找的路径下。

```bash
# 设置 MaiBot 期望的浏览器安装路径
export PLAYWRIGHT_BROWSERS_PATH=/your-maibot-path/data/playwright-browsers

# 在 MaiBot 的 uv 环境中安装 playwright
uv pip install playwright

# 在 MaiBot 的 uv 环境中安装 Chromium
uv run playwright install chromium
```

</details>

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
- [Ling-LA/maibot-llm-balance-monitor](https://github.com/Ling-LA/maibot-llm-balance-monitor) - 火山方舟与卡片展示参考
- [BUGJI/astrbot_plugin_balance](https://github.com/BUGJI/astrbot_plugin_balance) - 插件参考
- [DeepSeek V4 Pro](https://chat.deepseek.com/) - 辅助编写了此插件

## 更新日志

### v1.2.0 (2026-09-06)

- 暂停硅基流动余额查询，同时保留原 Provider 与旧配置兼容
- 新增火山方舟（火山引擎费用中心）余额查询和 AK/SK 配置
- 新增多个群共用时间的每日合并消息播报，默认关闭
- 卡片新增查询时间、成功/失败统计并改善长名称及空状态显示

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
