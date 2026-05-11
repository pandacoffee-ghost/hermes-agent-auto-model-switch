"""Content type detector for conversation messages."""


def detect_content_types(conversation_history: list) -> set:
    """Detect content types in the last user message.

    Scans the most recent user message's content parts for multimedia.
    Returns a set like {"text"}, {"vision"}, {"text", "vision"}, {"audio"}, etc.
    """
    # Find last user message
    last_user = None
    for msg in reversed(conversation_history):
        if msg.get("role") == "user":
            last_user = msg
            break

    if last_user is None:
        return {"text"}

    content = last_user.get("content", "")

    if isinstance(content, str):
        return {"text"}

    if not isinstance(content, list):
        return {"text"}

    types = set()
    for part in content:
        if not isinstance(part, dict):
            continue
        ptype = part.get("type", "")
        if ptype in ("image_url", "input_image", "image"):
            types.add("vision")
        elif ptype == "input_audio":
            types.add("audio")
        elif ptype == "text":
            types.add("text")

    return types if types else {"text"}
