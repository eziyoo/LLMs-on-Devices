"""Shared settings for RunnerConfig.py and the helper scripts (read from experiment/config.ini)."""
import configparser
import subprocess
from os.path import dirname, realpath
from pathlib import Path

ROOT_DIR = Path(dirname(realpath(__file__)))
CONFIG_FILE = ROOT_DIR / 'config.ini'

# GGUF file -> run ID. The run ID names the results folder and the published table in data/runs/.
MODEL_RUN_IDS = {
    "qwen2-0_5b-instruct-q4_k_m.gguf":          "1_qwen2-0_5b_Q4_K_M",
    "qwen2.5-1.5b-instruct-q4_k_m.gguf":        "2_qwen2.5-1.5b_Q4_K_M",
    "phi-2.Q4_K_M.gguf":                        "3_phi-2_Q4_K_M",
    "qwen2.5-3b-instruct-q4_k_m.gguf":          "4_qwen2.5-3b_Q4_K_M",
    "OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf":    "5_OLMoE_Q4_K_M",
    "qwen2.5-7b-instruct-q4_k_m.gguf":          "6_qwen2.5-7b_Q4_K_M",
    "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf":   "7_llama_Q4_K_M",
    "gemma-2-9b-it-Q4_K_M.gguf":                "8_gemma_Q4_K_M",
    "Qwen2-0.5b-instruct-iq4_xs.gguf":          "9_qwen2-0_5b_IQ4_XS",
    "Qwen2.5-1.5B-Instruct-IQ4_XS.gguf":        "10_qwen2.5-1.5b_IQ4_XS",
    "Phi-2-iq4_xs.gguf":                        "11_phi-2_IQ4_XS",
    "Qwen2.5-3B-Instruct-IQ4_XS.gguf":          "12_qwen2.5-3b_IQ4_XS",
    "OLMoE-1B-7B-0125-Instruct-i1-IQ4_XS.gguf": "13_OLMoE_IQ4_XS",
    "Qwen2.5-7B-Instruct-IQ4_XS.gguf":          "14_qwen2.5-7b_IQ4_XS",
    "Meta-Llama-3.1-8B-Instruct-IQ4_XS.gguf":   "15_llama_IQ4_XS",
    "gemma-2-9b-it-IQ4_XS.gguf":                "16_gemma_IQ4_XS",
}

COMPANION_PACKAGE = "com.example.batterymanager_utility"
COMPANION_SERVICE = f"{COMPANION_PACKAGE}/{COMPANION_PACKAGE}.DataCollectionService"
BATTERY_FIELDS = "BATTERY_PROPERTY_CURRENT_NOW,EXTRA_VOLTAGE,BATTERY_PROPERTY_CAPACITY,EXTRA_TEMPERATURE"


def load_settings():
    if not CONFIG_FILE.exists():
        raise FileNotFoundError(
            f"{CONFIG_FILE} not found. Copy experiment/config.example.ini to experiment/config.ini and edit it.")
    parser = configparser.ConfigParser()
    parser.read(CONFIG_FILE)
    return parser


def adb(settings, *args, **kwargs):
    """Run `adb -s <device_id> <args...>` and return the CompletedProcess."""
    cmd = [settings.get("device", "adb_path", fallback="adb"), "-s", settings.get("device", "device_id"), *args]
    return subprocess.run(cmd, **kwargs)
