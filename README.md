# Auto Model Switch Plugin

## English

### Overview
Automatically switches models mid-conversation without interruption. Two core features:
1. **Content-aware routing** — detects images/audio/video in your message and switches to a capable model if the current one doesn't support it. Switches back after 2 consecutive text-only turns.
2. **Quota enforcement** — set token budgets (daily/weekly/monthly/total) per model. When exceeded, automatically falls back to the next model in the chain.

### How It Works (Default Behavior)
- **The plugin does NOT change your default model.** Whatever model you have configured in Hermes (`/model` or `config.yaml`) remains your primary model.
- The plugin only intervenes in two cases:
  1. You send multimedia content that your current model can't handle
  2. A model's configured quota is exhausted
- If you have no quotas configured, the plugin is passive — it only activates for content-type switching.

### Manual `/model` Switching
- **Fully compatible.** You can use `/model` at any time to switch models manually.
- Manual switches override the plugin's state — if you manually switch, the plugin treats the new model as your "current" model going forward.
- The plugin will NOT fight your manual switches or switch you back unexpectedly.
- Quota tracking still applies to whatever model is active.

### Setup
1. Copy this plugin to `~/.hermes/plugins/auto-model-switch/` (or add the path to `plugins.enabled` in config.yaml)
2. Restart Hermes
3. On first session, the plugin will prompt you to configure quotas (optional)

### Quota Configuration (via conversation)
Tell the agent:
- "Set a daily quota of 2M tokens for deepseek-v4-flash, fallback to LongCat-Flash-Chat"
- "Set a monthly quota of 50M tokens for LongCat-Flash-Chat"
- "Show quota status"
- "Reset usage for deepseek-v4-flash"

### Quota Periods
| Period | Resets |
|--------|--------|
| daily | Every day at 00:00 |
| weekly | Every Monday at 00:00 |
| monthly | 1st of each month |
| total | Never (lifetime budget) |

A model can have multiple periods stacked. Any single period exceeding triggers the switch.

### Content-Type Switching Behavior
| Detected content | Action |
|-----------------|--------|
| Image (image_url, input_image) | Switch to vision model if current doesn't support |
| Audio (input_audio) | Switch to audio model if current doesn't support |
| Text only (after content switch) | Count turns; switch back after 2 consecutive text turns |
| Text only (normal) | No action |

### Tools Provided
- `model_quota_status` — view all quotas and usage
- `model_quota_set` — set/update a quota (model, period, max_tokens, fallback)
- `model_quota_reset` — reset usage counters for a model

---

## 中文说明

### 概述
在对话不中断的情况下自动切换模型。两个核心功能：
1. **内容感知路由** — 检测到消息中包含图片/音频/视频，且当前模型不支持时，自动切换到支持的模型。连续 2 轮纯文本后自动切回。
2. **额度管控** — 为模型设置 token 预算（日/周/月/总限额），超额后自动切换到 fallback 模型。

### 默认行为（重要）
- **插件不会改变你的默认模型。** 你在 Hermes 中配置的模型（通过 `/model` 或 `config.yaml`）始终是你的主模型。
- 插件只在两种情况下介入：
  1. 你发送了当前模型不支持的多媒体内容（图片/音频）
  2. 当前模型的配额用完了
- 如果你没有配置任何额度，插件几乎是透明的——只在内容类型不匹配时才会切换。

### 手动 `/model` 切换是否受影响？
- **完全不受影响。** 你随时可以用 `/model` 手动切换模型。
- 手动切换会覆盖插件状态——插件会把你手动选择的模型当作新的"当前模型"。
- 插件不会与你的手动操作冲突，不会把你意外切回去。
- 额度追踪仍然对当前活跃的模型生效。

### 安装
1. 将此插件复制到 `~/.hermes/plugins/auto-model-switch/`，或在 config.yaml 的 `plugins.enabled` 中添加插件路径
2. 重启 Hermes
3. 首次会话时，插件会提示你配置额度（可选，不配也行）

### 额度配置（通过对话）
直接告诉 AI：
- "给 deepseek-v4-flash 设日限额 200 万 token，用完切 LongCat-Flash-Chat"
- "给 LongCat-Flash-Chat 设月限额 5000 万 token"
- "查看模型额度状态"
- "重置 deepseek-v4-flash 的用量"

### 额度周期
| 周期 | 重置时间 |
|------|---------|
| daily（日限额） | 每天 00:00 自动重置 |
| weekly（周限额） | 每周一 00:00 自动重置 |
| monthly（月限额） | 每月 1 号自动重置 |
| total（总限额） | 永不重置，用完为止 |

同一模型可以叠加多个周期限额，任一周期超额即触发切换。

### 内容类型切换逻辑
| 检测到的内容 | 动作 |
|-------------|------|
| 图片（image_url, input_image） | 当前模型不支持 vision → 切到 vision 模型 |
| 音频（input_audio） | 当前模型不支持 audio → 切到 audio 模型 |
| 纯文本（之前因内容切换过） | 计数，连续 2 轮纯文本 → 切回原模型 |
| 纯文本（正常状态） | 不做任何操作 |

### 多级 Fallback 链
```
deepseek-v4-flash (日限 200万)
  → 用完 → LongCat-Flash-Chat (月限 5000万)
    → 用完 → 通知用户所有模型额度耗尽
```

### 提供的工具
- `model_quota_status` — 查看所有模型额度和用量
- `model_quota_set` — 设置/更新额度（模型、周期、最大 token 数、fallback）
- `model_quota_reset` — 重置指定模型的用量计数器

### 常见问题

**Q: 安装后我的模型会变吗？**
A: 不会。插件不修改你的 Hermes 配置，你原来用什么模型，安装后还是什么模型。

**Q: 我不设置额度，插件有什么用？**
A: 仍然有用——当你发送图片但当前模型不支持 vision 时，插件会自动临时切换到支持的模型，处理完后切回来。

**Q: 切换模型后对话历史会丢失吗？**
A: 不会。切换是在同一个 Agent 实例上原地进行的，对话历史完整保留。

**Q: 插件崩溃会影响 Hermes 吗？**
A: 不会。Hermes 的插件系统会捕获所有异常，插件出错只会被跳过，不影响正常使用。
