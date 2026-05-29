# API 余额查询插件 (maibot-api-balance-plugin)

一键查询 DeepSeek / SiliconFlow / NewAPI 平台的账号余额。

## 支持的平台

| 平台 | 查询方式 | 说明 |
|------|----------|------|
| **DeepSeek** | API Key (Bearer Token) | 查询 `/user/balance`，支持多币种（CNY/USD） |
| **SiliconFlow（硅基流动）** | API Key (Bearer Token) | 查询 `/v1/user/info`，区分代金券和充值余额 |
| **NewAPI** | API 令牌 (sk- 开头) | 查询 `/api/user/self`，可配置多个站点分别查询 |

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

直接编辑插件目录下的 `config.toml`，保存后自动生效。

**各平台 API Key 获取方式：**

- **DeepSeek**：访问 [platform.deepseek.com](https://platform.deepseek.com/api_keys) → API Keys
- **SiliconFlow**：访问 [siliconflow.cn](https://siliconflow.cn/account/ak) → API 密钥
- **NewAPI**：在您的 NewAPI 站点中，进入「个人设置」→ 点击「生成系统访问令牌」，复制生成的令牌值（**不是** sk- 开头的 API Key！）。同时记下您的用户 ID（在用户管理页面可见）。

### 多 NewAPI 配置示例

```toml
[[newapi_instances]]
enabled = true
label = "自建站A"
user_id = "10001"
api_key = "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
base_url = "https://my-newapi.example.com"

[[newapi_instances]]
enabled = true
label = "公益站B"
user_id = "20001"
api_key = "sk-yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
base_url = "https://public-api.example.com"
```

## 命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/余额` | 并行查询所有已启用平台的余额 | `/余额` |
| `/添加平台` | 在线添加平台配置 | `/添加平台 deepseek sk-xxx` |
| `/删除平台` | 移除平台配置 | `/删除平台 newapi 自建站A` |
| `/平台列表` | 查看所有已配置平台及状态 | `/平台列表` |

### 添加平台详细用法

```bash
# DeepSeek
/添加平台 deepseek sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
/添加平台 deepseek sk-xxx https://custom-deepseek.example.com

# SiliconFlow
/添加平台 siliconflow sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# NewAPI（需指定实例名、用户ID、系统令牌）
# 用户ID 可在 NewAPI 站点的「用户管理」页面查看
/添加平台 newapi 我的站点 10001 sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
/添加平台 newapi 自建站 10002 sk-xxx https://my-newapi.example.com
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

- `maibot-plugin-sdk`：MaiBot 插件开发 SDK
- `tomli` / `tomli_w`（可选）：用于在线管理命令读写 config.toml。如未安装，插件使用内置的简易 TOML 序列化器。

安装可选依赖：
```bash
pip install tomli tomli_w
```

## 常见问题

### Q: 图片卡片渲染失败？
A: 确认 MaiBot 环境中已安装 Playwright Chromium。失败后会自动回退为文本模式，不影响使用。

### Q: NewAPI 查询显示「业务失败：Unauthorized」？
A: NewAPI 需要的是 **系统访问令牌**（在站点「个人设置」→「生成系统访问令牌」获取），
**不是** sk- 开头的 API Key！两者是不同的：
- API Key（sk-xxx）：用于调用 LLM 模型接口
- 系统访问令牌：用于管理 API（余额查询等）
请确认配置中填写的是正确的令牌类型，同时确保 user_id 与令牌所属用户一致。

### Q: 如何添加多个 NewAPI 站点？
A: 在 config.toml 中添加多个 `[[newapi_instances]]` 块，或使用命令 `/添加平台 newapi <实例名> <API Key> [URL]` 逐个添加。

### Q: 修改 config.toml 后需要重启吗？
A: 不需要。在线命令修改后自动重载；手动编辑后插件会自动检测并应用新配置。

## 更新日志

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
