"""Minimal `abc` shim for MicroPython.

Provides `ABC` and `abstractmethod` used by libraries expecting the stdlib
`abc` module. This is a best-effort shim that does not enforce abstract
method checks, but allows imports to succeed.
"""

def abstractmethod(func):
    try:
        func.__isabstract__ = True
    except Exception:
        # Some MicroPython builds don't allow setting attributes on
        # function objects; silently ignore in that case.
        pass
    return func


class ABC:
    """Base class placeholder for abstract base classes."""
    pass
