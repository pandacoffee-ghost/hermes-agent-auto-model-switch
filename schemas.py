"""Tool schemas — what the LLM sees."""

MODEL_QUOTA_STATUS = {
    "name": "model_quota_status",
    "description": (
        "查看所有模型的额度配置和当前用量。显示每个模型的各周期限额、"
        "已用 token 数、剩余额度、以及 fallback 模型配置。"
        "当用户询问模型额度、用量、配额状态时使用。"
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}

MODEL_QUOTA_SET = {
    "name": "model_quota_set",
    "description": (
        "设置或更新模型的 token 用量额度。支持 daily（日限额）、weekly（周限额）、"
        "monthly（月限额）、total（总限额）四种周期。同一模型可叠加多个周期限额。"
        "可同时设置 fallback 模型（额度用完后自动切换的目标）。"
        "当用户要求设置、修改模型额度或配置 fallback 时使用。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "description": "模型名称，如 'deepseek-v4-flash'、'LongCat-Flash-Chat'",
            },
            "period": {
                "type": "string",
                "enum": ["daily", "weekly", "monthly", "total"],
                "description": "额度周期：daily=日限额, weekly=周限额, monthly=月限额, total=总限额",
            },
            "max_tokens": {
                "type": "integer",
                "description": "该周期内最大 token 数。如 2000000 表示 200 万 token",
            },
            "fallback": {
                "type": "string",
                "description": "额度用完后自动切换到的模型名称（可选）",
            },
        },
        "required": ["model", "period", "max_tokens"],
    },
}

MODEL_QUOTA_RESET = {
    "name": "model_quota_reset",
    "description": (
        "重置指定模型的所有用量计数器归零。不会删除额度配置本身。"
        "当用户要求重置某个模型的用量统计时使用。"
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "description": "要重置用量的模型名称",
            },
        },
        "required": ["model"],
    },
}
