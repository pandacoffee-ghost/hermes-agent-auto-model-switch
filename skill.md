# Auto Model Switch

## 功能
在对话不中断的情况下，根据内容类型和用量额度自动切换模型。

## 重要：插件不改变默认模型
安装后你的模型不会变。插件只在以下情况介入：
1. 你发送了当前模型不支持的多媒体内容（图片/音频）
2. 当前模型的配额用完了

用户随时可以用 `/model` 手动切换，不受插件影响。

## 自动切换场景

### 内容感知切换
- 发送图片但当前模型不支持 vision → 自动切到 vision 模型
- 连续 2 轮纯文本后 → 自动切回原模型
- 切换时会通知用户

### 额度管控
- 模型 token 用量超过配置的限额 → 自动切到 fallback 模型
- 支持 daily/weekly/monthly/total 四种周期，可叠加
- 超额时通知用户，用户可通过对话重设

## 工具使用

### model_quota_set — 设置额度
当用户说"设限额"、"设额度"、"配置预算"时调用。
参数：model（模型名）、period（daily/weekly/monthly/total）、max_tokens（最大token数）、fallback（可选，超额后切换目标）

### model_quota_status — 查看状态
当用户说"查看额度"、"用了多少"、"额度状态"时调用。

### model_quota_reset — 重置用量
当用户说"重置用量"、"清零"时调用。
参数：model（模型名）
