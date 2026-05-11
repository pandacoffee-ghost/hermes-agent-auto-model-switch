"""Model switcher — wraps Hermes internal switch_model API."""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SwitchState:
    """Tracks the current switch state for smart switch-back."""
    original_model: str = ""
    original_provider: str = ""
    switch_reason: str = ""  # "vision", "audio", "quota"
    text_turns_since_switch: int = 0


# Module-level state
_state = SwitchState()

# Cached model registry: model_name -> {provider, base_url, api_key_env, ...}
_model_registry: dict = {}


def get_state() -> SwitchState:
    return _state


def reset_state():
    global _state
    _state = SwitchState()


def _build_model_registry() -> dict:
    """Build a model->provider mapping from Hermes config.

    Scans config.yaml's `providers:` and `custom_providers:` sections
    to create a lookup table. This way we can resolve any model name
    to its correct provider + credentials regardless of how the user
    describes it.

    Returns dict like:
        {
            "deepseek-v4-flash": {"provider": "deepseek", "base_url": "...", "key_env": "..."},
            "LongCat-Flash-Chat": {"provider": "longcat", "base_url": "...", "key_env": "..."},
            ...
        }
    """
    registry = {}
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
    except Exception as e:
        logger.debug("Cannot load config: %s", e)
        return registry

    # Scan providers: section
    providers = cfg.get("providers", {})
    if isinstance(providers, dict):
        for pname, pcfg in providers.items():
            if not isinstance(pcfg, dict):
                continue
            base_url = pcfg.get("base_url", "")
            key_env = pcfg.get("key_env", "")
            api_mode = pcfg.get("api_mode", "chat_completions")

            entry = {"provider": pname, "base_url": base_url, "key_env": key_env, "api_mode": api_mode}

            # Register default_model
            default_model = pcfg.get("default_model", "")
            if default_model:
                registry[default_model] = entry

            # Register all models in models: dict
            models = pcfg.get("models", {})
            if isinstance(models, dict):
                for model_name in models:
                    registry[model_name] = entry
            elif isinstance(models, list):
                for m in models:
                    if isinstance(m, str):
                        registry[m] = entry

    # Scan custom_providers: section
    custom = cfg.get("custom_providers", [])
    if isinstance(custom, list):
        for cp in custom:
            if not isinstance(cp, dict):
                continue
            name = cp.get("name", "")
            base_url = cp.get("base_url", "")
            key_env = cp.get("key_env", "")
            api_key = cp.get("api_key", "")
            model = cp.get("model", "")
            entry = {"provider": name, "base_url": base_url, "key_env": key_env, "api_key": api_key}
            if model:
                registry[model] = entry
            models = cp.get("models", {})
            if isinstance(models, dict):
                for m in models:
                    registry[m] = entry

    logger.info("Model registry built: %s", list(registry.keys()))
    return registry


def get_model_registry() -> dict:
    """Get or build the model registry (cached)."""
    global _model_registry
    if not _model_registry:
        _model_registry = _build_model_registry()
    return _model_registry


def refresh_registry():
    """Force rebuild of model registry (call after config changes)."""
    global _model_registry
    _model_registry = _build_model_registry()


def resolve_model(user_input: str) -> tuple:
    """Resolve a user-provided model name to (exact_model_name, provider).

    Tries exact match first, then case-insensitive, then substring match.
    Returns ("", "") if not found.
    """
    registry = get_model_registry()

    # Exact match
    if user_input in registry:
        return user_input, registry[user_input]["provider"]

    # Case-insensitive match
    input_lower = user_input.lower()
    for model_name, info in registry.items():
        if model_name.lower() == input_lower:
            return model_name, info["provider"]

    # Substring/fuzzy match (user said "longcat" or "flash-chat")
    for model_name, info in registry.items():
        if input_lower in model_name.lower() or model_name.lower() in input_lower:
            return model_name, info["provider"]

    return "", ""


def _get_agent():
    """Get the running agent instance via plugin manager or gateway cache.

    Works in both CLI mode (_cli_ref.agent) and gateway mode
    (_gateway_runner_ref._agent_cache lookup by session context).
    """
    # Try CLI mode first
    try:
        from hermes_cli.plugins import get_plugin_manager
        cli = get_plugin_manager()._cli_ref
        if cli and hasattr(cli, "agent") and cli.agent is not None:
            return cli.agent
    except Exception:
        pass

    # Try gateway mode: find agent in cache via session context var
    try:
        from gateway.run import _gateway_runner_ref
        runner = _gateway_runner_ref()
        if runner is None:
            return None
        cache = getattr(runner, "_agent_cache", None)
        lock = getattr(runner, "_agent_cache_lock", None)
        if cache is None:
            return None

        # Get current session key from context var
        from gateway.session_context import _SESSION_KEY
        session_key = _SESSION_KEY.get(None)
        if session_key and session_key != "":
            if lock:
                with lock:
                    entry = cache.get(session_key)
            else:
                entry = cache.get(session_key)
            if entry and entry[0] is not None:
                return entry[0]

        # Fallback: search by session_id (passed to hook via kwargs)
        # This is set by _find_agent_by_session_id below
        if _current_session_agent:
            return _current_session_agent
    except Exception as e:
        logger.debug("Gateway agent lookup failed: %s", e)

    return None


# Thread-local-ish storage for gateway mode agent lookup
_current_session_agent = None


