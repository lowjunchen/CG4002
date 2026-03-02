# HLS Control register map for ap_ctrl_hs
AP_CTRL = 0x00
AP_START_MASK = 0x01
AP_DONE_MASK = 0x02
AP_IDLE_MASK = 0x04

def start(accel):
    """Starts the accelerator by writing to the control register."""
    accel.write(AP_CTRL, AP_START_MASK)

def wait_for_done(accel, timeout=10_000_000):
    """Waits for the accelerator to finish by polling the control register."""
    for _ in range(timeout):
        v = accel.read(AP_CTRL)
        if (v & AP_DONE_MASK) or (v & AP_IDLE_MASK):
            return True
    return False