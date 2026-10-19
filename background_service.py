"""
ZEB-Silencio 200T - Headless Background Auto-Tuner Service
Runs silently in the background, continuously watching for Bluetooth connection.
Immediately upon connection, automatically flashes the 'OnePlus Buds 3' EQ curve to the headphones.
"""

import os
import sys
import time
import signal
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.controller import HeadphoneController
from app.connection import find_silencio_com_port
from app import protocol

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background_service.log")

def log(msg: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    print(entry)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        pass

def notify_user(title: str, message: str):
    try:
        import pystray
        from PIL import Image
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "assets", "icon.ico")
        img = Image.open(ico) if os.path.exists(ico) else Image.new("RGBA", (16, 16), (37, 99, 235))
        icon = pystray.Icon("SilencioNotifier", img, title)
        icon.run_detached()
        time.sleep(0.1)
        icon.notify(message, title)
        time.sleep(1.0)
        icon.stop()
    except Exception:
        pass

def main():
    log("==================================================")
    log("ZEB-Silencio 200T Background Auto-Tuning Service Started.")
    log("Target Preset: OnePlus Buds 3 (+3, +4, +3, +2, +1, 0, -1, -3, -3, -2 dB)")
    log("Waiting for headphones to connect via Bluetooth...")
    log("==================================================")

    ctrl = HeadphoneController()
    running = True

    def sig_handler(sig, frame):
        nonlocal running
        log("Shutting down background service...")
        running = False
        ctrl.stop_auto_reconnect()
        ctrl.disconnect()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    was_connected = False

    while running:
        try:
            port = find_silencio_com_port() or "COM5"
            if not ctrl.is_connected:
                success = ctrl.connect(port, sync=True)
                if success:
                    log(f"Headphones connected on {port}! Automatically applied 'OnePlus Buds 3' EQ.")
                    notify_user("🎧 ZEB-Silencio 200T", "Connected! Automatically set EQ to OnePlus Buds 3.")
                    was_connected = True
            else:
                if not was_connected:
                    was_connected = True
            time.sleep(1.5)
        except KeyboardInterrupt:
            break
        except Exception as e:
            time.sleep(2.0)

    ctrl.disconnect()
    log("Background service stopped.")

if __name__ == "__main__":
    main()
