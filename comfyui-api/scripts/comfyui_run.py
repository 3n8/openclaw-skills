#!/usr/bin/env python3
"""
ComfyUI remote runner for OpenClaw skill - agent-robust with configurable server.
Supports config.yml host profiles plus CLI overrides:
- --server http://host:port (full URL override)
- --host <profile-name-or-hostname>
- --port <port>
Always returns structured JSON.
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote


SKILL_BASE_CANDIDATES = [
    Path("/home/en/.openclaw/skills/comfyui-api"),
    Path("/home/en/.openclaw/skills/comfyui"),  # backward compatibility for local installs not yet renamed
    Path("/home/en/git/openclaw-skills/comfyui-api"),  # local repo testing
]


def resolve_skill_base() -> Path:
    for candidate in SKILL_BASE_CANDIDATES:
        if candidate.exists():
            return candidate.resolve()
    # Default to the new runtime path even if not installed yet
    return SKILL_BASE_CANDIDATES[0].resolve()


SKILL_BASE = resolve_skill_base()
ASSETS_DIR = SKILL_BASE / "assets"
CONFIG_PATH = SKILL_BASE / "config.yml"


def resolve_default_workflow() -> Path:
    candidates = [
        ASSETS_DIR / "imagegen_workflow.json",
        ASSETS_DIR / "default-workflow.json",
        ASSETS_DIR / "default-workflow-realistic.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


DEFAULT_WORKFLOW = resolve_default_workflow()
DEFAULT_DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/ComfyUI"))
DEFAULT_LOG_DIR = Path(os.path.expanduser("~/.openclaw/logs/ComfyUI"))

LOCAL_DOWNLOAD_DIR = DEFAULT_DOWNLOAD_DIR
LOG_DIR = DEFAULT_LOG_DIR


final_result = {
    "status": "failed",
    "prompt_id": None,
    "prompt_ids": [],
    "local_images": [],
    "error": "unknown_error",
    "missing_models": [],
    "verified": False,
    "verification_error": None,
    "server": None,
}


def ensure_runtime_dirs():
    LOCAL_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def parse_yaml_scalar(raw: str):
    value = raw.strip()
    if not value:
        return ""
    if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
        value = value[1:-1]
    lower = value.lower()
    if lower in {"true", "false"}:
        return lower == "true"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def load_skill_config(config_path: Path) -> dict:
    # Minimal YAML parser for this skill's config structure:
    # version, active_host, hosts:<name>:<key:value>
    config = {"version": 1, "active_host": "hel", "hosts": {}}
    if not config_path.exists():
        return config

    section = None
    current_host = None
    for raw_line in config_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            current_host = None
            if stripped.endswith(":"):
                key = stripped[:-1].strip()
                section = key
                if key == "hosts" and not isinstance(config.get("hosts"), dict):
                    config["hosts"] = {}
                continue
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                config[key.strip()] = parse_yaml_scalar(value)
                section = None
                continue

        if section == "hosts" and indent >= 2:
            if indent == 2 and stripped.endswith(":"):
                current_host = stripped[:-1].strip()
                config.setdefault("hosts", {})[current_host] = {}
                continue
            if indent >= 4 and current_host and ":" in stripped:
                key, value = stripped.split(":", 1)
                config["hosts"][current_host][key.strip()] = parse_yaml_scalar(value)
                continue

    return config


def expand_path(value, fallback: Path) -> Path:
    if not value:
        return fallback
    return Path(os.path.expanduser(str(value))).resolve()


def build_server_url(scheme: str, host: str, port: int) -> str:
    return f"{scheme}://{host}:{port}"


def resolve_server_config(args) -> str:
    global LOCAL_DOWNLOAD_DIR, LOG_DIR

    cfg = load_skill_config(Path(args.config).expanduser().resolve()) if args.config else load_skill_config(CONFIG_PATH)
    hosts = cfg.get("hosts") if isinstance(cfg.get("hosts"), dict) else {}
    active_profile = str(cfg.get("active_host") or "hel")

    selected_profile_name = active_profile
    literal_host_override = None
    if args.host:
        if args.host in hosts:
            selected_profile_name = args.host
        else:
            literal_host_override = args.host

    profile = hosts.get(selected_profile_name, {}) if isinstance(hosts, dict) else {}
    scheme = str(profile.get("scheme") or "http")
    resolved_host = literal_host_override or str(profile.get("host") or "Hel")
    resolved_port = int(args.port if args.port is not None else profile.get("port") or 8188)

    LOCAL_DOWNLOAD_DIR = expand_path(profile.get("download_dir"), DEFAULT_DOWNLOAD_DIR)
    LOG_DIR = expand_path(profile.get("log_dir"), DEFAULT_LOG_DIR)
    ensure_runtime_dirs()

    if args.server:
        final_result["server"] = args.server.rstrip("/")
        return args.server.rstrip("/")

    server_url = build_server_url(scheme, resolved_host, resolved_port).rstrip("/")
    final_result["server"] = server_url
    return server_url


def log_prompt(prompt, name=None):
    ensure_runtime_dirs()
    timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    if name is None:
        name = "prompt"
    log_path = LOG_DIR / f"{timestamp}-{name}.log"
    log_path.write_text(prompt, encoding="utf-8")


def print_and_log(msg):
    print(msg)
    sys.stdout.flush()


def http_json(server_url, url_path, method="GET", payload=None):
    full_url = f"{server_url.rstrip('/')}/{url_path.lstrip('/')}"
    headers = {"Content-Type": "application/json"} if payload else {}
    data = payload and json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(full_url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        final_result["error"] = f"Connection failed (cannot reach server at {server_url}): {str(e.reason)}"
        raise
    except Exception as e:
        final_result["error"] = f"HTTP error to {server_url}: {str(e)}"
        raise


UPSCALER_MODELS = {
    "2x": "RealESRGAN_x2.pth",
    "4x": "RealESRGAN_x4.pth",
    "4x_legacy": "4x_foolhardy_Remacri.pth",
}


def prepare_tmp_workflow(prompt, negative=None, upscaler="2x"):
    print_and_log("Loading default workflow...")
    if not DEFAULT_WORKFLOW.exists():
        final_result["error"] = f"Default workflow missing: {DEFAULT_WORKFLOW}"
        raise FileNotFoundError(final_result["error"])

    with open(DEFAULT_WORKFLOW, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    print_and_log("Modifying prompt/negative/seed...")
    if "6" in workflow:
        workflow["6"]["inputs"]["text"] = prompt
    if negative and "7" in workflow:
        workflow["7"]["inputs"]["text"] = negative
    if "3" in workflow:
        workflow["3"]["inputs"]["seed"] = random.randint(0, 2**64 - 1)

    if "9" in workflow and "model_name" in workflow["9"]["inputs"]:
        model_key = upscaler if upscaler in UPSCALER_MODELS else "4x"
        workflow["9"]["inputs"]["model_name"] = UPSCALER_MODELS[model_key]
        print_and_log(f"Using {upscaler} upscaler: {workflow['9']['inputs']['model_name']}")

    tmp_workflow = ASSETS_DIR / f"tmp-workflow-{uuid.uuid4().hex[:8]}.json"
    print_and_log(f"Writing unique workflow: {tmp_workflow.name}...")
    with open(tmp_workflow, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2)

    return tmp_workflow


def queue_prompt(server_url, workflow_path):
    with open(workflow_path, "r", encoding="utf-8") as f:
        workflow = json.load(f)

    payload = {"prompt": workflow, "client_id": "openclaw_skill"}
    resp = http_json(server_url, "/prompt", method="POST", payload=payload)
    pid = resp.get("prompt_id")
    if not pid:
        raise ValueError("No prompt_id returned")
    return pid


def poll_history(server_url, prompt_id, max_wait=600):
    print_and_log("Polling for completion...")
    deadline = time.time() + max_wait
    while time.time() < deadline:
        hist = http_json(server_url, f"/history/{prompt_id}")
        item = hist.get(prompt_id)
        if item:
            print_and_log("Generation completed!")
            return item
        print(".", end="", flush=True)
        time.sleep(2)
    raise TimeoutError("Generation timeout")


def download_file(server_url, img_info):
    view_url = build_view_url(server_url, img_info)
    filename = img_info["filename"]
    local_path = LOCAL_DOWNLOAD_DIR / filename
    urllib.request.urlretrieve(view_url, local_path)
    print_and_log(f"Downloaded: {local_path}")
    return str(local_path)


def build_view_url(server_url, img_info):
    fn = quote(img_info["filename"])
    url = f"{server_url.rstrip('/')}/view?filename={fn}&type={quote(img_info.get('type', 'output'))}"
    if img_info.get("subfolder"):
        url += f"&subfolder={quote(img_info['subfolder'])}"
    return url


def cleanup_tmp_workflow(workflow_path):
    if workflow_path and "tmp-workflow-" in str(workflow_path):
        try:
            workflow_path.unlink()
        except Exception:
            pass


def verify_queued_or_history(server_url, prompt_id):
    queue = http_json(server_url, "/queue")
    for item in queue.get("queue_running", []):
        if len(item) >= 2 and item[1] == prompt_id:
            return True
    for item in queue.get("queue_pending", []):
        if len(item) >= 2 and item[1] == prompt_id:
            return True
    try:
        hist = http_json(server_url, f"/history/{prompt_id}")
        if prompt_id in hist:
            return True
    except Exception:
        pass
    return False


def extract_missing_models(err: str):
    import re

    models = re.findall(r"([^/\\s]+\\.safetensors)", err)
    if models:
        final_result["missing_models"] = [
            f"/opt/appdata/comfyui/models/checkpoints/{m}" for m in set(models)
        ]


def collect_history_images(server_url, result):
    if "error" in result:
        err = result["error"].get("message", str(result["error"]))
        final_result["error"] = err
        extract_missing_models(err)
        raise ValueError(err)

    print_and_log("Downloading images...")
    images = [img for node in result.get("outputs", {}).values() for img in node.get("images", [])]
    if not images:
        raise ValueError("No images generated")

    downloaded = []
    for img in images:
        local_path = download_file(server_url, img)
        if Path(local_path).exists():
            downloaded.append(local_path)
        else:
            raise IOError(f"Downloaded file not found: {local_path}")

    for f in downloaded:
        if not Path(f).exists():
            raise IOError(f"Verification failed: {f} not found")

    return downloaded


def await_poll_only(server_url, prompt_id, max_wait=900):
    if not verify_queued_or_history(server_url, prompt_id):
        final_result["error"] = f"Prompt {prompt_id} not found in queue or history"
        raise ValueError(final_result["error"])

    final_result["prompt_id"] = prompt_id
    final_result["status"] = "polling"
    print_and_log(f"Polling for prompt {prompt_id}...")

    result = poll_history(server_url, prompt_id, max_wait)

    downloaded = collect_history_images(server_url, result)

    final_result["status"] = "success"
    final_result["local_images"] = downloaded
    final_result["error"] = None
    final_result["verified"] = True


def main():
    workflow_path = None
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("--positive", required=True, help="File containing positive prompt (REQUIRED)")
        parser.add_argument("--negative-file", default=None, help="File containing negative prompt (optional)")
        parser.add_argument("--workflow", default=None, help="Custom workflow JSON path (optional, skips prompt modification)")
        parser.add_argument("--config", default=None, help="Path to config.yml (optional override)")
        parser.add_argument("--server", default=None, help="Full server URL override, e.g. http://Hel:8188")
        parser.add_argument("--host", default=None, help="Host profile name from config.yml (e.g. hel) or literal hostname/IP")
        parser.add_argument("--port", type=int, default=None, help="Port override (used with config profile or --host)")
        parser.add_argument("--maxwait", type=int, default=900, help="Max wait time in seconds (default 900 = 15 minutes)")
        parser.add_argument("--follow", action="store_true", help="Verbose progress output while waiting (still waits and downloads)")
        parser.add_argument("--await", dest="await_prompt_id", default=None, help="Poll for completion of a previously queued prompt (provide prompt_id)")
        parser.add_argument("--upscaler", default="2x", choices=["2x", "4x", "4x_legacy"], help="Upscaler model: 2x (default), 4x, or 4x_legacy")
        parser.add_argument("--count", type=int, default=1, help="Generate N variations using the same prompt (different random seeds)")
        args = parser.parse_args()
        if args.count < 1:
            raise ValueError("--count must be >= 1")

        server_url = resolve_server_config(args)
        print_and_log(f"Using server: {server_url}")
        print_and_log(f"Download dir: {LOCAL_DOWNLOAD_DIR}")

        if args.await_prompt_id:
            await_poll_only(server_url, args.await_prompt_id, args.maxwait)
            return

        prompt_path = Path(args.positive).expanduser().resolve()
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Positive prompt file not found: {prompt_path}. You must CREATE the file first - the script does not create files for you. Example: echo 'your prompt' > /tmp/positive.txt"
            )
        prompt = prompt_path.read_text(encoding="utf-8").strip()
        prompt_name = prompt_path.stem

        negative = None
        if args.negative_file:
            neg_path = Path(args.negative_file).expanduser().resolve()
            if neg_path.exists():
                negative = neg_path.read_text(encoding="utf-8").strip()

        log_prompt(prompt, prompt_name)

        if not prompt or not prompt.strip():
            raise ValueError(
                "Error: --positive file is EMPTY! You must write a prompt to the file first. Example: echo 'beautiful landscape' > /tmp/positive.txt"
            )

        if negative and len(negative) > 5000:
            print_and_log("Warning: Negative prompt is very long (>5000 chars), this may cause issues")

        all_downloaded = []
        prompt_ids = []
        for idx in range(args.count):
            if args.count > 1:
                print_and_log(f"\n=== Variation {idx + 1}/{args.count} ===")
            if args.workflow:
                workflow_path = Path(args.workflow).expanduser().resolve()
                print_and_log(f"Custom workflow: {workflow_path}")
            else:
                workflow_path = prepare_tmp_workflow(prompt, negative, args.upscaler)

            print_and_log(f"Queueing on {server_url}...")
            prompt_id = queue_prompt(server_url, workflow_path)
            prompt_ids.append(prompt_id)
            if idx == 0:
                final_result["prompt_id"] = prompt_id
            print_and_log(f"Queued! ID: {prompt_id}")

            cleanup_tmp_workflow(workflow_path)
            workflow_path = None

            if not verify_queued_or_history(server_url, prompt_id):
                raise ValueError(f"Prompt {prompt_id} not found in queue after submission")

            result = poll_history(server_url, prompt_id, args.maxwait)
            downloaded = collect_history_images(server_url, result)
            all_downloaded.extend(downloaded)

        final_result["prompt_ids"] = prompt_ids
        final_result["local_images"] = all_downloaded
        final_result["status"] = "success"
        final_result["error"] = None
        final_result["verified"] = True

    except Exception as e:
        if workflow_path:
            cleanup_tmp_workflow(workflow_path)
        if final_result["error"] == "unknown_error":
            final_result["error"] = str(e)
        final_result["verification_error"] = str(e)
        print_and_log(f"Failed: {final_result['error']}")

    finally:
        print_and_log("\n=== AGENT JSON RESULT ===")
        json.dump(final_result, sys.stdout, indent=2)
        print_and_log("\n=== END JSON ===")


if __name__ == "__main__":
    main()
