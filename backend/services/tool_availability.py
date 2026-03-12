"""Check which optional tools are installed. Results cached at startup."""

_cache = {}


def check_tool(name: str) -> bool:
    if name in _cache:
        return _cache[name]

    available = False
    try:
        if name == "whisperx":
            import whisperx  # noqa: F401
            available = True
        elif name == "stable_ts":
            import stable_whisper  # noqa: F401
            available = True
        elif name == "auto_editor":
            import subprocess
            result = subprocess.run(
                ["auto-editor", "--help"],
                capture_output=True, timeout=5,
            )
            available = result.returncode == 0
        elif name == "pycaps":
            import pycaps  # noqa: F401
            available = True
        elif name == "moviepy":
            from moviepy import VideoFileClip  # noqa: F401
            available = True
    except Exception:
        pass

    _cache[name] = available
    return available


def get_available_tools() -> dict:
    """Return availability of all optional tools."""
    tools = ["whisperx", "stable_ts", "auto_editor", "pycaps", "moviepy"]
    return {t: check_tool(t) for t in tools}


def require_tool(name: str):
    """Raise ImportError if tool is not available."""
    if not check_tool(name):
        raise ImportError(f"{name} is not installed. Install it to use this feature.")
