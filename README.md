# Auto Model Switch Plugin for Hermes Agent

> Hermes Agent 目前不支持基于 token 预算的自动模型切换。本插件通过钩子系统实现了这一能力：根据 token 用量额度和内容类型，在对话不中断的情况下自动切换模型。

## 谁需要这个插件？

本插件适合**同时使用多个按 token 计费的 provider，想精细控制每个模型花费上限**的用户。

典型场景：
- DeepSeek 免费额度每日有限，用完自动切到 LongCat 或 OpenRouter
- 用便宜的文本模型做主力，发图片时自动临时切到 vision 模型
- 多个 provider 之间设置级联降级预算

**不适合的场景：**
- Kimi Coding Plan、MiniMax 等按调用次数/小时限制的方案 — 这类限制触发 429 后，Hermes 官方的 `fallback_providers` 已能处理
- 包月不限量的用户 — 不需要额度管理

## 功能

- **额度管控** — 为模型设置 token 预算（日/周/月/总限额），超额后自动切换到 fallback 模型
- **内容感知路由** — 检测到图片/音频但当前模型不支持时，自动切换到支持的模型
- **智能回切** — 多媒体处理完毕后，连续 2 轮纯文本自动切回原模型
- **多级 Fallback 链** — 支持 A→B→C 级联降级
- **对话不中断** — 切换在同一 Agent 实例上原地进行，历史完整保留

## 安装

```bash
# 方式一：复制到 Hermes 插件目录
cp -r hermes-agent-auto-model-switch ~/.hermes/plugins/auto-model-switch

# 方式二：在 config.yaml 中指定路径
# plugins:
#   enabled:
#   - /path/to/hermes-agent-auto-model-switch
```

重启 Hermes，输入 `/plugins` 确认加载：

```
✓ auto-model-switch v2.0.0 (3 tools, 3 hooks)
```

## 使用

### 设置额度（通过对话）

直接告诉 AI：

```
给 claude-opus-4.6 设日限额 200 万 token，用完切 deepseek-v4-pro
给 deepseek-v4-pro 设月限额 5000 万 token，用完切 deepseek-v4-flash
```

### 查看状态

```
查看模型额度状态
```

### 重置用量

```
重置  claude-opus-4.6 的用量
```

### 手动切换

`/model` 命令随时可用，不受插件影响。手动切换后插件会以新模型为基准继续工作。

## 额度周期

| 周期 | 重置时间 | 示例 |
|------|---------|------|
| `daily` | 每天 00:00 | 免费 API 日限额 |
| `weekly` | 每周一 00:00 | 周预算控制 |
| `monthly` | 每月 1 号 | 付费 API 月度预算 |
| `total` | 永不重置 | 一次性额度 |

同一模型可叠加多个周期，任一超额即触发切换。

## 切换通知

当自动切换发生时：
- 终端显示 `⚡ Auto-switch: modelA → modelB (provider)`
- 左下角状态栏立即更新为当前模型
- LLM 会意识到模型已切换并相应调整

## 默认行为

- **不改变你的默认模型** — 安装前用什么模型，安装后还是什么模型
- **不修改 config.yaml** — 零侵入
- **不配额度也有用** — 仍会在内容类型不匹配时自动切换

## 插件结构

```
auto-model-switch/
├── plugin.yaml      # 清单：声明 hooks 和 tools
├── __init__.py      # register(ctx) 入口
├── detector.py      # 内容类型检测（image_url/input_audio）
├── quota.py         # 额度管理（多周期、持久化）
├── switcher.py      # 模型切换（调用 Hermes 内部 API）
├── hooks.py         # 钩子逻辑（pre_llm_call / post_api_request）
├── schemas.py       # 工具 schema（LLM 可见）
├── tools.py         # 工具 handler
├── skill.md         # 技能描述
└── data/
    └── quotas.json  # 运行时数据（.gitignore）
```

## 技术原理

本插件利用 Hermes 的插件钩子系统：

- **`pre_llm_call`** — 每轮 LLM 调用前触发，检测内容类型 + 检查额度，必要时调用 `agent.switch_model()` 切换
- **`post_api_request`** — 每次 API 响应后触发，从 `usage` 字段记录真实 token 用量
- **`on_session_start`** — 新会话开始时，首次使用引导

模型切换通过 `hermes_cli.model_switch.switch_model()` 解析 credentials，再调用 `agent.switch_model()` 重建 client。对话历史完整保留，因为切换的是同一个 Agent 实例。

## 常见问题

**Q: 安装后我的模型会变吗？**
A: 不会。插件不修改配置，你原来用什么模型，安装后还是什么模型。

**Q: 切换模型后对话历史会丢失吗？**
A: 不会。切换在同一个 Agent 实例上原地进行，对话历史完整保留。

**Q: 插件崩溃会影响 Hermes 吗？**
A: 不会。Hermes 的插件系统会捕获所有异常，插件出错只会被跳过。

**Q: 我不设置额度，插件有什么用？**
A: 仍然有用——当你发送图片但当前模型不支持 vision 时，插件会自动临时切换。

**Q: 手动 `/model` 切换会冲突吗？**
A: 不会。手动切换优先级最高，插件会以新模型为基准继续工作。

## License

MIT
