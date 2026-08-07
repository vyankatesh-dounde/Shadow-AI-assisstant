# core/system_status.py
#
# Small helper the web dashboard polls/broadcasts so every connected
# device can see what the host PC is doing right now.

import psutil

try:
    import pygetwindow as gw
except Exception:
    gw = None


def get_active_window_title():
    if gw is None:
        return None
    try:
        win = gw.getActiveWindow()
        return win.title if win else None
    except Exception:
        return None


def get_status():
    try:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        battery = None
        try:
            b = psutil.sensors_battery()
            if b:
                battery = round(b.percent)
        except Exception:
            pass

        return {
            "cpu": cpu,
            "memory": mem,
            "battery": battery,
            "active_window": get_active_window_title(),
            "uptime_seconds": int(psutil.boot_time()),
        }
    except Exception as e:
        return {"error": str(e)}
