import json
import os
import tempfile

CONFIG_FILE = "data/config.json"
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
    dir_name = os.path.dirname(os.path.abspath(CONFIG_FILE))
    with tempfile.NamedTemporaryFile(mode="w", dir=dir_name, suffix=".tmp", delete=False) as f:
        json.dump(data, f, indent=4)
        tmp_path = f.name
    os.replace(tmp_path, CONFIG_FILE)
