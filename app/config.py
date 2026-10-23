"""
Configuration Manager for ZEB-Silencio 200T
Manages persistent user settings, MAC address configuration, and Bluetooth device discovery.
"""

import os
import sys
import json
import re
import csv
import io
import subprocess
from typing import Dict, Any, List, Optional

CONFIG_DIR_NAME = "ZEB-Silencio-200T"
CONFIG_FILE_NAME = "config.json"
DEFAULT_MAC = "41:42:F3:8D:54:52"


def get_config_dir() -> str:
    """Returns the persistent configuration directory in %APPDATA%."""
    appdata = os.environ.get("APPDATA")
    if appdata and os.path.exists(appdata):
        cfg_dir = os.path.join(appdata, CONFIG_DIR_NAME)
    else:
        cfg_dir = os.path.join(os.path.expanduser("~"), f".{CONFIG_DIR_NAME.lower()}")
    os.makedirs(cfg_dir, exist_ok=True)
    return cfg_dir


def get_config_path() -> str:
    """Returns the full path to config.json."""
    return os.path.join(get_config_dir(), CONFIG_FILE_NAME)


def clean_mac(mac: Optional[str]) -> str:
    """Strips delimiters and converts to uppercase 12-char hex string."""
    if not mac:
        return ""
    return re.sub(r"[^0-9A-Fa-f]", "", str(mac)).upper()


def format_mac(mac: Optional[str]) -> str:
    """Formats a 12-char hex string to XX:XX:XX:XX:XX:XX."""
    cleaned = clean_mac(mac)
    if len(cleaned) == 12:
        return ":".join(cleaned[i:i+2] for i in range(0, 12, 2))
    return mac.strip() if mac else ""


def is_valid_mac(mac: Optional[str]) -> bool:
    """Returns True if the MAC address consists of exactly 12 hexadecimal characters."""
    cleaned = clean_mac(mac)
    return len(cleaned) == 12 and bool(re.match(r"^[0-9A-F]{12}$", cleaned))


def load_config() -> Dict[str, Any]:
    """Loads configuration from JSON file or returns defaults."""
    cfg_path = get_config_path()
    defaults = {
        "mac_address": "",
        "preferred_port": "",
        "auto_start": True,
        "default_preset": "OnePlus Buds 3",
        "custom_eq": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "custom_presets": {}
    }
    if os.path.exists(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    defaults.update(data)
        except Exception as e:
            print(f"[Config] Error loading config: {e}")
    return defaults


def save_config(data: Dict[str, Any]) -> bool:
    """Saves configuration dict to JSON file."""
    cfg_path = get_config_path()
    try:
        current = load_config()
        current.update(data)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=4)
        return True
    except Exception as e:
        print(f"[Config] Error saving config: {e}")
        return False


def get_mac_address() -> str:
    """Returns the stored formatted MAC address, or empty string if not configured."""
    cfg = load_config()
    mac = cfg.get("mac_address", "")
    return format_mac(mac) if is_valid_mac(mac) else ""


def set_mac_address(mac: str) -> bool:
    """Validates and stores the MAC address persistently."""
    if not is_valid_mac(mac):
        return False
    formatted = format_mac(mac)
    return save_config({"mac_address": formatted})


def has_configured_mac() -> bool:
    """Returns True if a valid MAC address is saved in configuration."""
    return is_valid_mac(get_mac_address())


def get_default_preset() -> str:
    """Returns the stored default EQ preset name."""
    cfg = load_config()
    return cfg.get("default_preset", "OnePlus Buds 3")


def set_default_preset(name: str) -> bool:
    """Stores the default EQ preset name persistently."""
    return save_config({"default_preset": name})


def get_custom_eq() -> List[int]:
    """Returns the stored custom 10-band EQ gains."""
    cfg = load_config()
    gains = cfg.get("custom_eq", [0] * 10)
    if isinstance(gains, list) and len(gains) == 10:
        return [int(g) for g in gains]
    return [0] * 10


def set_custom_eq(gains: List[int]) -> bool:
    """Stores custom 10-band EQ gains persistently."""
    return save_config({"custom_eq": [int(g) for g in gains[:10]]})


def get_custom_presets() -> Dict[str, List[int]]:
    """Returns dictionary of user-created custom EQ presets {name: [10 gains]}."""
    cfg = load_config()
    presets = cfg.get("custom_presets", {})
    return presets if isinstance(presets, dict) else {}


def save_custom_preset(name: str, gains: List[int]) -> bool:
    """Stores a named custom EQ preset persistently."""
    if not name or not name.strip():
        return False
    clean_name = name.strip()
    presets = get_custom_presets()
    presets[clean_name] = [int(g) for g in gains[:10]]
    return save_config({"custom_presets": presets, "custom_eq": [int(g) for g in gains[:10]]})


def delete_custom_preset(name: str) -> bool:
    """Deletes a custom EQ preset by name."""
    presets = get_custom_presets()
    if name in presets:
        del presets[name]
        # If deleted preset was the configured default, fallback to OnePlus Buds 3
        if get_default_preset() == name:
            set_default_preset("OnePlus Buds 3")
        return save_config({"custom_presets": presets})
    return False


def discover_paired_bluetooth_devices() -> List[Dict[str, Any]]:
    """
    Scans paired Bluetooth devices via Windows PnP and returns a list of
    detected devices with their FriendlyName and formatted MAC address.
    Prioritizes devices with names matching Silencio / ZEB / Headphones.
    """
    devices: List[Dict[str, Any]] = []
    seen_macs = set()

    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            'Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName, InstanceId | ConvertTo-Csv -NoTypeInformation'
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            reader = csv.reader(io.StringIO(res.stdout))
            next(reader, None)  # Skip header
            for row in reader:
                if len(row) < 2:
                    continue
                friendly_name = row[0].strip('"\r ')
                instance_id = row[1].upper()

                # Skip non-device transports / services
                if (friendly_name.endswith("Transport") or
                    friendly_name.startswith("Device ") or
                    friendly_name.startswith("Service ") or
                    friendly_name.startswith("Generic ") or
                    friendly_name.startswith("Bluetooth ") or
                    friendly_name.startswith("Microsoft ") or
                    friendly_name.startswith("Intel")):
                    continue

                m = re.search(r"DEV_([0-9A-F]{12})", instance_id)
                if m:
                    raw_mac = m.group(1)
                    if raw_mac not in seen_macs:
                        seen_macs.add(raw_mac)
                        formatted = format_mac(raw_mac)
                        is_target = any(k in friendly_name.lower() for k in ["silencio", "zeb", "x1040", "x-1040"])
                        devices.append({
                            "name": friendly_name,
                            "mac": formatted,
                            "clean_mac": raw_mac,
                            "is_target": is_target
                        })
    except Exception as e:
        print(f"[Discovery] Error querying Bluetooth devices: {e}")

    # Sort so target devices appear first
    devices.sort(key=lambda d: (not d.get("is_target", False), d.get("name", "")))
    return devices
