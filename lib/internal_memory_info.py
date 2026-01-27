import gc

def print_memory_info():
    try:
        gc.collect()
        free = gc.mem_free()
        allocated = gc.mem_alloc()
        total = free + allocated
        print("======== Memory ========\nFree: {} bytes\nAllocated: {} bytes\nTotal: {} bytes".format(free, allocated, total))
    except Exception as e:
        print("Failed to get memory info:", e)