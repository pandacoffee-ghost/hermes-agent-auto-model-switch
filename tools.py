"""Tool handlers."""

import json
from .hooks import get_quota


def handle_quota_status(args: dict, **kwargs) -> str:
    """Show all model quotas and usage."""
    quota = get_quota()
    if quota is None:
        return json.dumps({"error": "Plugin not initialized"})

    status = quota.get_status()
    if not status:
        return json.dumps({
            "message": "尚未配置任何模型额度。",
            "hint": "使用 model_quota_set 工具来设置模型额度，例如：model=deepseek-v4-flash, period=daily, max_tokens=2000000",
        }, ensure_ascii=False)

    result = {}
    for model, cfg in status.items():
        model_info = {"fallback": cfg.get("fallback", ""), "quotas": []}
        for q in cfg.get("quotas", []):
            used = q.get("used_tokens", 0)
            max_t = q.get("max_tokens", 0)
            pct = round(used / max_t * 100, 1) if max_t > 0 else 0
            model_info["quotas"].append({
                "period": q["period"],
                "used": used,
                "max": max_t,
                "remaining": max(0, max_t - used),
                "usage_percent": pct,
                "period_start": q.get("period_start", ""),
            })
        result[model] = model_info

    return json.dumps(result, ensure_ascii=False, indent=2)


def handle_quota_set(args: dict, **kwargs) -> str:
    """Set or update a model quota."""
    quota = get_quota()
    if quota is None:
        return json.dumps({"error": "Plugin not initialized"})

    model = args.get("model", "").strip()
    period = args.get("period", "").strip()
    max_tokens = args.get("max_tokens")
    fallback = args.get("fallback", "").strip()

    if not model:
        return json.dumps({"error": "缺少 model 参数"}, ensure_ascii=False)
    if period not in ("daily", "weekly", "monthly", "total"):
        return json.dumps({"error": "period 必须是 daily/weekly/monthly/total"}, ensure_ascii=False)
    if not max_tokens or int(max_tokens) <= 0:
        return json.dumps({"error": "max_tokens 必须大于 0"}, ensure_ascii=False)

    quota.set_quota(model, period, int(max_tokens), fallback)

    msg = f"已设置 {model} 的{period}限额为 {int(max_tokens):,} token"
    if fallback:
        msg += f"，额度用完后切换到 {fallback}"
    return json.dumps({"success": True, "message": msg}, ensure_ascii=False)


def handle_quota_reset(args: dict, **kwargs) -> str:
    """Reset usage counters for a model."""
    quota = get_quota()
    if quota is None:
        return json.dumps({"error": "Plugin not initialized"})

    model = args.get("model", "").strip()
    if not model:
        return json.dumps({"error": "缺少 model 参数"}, ensure_ascii=False)

    if model not in quota.data.get("models", {}):
        return json.dumps({"error": f"模型 {model} 未配置额度"}, ensure_ascii=False)

    quota.reset_usage(model)
    return json.dumps({"success": True, "message": f"已重置 {model} 的所有用量计数器"}, ensure_ascii=False)
