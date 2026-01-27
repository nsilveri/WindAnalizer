"""Minimal path helpers for environments without full `os.path`.

Provides `dirname`, `join`, `exists`, `makedirs` and `isdir` using `os`.
Suitable for MicroPython / limited stdlib environments.
"""
import os

def dirname(p):
    if not p:
        return ''
    # normalize to use forward slashes internally
    p = p.replace('\\', '/')
    if '/' not in p:
        return ''
    return p.rsplit('/', 1)[0]

def join(*parts):
    segs = []
    for part in parts:
        if not part:
            continue
        part = part.replace('\\', '/')
        segs.append(part.strip('/'))
    if not segs:
        return ''
    return '/'.join(segs)

def exists(p):
    try:
        os.stat(p)
        return True
    except Exception:
        return False

def isdir(p):
    try:
        st = os.stat(p)
        # Check directory bit if available
        return (st[0] & 0o170000) == 0o040000
    except Exception:
        return False

def makedirs(p):
    if not p:
        return
    parent = dirname(p)
    if parent and not exists(parent):
        makedirs(parent)
    if not exists(p):
        try:
            os.mkdir(p)
        except Exception:
            pass
