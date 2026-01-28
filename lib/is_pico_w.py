def is_pico_w():
    try:
        import network
        return True
    except ImportError:
        return False