---
name: ComfyUI API
description: Use the ComfyUI HTTP API for image generation (current), with planned support for variation, upscale, and image editing. Uses a local config.yml host profile (default hel) and supports CLI overrides such as --server/--host/--port when the runner script supports them. Returns structured JSON for downstream channel delivery.
read_when:
  - User asks to generate images with ComfyUI
  - User wants to run a ComfyUI workflow over HTTP/API
  - User asks for prompt-based image generation, variations, or upscaling with ComfyUI
  - User provides a custom workflow JSON for ComfyUI
metadata: {"clawdbot":{"emoji":"🖼️","requires":{"bins":["python3"]}}}
---

# ComfyUI API Skill

## Scope
This skill is the low-level ComfyUI API execution skill.

Current reliable mode:
- Prompt-based image generation (txt2img-style workflow using the provided runner script)

Planned modes (script upgrades):
- Variation (same prompt, multiple seeds)
- Upscale (standalone input image upscale)
- Image editing (img2img / inpaint) - last, and avoid Flux-first workflows

Use a separate wrapper/usage skill for:
- mode selection
- channel-aware delivery (Eden / Discord / Matrix)
- fallback behavior if channel delivery fails

## Server Configuration (config.yml)
This skill now has a local config file:
- `/home/en/.openclaw/skills/comfyui-api/config.yml` (runtime install path)
- Repo path: `~/git/openclaw-skills/comfyui-api/config.yml`

Current profile scaffold:
- `hel` (default)

The runner script will be upgraded to support config-driven host selection. Until then, the existing `--server` override remains the reliable way to point at a different ComfyUI instance.

Planned CLI override precedence (for the upgraded runner):
1. `--server` (full URL)
2. `--host` / `--port`
3. `config.yml`

## Current Generation Workflow (what works today)
Use the provided runner script directly. It queues, waits, verifies, and downloads images.

Required usage pattern:
```bash
echo "your prompt here" > /tmp/positive.txt
python3 /home/en/.openclaw/skills/comfyui-api/scripts/comfyui_run.py --positive /tmp/positive.txt
```

Optional negative prompt:
```bash
echo "your prompt" > /tmp/positive.txt
echo "bad quality, blurry" > /tmp/negative.txt
python3 /home/en/.openclaw/skills/comfyui-api/scripts/comfyui_run.py --positive /tmp/positive.txt --negative-file /tmp/negative.txt
```

Supported current flags (script today):
- `--positive` (required prompt file)
- `--negative-file`
- `--workflow`
- `--server`
- `--maxwait`
- `--follow`
- `--await`
- `--upscaler` (`2x`, `4x`, `4x_legacy`)

## Multiple Image Requests (current best practice)
For multiple images, queue multiple runs in parallel with different prompt files (or prompt variants) and `wait`.

## Verification (mandatory)
Do not report success without checking the runner JSON result.

Success requires:
- `"status": "success"`
- `"verified": true`
- `"local_images"` contains file paths that exist

## Output Contract (low-level skill)
This skill should return the runner JSON result and absolute local file paths.

Do not assume the delivery surface here.
A separate wrapper skill decides whether to:
- upload to Discord
- upload to Matrix
- return renderable paths for Eden

## Important Paths
- Script: `/home/en/.openclaw/skills/comfyui-api/scripts/comfyui_run.py`
- Assets: `/home/en/.openclaw/skills/comfyui-api/assets/`
- Output directory (current default): `~/Downloads/ComfyUI/`
