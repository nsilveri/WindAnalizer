"""Minimal warnings shim for MicroPython.

Provides a `warn()` function used by some stdlib-like modules.
"""
__all__ = ("warn",)

def warn(message, category=None, stacklevel=1):
    try:
        print("Warning:", message)
    except Exception:
        # Best-effort: don't raise from the warning system
        pass