def set_current_agent_for_session(session_id: str):
    """Called from hooks to help locate the agent in gateway mode.

    In gateway mode, we search the agent cache for the agent with
    matching session_id.
    """
    global _current_session_agent
    try:
        from gateway.run import _gateway_runner_ref
        runner = _gateway_runner_ref()
        if runner is None:
            return
        cache = getattr(runner, "_agent_cache", None)
        lock = getattr(runner, "_agent_cache_lock", None)
        if cache is None:
            return
        if lock:
            with lock:
                for key, entry in cache.items():
                    if entry and entry[0] and getattr(entry[0], "session_id", None) == session_id:
                        _current_session_agent = entry[0]
                        return
        else:
            for key, entry in cache.items():
                if entry and entry[0] and getattr(entry[0], "session_id", None) == session_id:
                    _current_session_agent = entry[0]
                    return
    except Exception:
        pass


def _get_cli():
    """Get the CLI instance (None in gateway mode)."""
    try:
        from hermes_cli.plugins import get_plugin_manager
        return get_plugin_manager()._cli_ref
    except Exception:
        return None


def do_switch(model: str, provider: str = "") -> bool:
    """Switch the running agent to a new model.

    If provider is not given, resolves it from the model registry.
    Uses hermes_cli.model_switch.switch_model() to resolve credentials,
    then calls agent.switch_model() to perform the runtime swap.

    Returns True on success.
    """
    agent = _get_agent()
    if agent is None:
        logger.warning("No agent available for model switch")
        return False

    cli = _get_cli()
    current_provider = getattr(agent, "provider", "") or ""
    current_model = getattr(agent, "model", "") or ""
    current_base_url = getattr(agent, "base_url", "") or ""
    current_api_key = getattr(agent, "api_key", "") or ""

    # Resolve model name and provider from registry
    exact_model, resolved_provider = resolve_model(model)
    if exact_model:
        model = exact_model
    if not provider and resolved_provider:
        provider = resolved_provider
        logger.info("Resolved model '%s' → provider '%s' from config", model, provider)

    # Get user_providers and custom_providers from config
    try:
        from hermes_cli.config import load_config
        cfg = load_config()
        user_providers = cfg.get("providers", {})
        custom_providers = cfg.get("custom_providers", [])
    except Exception:
        user_providers = {}
        custom_providers = []

    try:
        from hermes_cli.model_switch import switch_model
        result = switch_model(
            raw_input=model,
            current_provider=current_provider,
            current_model=current_model,
            current_base_url=current_base_url,
            current_api_key=current_api_key,
            explicit_provider=provider,
            user_providers=user_providers,
            custom_providers=custom_providers,
        )
    except Exception as e:
        logger.warning("model_switch.switch_model failed: %s", e)
        return False

    if not result.success:
        logger.warning("Switch to %s (provider=%s) failed: %s", model, provider, result.error_message)
        return False

    # Apply the switch — mirror what Hermes _apply_model_switch_result does
    try:
        old_model = getattr(agent, "model", "")
        agent.switch_model(
            new_model=result.new_model,
            new_provider=result.target_provider,
            api_key=result.api_key,
            base_url=result.base_url,
            api_mode=result.api_mode,
        )
        # Update CLI state (mirrors _apply_model_switch_result exactly)
        if cli:
            cli.model = result.new_model
            cli.provider = result.target_provider
            cli.requested_provider = result.target_provider
            cli._explicit_api_key = result.api_key
            cli._explicit_base_url = result.base_url
            if result.api_key:
                cli.api_key = result.api_key
            if result.base_url:
                cli.base_url = result.base_url
            if result.api_mode:
                cli.api_mode = result.api_mode
            # This note is prepended to the next user message so the LLM
            # knows the model changed.
            cli._pending_model_switch_note = (
                f"[Note: model was just auto-switched from {old_model} to {result.new_model} "
                f"via {result.provider_label or result.target_provider}. "
                f"Adjust your self-identification accordingly.]"
            )
        else:
            # Gateway mode: persist override so next turn uses the new model
            try:
                from gateway.run import _gateway_runner_ref
                from gateway.session_context import _SESSION_KEY
                runner = _gateway_runner_ref()
                session_key = _SESSION_KEY.get(None)
                if runner and session_key:
                    overrides = getattr(runner, "_session_model_overrides", {})
                    overrides[session_key] = {
                        "model": result.new_model,
                        "provider": result.target_provider,
                        "api_key": result.api_key,
                        "base_url": result.base_url,
                        "api_mode": result.api_mode,
                    }
                    # Also set pending note for gateway
                    notes = getattr(runner, "_pending_model_notes", None)
                    if notes is None:
                        runner._pending_model_notes = {}
                        notes = runner._pending_model_notes
                    notes[session_key] = (
                        f"[Note: model was just auto-switched from {old_model} to {result.new_model} "
                        f"via {result.provider_label or result.target_provider}. "
                        f"Adjust your self-identification accordingly.]"
                    )
            except Exception as e:
                logger.debug("Gateway override failed (non-critical): %s", e)

        # Print visible notification to terminal (CLI only, no-op in gateway)
        if cli:
            try:
                from hermes_cli.banner import cprint as _cprint
                _cprint(f"  ⚡ Auto-switch: {old_model} → {result.new_model} ({result.provider_label or result.target_provider})")
            except Exception:
                pass

        logger.info("Switched to %s (%s) successfully", result.new_model, result.target_provider)
        return True
    except Exception as e:
        logger.warning("agent.switch_model failed: %s", e)
        return False


def switch_for_content(model: str, reason: str, current_model: str, current_provider: str) -> bool:
    """Switch model due to content type mismatch. Records state for switch-back."""
    _state.original_model = current_model
    _state.original_provider = current_provider
    _state.switch_reason = reason
    _state.text_turns_since_switch = 0
    return do_switch(model)


def switch_back() -> bool:
    """Switch back to original model after content-based switch."""
    if not _state.original_model:
        return False
    ok = do_switch(_state.original_model, _state.original_provider)
    if ok:
        reset_state()
    return ok
