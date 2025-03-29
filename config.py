import json
import os

CONFIG_FILE = "config.json"
DEFAULTS = {
    "PROXMOX_HOST": "",
    "PROXMOX_PORT": "8006",
    "PROXMOX_USER": "",
    "PROXMOX_TOKEN_NAME": "",
    "PROXMOX_TOKEN_VALUE": "",
    "VERIFY_SSL": True
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return DEFAULTS.copy()

def save_config(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)
