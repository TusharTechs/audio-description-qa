"""Quality checks for machine-written audio description."""

__version__ = "0.2.0"
__all__ = [
    "check",
    "check_bundle",
    "analyse",
    "worth_checking",
    "describe_for_prompt",
]


def __getattr__(name):
    if name in ("check", "check_bundle"):
        from . import preflight
        return getattr(preflight, name)
    if name in ("analyse", "worth_checking", "describe_for_prompt"):
        from . import audio_events
        return getattr(audio_events, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
