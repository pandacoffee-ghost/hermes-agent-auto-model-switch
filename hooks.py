"""Hook implementations for auto model switching."""

import logging
from pathlib import Path

from .detector import detect_content_types
from .quota import QuotaManager
from .switcher import get_state, switch_for_content, switch_back, do_switch, reset_state

logger = logging.getLogger(__name__)

# Module state
_quota: QuotaManager = None
_first_session = False
_TEXT_TURNS_TO_SWITCH_BACK = 2


def init(data_dir: Path):
    """Initialize hooks module with data directory."""
    global _quota
    _quota = QuotaManager(data_dir)


def get_quota() -> QuotaManager:
    return _quota


def _model_supports_vision(model: str, provider: str) -> bool:
    """Check if model supports vision via models.dev catalog."""
    try:
        from agent.models_dev import get_model_capabilities
        caps = get_model_capabilities(provider, model)
        if caps:
            return caps.supports_vision
    except Exception:
        pass
    # Fallback: known vision model patterns
    model_lower = model.lower()
    vision_keywords = ["vision", "omni", "4o", "gpt-4", "claude-3", "gemini", "qwen-vl", "glm-4v"]
    return any(kw in model_lower for kw in vision_keywords)


def on_session_start(session_id, model, platform, **kwargs):
    """Mark session start for first-use detection."""
    global _first_session
    _first_session = True
    reset_state()


def on_pre_llm_call(session_id, user_message, conversation_history,
                     is_first_turn, model, platform, **kwargs):
    """Core logic: detect content, check quotas, switch if needed.

    Returns context injection dict or None.
    """
    if _quota is None:
        return None

    notifications = []

    # --- 1. Content type detection & vision/audio switching ---
    content_types = detect_content_types(conversation_history)
    state = get_state()

    # Get current agent info
    try:
        from hermes_cli.plugins import get_plugin_manager
        cli = get_plugin_manager()._cli_ref
        current_model = cli.model if cli else model
        current_provider = cli.provider if cli else ""
    except Exception:
        current_model = model
        current_provider = ""

    if "vision" in content_types or "audio" in content_types:
        # Reset text turn counter if we're already in a content switch
        if state.switch_reason in ("vision", "audio"):
            state.text_turns_since_switch = 0

        # Check if current model supports the content type
        needs_switch = False
        if "vision" in content_types and not _model_supports_vision(current_model, current_provider):
            needs_switch = True
            needed_cap = "vision"

        if needs_switch:
            # Find a vision-capable model from quota config or known models
            vision_model = _find_capable_model(needed_cap, current_model)
            if vision_model and vision_model != current_model:
                ok = switch_for_content(vision_model, needed_cap, current_model, current_provider)
                if ok:
                    notifications.append(
                        f"[Auto Model Switch] 检测到{needed_cap}内容，当前模型 {current_model} 不支持，"
                        f"已自动切换到 {vision_model}。对话继续，无需重新开始。"
                    )
    else:
        # Pure text — check if we should switch back
        if state.switch_reason in ("vision", "audio"):
            state.text_turns_since_switch += 1
            if state.text_turns_since_switch >= _TEXT_TURNS_TO_SWITCH_BACK:
                old_model = current_model
                ok = switch_back()
                if ok:
                    notifications.append(
                        f"[Auto Model Switch] 连续 {_TEXT_TURNS_TO_SWITCH_BACK} 轮纯文本，"
                        f"已从 {old_model} 切回 {state.original_model or '原始模型'}。"
                    )

    # --- 2. Quota check ---
    # Re-read current model (may have changed from step 1)
    try:
        cli = get_plugin_manager()._cli_ref
        current_model = cli.model if cli else model
    except Exception:
        pass

    if _quota.is_exhausted(current_model):
        fallback = _quota.get_fallback(current_model)
        if fallback:
            ok = do_switch(fallback)
            if ok:
                notifications.append(
                    f"[Auto Model Switch] 模型 {current_model} 额度已用完，"
                    f"已自动切换到 {fallback}。你可以通过对话重新设置额度或切换模型。"
                )
        else:
            notifications.append(
                f"[Auto Model Switch] ⚠️ 模型 {current_model} 额度已用完，"
                f"且未配置 fallback 模型。请通过对话设置新的模型或重置额度。"
            )

    # --- 3. First-use guidance ---
    global _first_session
    if _first_session and is_first_turn and not _quota.has_any_quota():
        _first_session = False
        notifications.append(
            "[Auto Model Switch 插件已加载] 你可以为模型设置用量额度，到额度后自动切换。\n"
            "示例：\n"
            "- \"给 deepseek-v4-flash 设日限额 200 万 token，用完切 LongCat-Flash-Chat\"\n"
            "- \"给 LongCat-Flash-Chat 设月限额 5000 万 token\"\n"
            "- \"查看模型额度状态\"\n"
            "如果不需要额度管理，忽略此消息即可。插件仍会在检测到图片/音频时自动切换到支持的模型。"
        )
    elif _first_session:
        _first_session = False

    if notifications:
        return {"context": "\n\n".join(notifications)}
    return None


def on_post_api_request(model, usage, **kwargs):
    """Record real token usage from API response."""
    if _quota is None or usage is None:
        return
    total = usage.get("total_tokens", 0)
    if total > 0:
        _quota.record_usage(model, total)


def _find_capable_model(capability: str, current_model: str) -> str:
    """Find a model that supports the given capability.

    Checks quota config for models, then tries known vision models.
    """
    # First check if any model in our quota config supports vision
    if _quota:
        for model_name in _quota.data.get("models", {}):
            if model_name == current_model:
                continue
            try:
                from hermes_cli.plugins import get_plugin_manager
                cli = get_plugin_manager()._cli_ref
                provider = cli.provider if cli else ""
            except Exception:
                provider = ""
            if capability == "vision" and _model_supports_vision(model_name, provider):
                return model_name

    # Fallback: try well-known vision models
    if capability == "vision":
        known_vision = [
            "anthropic/claude-sonnet-4",
            "google/gemini-2.5-flash",
            "openai/gpt-4o",
            "qwen-vl-max",
        ]
        for m in known_vision:
            if m != current_model:
                return m

    return ""
