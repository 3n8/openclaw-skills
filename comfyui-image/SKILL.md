---
name: ComfyUI Image Router
description: Channel-aware wrapper skill for ComfyUI image tasks. Selects mode (generate/upscale/edit), calls the ComfyUI API skill, and returns results to the same surface (Eden, Discord, or Matrix) when possible with explicit fallback behavior.
read_when:
  - User asks for images and the agent may need to return them in Eden, Discord, or Matrix
  - User asks for ComfyUI image generation, upscaling, or editing workflows
  - Channel-aware media delivery behavior matters
---

# ComfyUI Image Router Skill

## Purpose
This is the higher-level wrapper skill for image tasks.
It chooses the image mode and delivery strategy, then uses the `ComfyUI API` skill for execution.

Keep this skill separate so the backend can later swap between:
- local ComfyUI
- remote ComfyUI pods
- other external image APIs (e.g. SFW providers)

## Mode Selection (policy)
Choose one mode:
- `generate` (prompt -> image)
- `upscale` (input image -> larger image)
- `edit` (img2img / inpaint) [last]

Current backend reality:
- `generate` works reliably now
- `upscale` is available in `comfyui-api` `--mode upscale`
- `edit` is available in `comfyui-api` `--mode edit` but should be treated as experimental until runtime-tested

## Channel-Aware Return Policy (Eden / Discord / Matrix)
Always prefer returning the result in the same surface where the request came from.

1. Detect source surface: `Eden`, `Discord`, or `Matrix`
2. Attempt same-surface media delivery
3. If delivery fails:
   - report generation success
   - report the delivery error clearly
   - include local file path(s) as fallback diagnostics

Never silently send the image to a different platform than the originating request unless explicitly asked.

## Eden-specific note
Eden can render local file paths if they are in an allowlisted mounted directory and Eden serves them via `/api/media`.
The wrapper may return absolute local paths for Eden, or prefer `comfyui_images[].view_url` when Eden can fetch from the ComfyUI server.

## Discord / Matrix note
Prefer direct upload via the channel/plugin if available.
Best path (when reachable): fetch bytes from `comfyui_images[].view_url` and upload directly, instead of depending on local downloads.
A raw local path may still be useful as fallback diagnostics, but is not the preferred user-facing result.

## Verification before delivery
Do not attempt delivery until the underlying `ComfyUI API` skill reports a verified success result.

Required checks:
- `status == success`
- `verified == true`
- at least one image path exists

## Future extensions
- direct ComfyUI `/view` fetch and upload without forced local download
- remote profile selection (SFW/NSFW providers)
- per-channel delivery capability detection
