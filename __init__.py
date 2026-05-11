"""Auto Model Switch plugin — registration entry point."""

import logging
from pathlib import Path

from . import schemas, tools, hooks

logger = logging.getLogger(__name__)


def register(ctx):
    """Register plugin components with Hermes."""
    data_dir = Path(__file__).parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Initialize hooks module
    hooks.init(data_dir)

    # Register tools
    ctx.register_tool(
        name="model_quota_status",
        toolset="auto_model_switch",
        schema=schemas.MODEL_QUOTA_STATUS,
        handler=tools.handle_quota_status,
    )
    ctx.register_tool(
        name="model_quota_set",
        toolset="auto_model_switch",
        schema=schemas.MODEL_QUOTA_SET,
        handler=tools.handle_quota_set,
    )
    ctx.register_tool(
        name="model_quota_reset",
        toolset="auto_model_switch",
        schema=schemas.MODEL_QUOTA_RESET,
        handler=tools.handle_quota_reset,
    )

    # Register hooks
    ctx.register_hook("pre_llm_call", hooks.on_pre_llm_call)
    ctx.register_hook("post_api_request", hooks.on_post_api_request)
    ctx.register_hook("on_session_start", hooks.on_session_start)

    logger.info("Auto Model Switch v2.0 loaded (no proxy, direct switch)")
