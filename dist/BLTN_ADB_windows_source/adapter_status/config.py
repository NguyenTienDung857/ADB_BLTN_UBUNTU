import json
import os

from .constants import CONFIG_DIR, CONFIG_FILE, DEFAULT_CONFIG
from .host_platform import sanitize_iface_value

def sanitize_iface(value, fallback=DEFAULT_CONFIG["iface"]):
    return sanitize_iface_value(value, fallback)


def load_config():
    config = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        for key in DEFAULT_CONFIG:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                config[key] = sanitize_iface(value) if key == "iface" else value.strip()
    except (OSError, json.JSONDecodeError):
        pass
    return config


def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    safe_config = {key: str(config.get(key, DEFAULT_CONFIG[key])).strip() for key in DEFAULT_CONFIG}
    safe_config["iface"] = sanitize_iface(safe_config["iface"])
    with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
        json.dump(safe_config, handle, indent=2, sort_keys=True)

def host_ip_from_cidr(host_cidr):
    return host_cidr.split("/", 1)[0].strip()


def adb_target(config):
    return f"{config['device_ip']}:{config['adb_port']}"
