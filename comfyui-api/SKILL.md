---
name: ComfyUI API
description: Use the ComfyUI HTTP API for image generation, standalone upscaling, and img2img-style image editing via a local runner script. Uses a local config.yml host profile (default hel) and supports CLI overrides such as --server/--host/--port. Returns structured JSON for downstream channel delivery.
read_when:
  - User asks to generate images with ComfyUI
  - User wants to run a ComfyUI workflow over HTTP/API
  - User asks for prompt-based image generation, upscaling, or image editing with ComfyUI
  - User provides a custom workflow JSON for ComfyUI
metadata: {"clawdbot":{"emoji":"🖼️","requires":{"bins":["python3"]}}}
---

# ComfyUI API Skill

## Scope
This skill is the low-level ComfyUI API execution skill.

Current reliable modes:
- Prompt-based image generation (txt2img-style workflow using the provided runner script)
- Standalone image upscaling from an input image (`--mode upscale`)

Planned modes (script upgrades):
- Image editing (img2img / inpaint) - last, and avoid Flux-first workflows
- Better variation workflows (not seed-sweep garbage)

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

The runner script now supports config-driven host selection plus CLI overrides.

CLI override precedence:
1. `--server` (full URL)
2. `--host` / `--port`
3. `config.yml`

## Current Workflow Modes (what works today)

Use the provided runner script directly. It queues, waits, verifies, uploads input images when needed, and downloads outputs.

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


Standalone upscale example:
```bash
python3 /home/en/.openclaw/skills/comfyui-api/scripts/comfyui_run.py --mode upscale --input-image /tmp/input.png --host hel --upscaler 4x
```

Image edit example (img2img-style):
```bash
echo "make the lighting dramatic and the pose more confident" > /tmp/positive.txt
python3 /home/en/.openclaw/skills/comfyui-api/scripts/comfyui_run.py --mode edit --positive /tmp/positive.txt --input-image /tmp/input.png --host hel --denoise 0.45
```
Supported current flags:
- `--mode` (`generate`, `upscale`, `edit`)
- `--positive` (required prompt file)
- `--input-image` (required for `upscale` and `edit`)
- `--negative-file`
- `--workflow`
- `--config`
- `--server`
- `--host`
- `--port`
- `--maxwait`
- `--follow`
- `--await`
- `--upscaler` (`2x`, `4x`, `4x_legacy`)
- `--denoise` (edit strength for `--mode edit`, `0.0` to `1.0`)
- `--no-download` (skip local file download and return ComfyUI `view_url` metadata only)

## Multiple Image Requests (current best practice)
For multiple images, queue multiple runs in parallel with different prompt files (or prompt variants) and `wait`.

## Verification (mandatory)
Do not report success without checking the runner JSON result.

Success requires:
- `"status": "success"`
- `"verified": true`
- `"local_images"` contains file paths that exist
- `"mode"` matches the requested mode

## Output Contract (low-level skill)
This skill should return the runner JSON result.

Preferred downstream fields:
- `comfyui_images[]` (includes `view_url`, filename, subfolder, type) for direct fetch/upload workflows
- `local_images[]` (downloaded local file paths) for Eden path-based rendering or local fallbacks

Do not assume the delivery surface here.
A separate wrapper skill decides whether to:
- upload to Discord
- upload to Matrix
- return renderable paths for Eden

## Important Paths
- Script: `/home/en/.openclaw/skills/comfyui-api/scripts/comfyui_run.py`
- Assets: `/home/en/.openclaw/skills/comfyui-api/assets/`
- Output directory (current default): `~/Downloads/ComfyUI/`
