import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests

from Config import settings
from Logger import logger


class OllamaSetupError(Exception):
    pass


# ---------- Detection ----------

def find_ollama_executable() -> str:
    path = shutil.which("ollama")
    if path:
        logger.info(f"Ollama found in PATH: {path}")
        return path

    common_paths = []

    if sys.platform.startswith("win"):
        common_paths = [
            r"C:\Program Files\Ollama\ollama.exe",
            r"C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama.exe",
        ]
    elif sys.platform == "darwin":
        common_paths = [
            "/usr/local/bin/ollama",
            "/opt/homebrew/bin/ollama",
            "/Applications/Ollama.app/Contents/Resources/ollama",
        ]
    else:
        common_paths = [
            "/usr/bin/ollama",
            "/usr/local/bin/ollama",
        ]

    for raw_path in common_paths:
        expanded = os.path.expandvars(raw_path)
        if Path(expanded).exists():
            logger.info(f"Ollama found at: {expanded}")
            return expanded

    raise OllamaSetupError("Ollama is not installed.")


# ---------- Port / Health ----------

def is_port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) == 0


def check_server_health(base_url: str) -> bool:
    try:
        r = requests.get(f"{base_url}/api/tags", timeout=3)
        return r.status_code == 200
    except:
        return False


# ---------- Server Control ----------

def start_ollama_server(executable_path: str):
    env = os.environ.copy()
    env["OLLAMA_HOST"] = f"{settings.ollama_host}:{settings.ollama_port}"

    logger.info("Starting Ollama server...")

    creation_flags = 0
    if sys.platform.startswith("win"):
        creation_flags = subprocess.CREATE_NO_WINDOW

    return subprocess.Popen(
        [executable_path, "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        creationflags=creation_flags,
    )


def wait_for_server(base_url: str, timeout: int) -> bool:
    start = time.time()

    while time.time() - start < timeout:
        if check_server_health(base_url):
            logger.info("Ollama server is ready")
            return True
        time.sleep(1)

    return False


# ---------- Model Handling ----------

def list_models(base_url: str):
    r = requests.get(f"{base_url}/api/tags")
    r.raise_for_status()
    data = r.json()
    return [m["name"] for m in data.get("models", [])]


def model_exists(base_url: str, model_name: str) -> bool:
    models = list_models(base_url)
    return model_name in models


def pull_model(base_url: str, model_name: str):
    logger.info(f"Pulling model: {model_name}")
    r = requests.post(
        f"{base_url}/api/pull",
        json={"name": model_name, "stream": False},
        timeout=settings.ollama_pull_timeout
    )
    r.raise_for_status()


def ensure_model(base_url: str, model_name: str):
    if not model_exists(base_url, model_name):
        pull_model(base_url, model_name)


# ---------- Full Bootstrap ----------

def bootstrap_ollama() -> dict[str, Any]:
    base_url = settings.ollama_base_url

    # Try reusing existing server if one is already running
    if check_server_health(base_url):
        logger.info("Using existing Ollama server")
        ensure_model(base_url, settings.ollama_model)
        return {
            "base_url": base_url,
            "model": settings.ollama_model,
            "status": "Connected to existing server"
        }

    # Start fresh
    exe = find_ollama_executable()
    process = start_ollama_server(exe)

    if not wait_for_server(base_url, settings.ollama_startup_timeout):
        process.terminate()
        raise OllamaSetupError("Ollama failed to start")

    ensure_model(base_url, settings.ollama_model)

    return {
        "base_url": base_url,
        "model": settings.ollama_model,
        "status": "Started new Ollama server"
    }


# ---------- Prompt + Chat ----------

def build_prompt(draft: str, tone: str) -> str:
    return f"""
You are Whetstone AI.

Improve the writing using a {tone} tone.

Return ONLY JSON:

{{
  "subject": "...",
  "improved_version": "...",
  "feedback": ["...", "..."]
}}

Text:
{draft}
""".strip()


def improve_with_ollama(base_url: str, model: str, draft: str, tone: str):
    prompt = build_prompt(draft, tone)

    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "format": "json"
    }

    r = requests.post(f"{base_url}/api/chat", json=body)
    r.raise_for_status()

    data = r.json()

    raw = data["message"]["content"].strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start:end + 1])
        except json.JSONDecodeError:
            pass
    
    logger.error(f"Raw Ollama output was not valid JSON: {raw}")
    raise OllamaSetupError("Invalid AI response format")