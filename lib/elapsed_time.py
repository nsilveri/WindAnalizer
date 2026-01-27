import time

elapsed_time_ms = time.ticks_ms()

def elapsed_time(time_interval=1000):
    global elapsed_time_ms
    current_time = time.ticks_ms()
    if current_time - elapsed_time_ms >= time_interval:
        elapsed_time_ms = current_time
        return True
    return False