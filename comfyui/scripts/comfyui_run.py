#!/usr/bin/env python3
"""
ComfyUI remote runner for OpenClaw skill - agent-robust with configurable server.
Supports --server http://<ip-or-host>:8188 (default http://Hel:8188).
Absolute paths, structured JSON always, full error reporting.
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import quote
import uuid
from datetime import datetime

SKILL_BASE = Path("/home/en/.openclaw/skills/comfyui").resolve()
ASSETS_DIR = SKILL_BASE / "assets"
DEFAULT_WORKFLOW = ASSETS_DIR / "imagegen_workflow.json"

LOCAL_DOWNLOAD_DIR = Path(os.path.expanduser("~/Downloads/ComfyUI"))
LOCAL_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

LOG_DIR = Path("/home/en/.openclaw/logs/ComfyUI")
LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_prompt(prompt, name=None):
    timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
    if name is None:
        name = "prompt"
    log_path = LOG_DIR / f"{timestamp}-{name}.log"
    log_path.write_text(prompt, encoding="utf-8")


final_result = {
    "status": "failed",
    "prompt_id": None,
    "local_images": [],
    "error": "unknown_error",
    "missing_models": [],
    "verified": False,
    "verification_error": None,
}


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
        final_result["error"] = (
            f"Connection failed (cannot reach server at {server_url}): {str(e.reason)}"
        )
        raise
    except Exception as e:
        final_result["error"] = f"HTTP error to {server_url}: {str(e)}"
        raise


UPSCALER_MODELS = {
    "2x": "RealESRGAN_x2plus.pth",
    "4x": "4x_foolhardy_Remacri.pth",
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
        workflow["9"]["inputs"]["model_name"] = UPSCALER_MODELS.get(
            upscaler, UPSCALER_MODELS["2x"]
        )
        print_and_log(
            f"Using {upscaler} upscaler: {workflow['9']['inputs']['model_name']}"
        )

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
    except:
        pass
    return False


def await_poll_only(server_url, prompt_id, max_wait=900):
    if not verify_queued_or_history(server_url, prompt_id):
        final_result["error"] = f"Prompt {prompt_id} not found in queue or history"
        raise ValueError(final_result["error"])

    final_result["prompt_id"] = prompt_id
    final_result["status"] = "polling"
    print_and_log(f"Polling for prompt {prompt_id}...")

    result = poll_history(server_url, prompt_id, max_wait)

    if "error" in result:
        err = result["error"].get("message", str(result["error"]))
        final_result["error"] = err
        import re

        models = re.findall(r"([^/\s]+\.safetensors)", err)
        if models:
            final_result["missing_models"] = [
                f"/opt/appdata/comfyui/models/checkpoints/{m}" for m in set(models)
            ]
        raise ValueError(err)

    print_and_log("Downloading images...")
    images = [
        img
        for node in result.get("outputs", {}).values()
        for img in node.get("images", [])
    ]
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

    final_result["status"] = "success"
    final_result["local_images"] = downloaded
    final_result["error"] = None
    final_result["verified"] = True


def main():
    workflow_path = None
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--positive",
            required=True,
            help="File containing positive prompt (REQUIRED)",
        )
        parser.add_argument(
            "--negative-file",
            default=None,
            help="File containing negative prompt (optional)",
        )
        parser.add_argument(
            "--workflow",
            default=None,
            help="Custom workflow JSON path (optional, skips prompt modification)",
        )
        parser.add_argument(
            "--server",
            default="http://Hel:8188",
            help="Full server URL (use IP if hostname resolution fails in subworker)",
        )
        parser.add_argument(
            "--maxwait",
            type=int,
            default=900,
            help="Max wait time in seconds (default 900 = 15 minutes)",
        )
        parser.add_argument(
            "--follow",
            action="store_true",
            help="Queue and return immediately (don't wait for completion). Default is to wait and download.",
        )
        parser.add_argument(
            "--await",
            dest="await_prompt_id",
            default=None,
            help="Poll for completion of a previously queued prompt (provide prompt_id)",
        )
        parser.add_argument(
            "--upscaler",
            default="2x",
            choices=["2x", "4x"],
            help="Upscaler model: 2x (default, faster) or 4x (slower, higher res)",
        )
        args = parser.parse_args()

        # Default: queue and wait for completion + download
        # --follow: same but with verbose output
        verbose = args.follow

        if args.await_prompt_id:
            await_poll_only(args.server, args.await_prompt_id, args.maxwait)
            return

        prompt_path = Path(args.positive).expanduser().resolve()
        if not prompt_path.exists():
            raise FileNotFoundError(f"Positive prompt file not found: {prompt_path}")
        prompt = prompt_path.read_text(encoding="utf-8").strip()
        prompt_name = prompt_path.stem

        negative = None
        if args.negative_file:
            neg_path = Path(args.negative_file).expanduser().resolve()
            if neg_path.exists():
                negative = neg_path.read_text(encoding="utf-8").strip()

        log_prompt(prompt, prompt_name)

        if not prompt or not prompt.strip():
            raise ValueError("Error: --positive file cannot be empty")

        if negative and len(negative) > 5000:
            print_and_log(
                "Warning: Negative prompt is very long (>5000 chars), this may cause issues"
            )

        server_url = args.server.rstrip("/")

        workflow_path = None
        if args.workflow:
            workflow_path = Path(args.workflow).expanduser().resolve()
            print_and_log(f"Custom workflow: {workflow_path}")
        else:
            workflow_path = prepare_tmp_workflow(prompt, negative, args.upscaler)

        print_and_log(f"Queueing on {server_url}...")
        prompt_id = queue_prompt(server_url, workflow_path)
        final_result["prompt_id"] = prompt_id
        print_and_log(f"Queued! ID: {prompt_id}")

        cleanup_tmp_workflow(workflow_path)

        if not verify_queued_or_history(server_url, prompt_id):
            raise ValueError(f"Prompt {prompt_id} not found in queue after submission")

        # Always wait for completion and download (default behavior)
        # --follow just adds verbose output
        verbose = args.follow
        result = poll_history(server_url, prompt_id, args.maxwait)

        if "error" in result:
            err = result["error"].get("message", str(result["error"]))
            final_result["error"] = err
            import re

            models = re.findall(r"([^/\s]+\.safetensors)", err)
            if models:
                final_result["missing_models"] = [
                    f"/opt/appdata/comfyui/models/checkpoints/{m}" for m in set(models)
                ]
            raise ValueError(err)

        print_and_log("Downloading images...")
        images = [
            img
            for node in result.get("outputs", {}).values()
            for img in node.get("images", [])
        ]
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

        final_result["status"] = "success"
        final_result["local_images"] = downloaded
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
