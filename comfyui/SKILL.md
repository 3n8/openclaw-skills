---
name: ComfyUI
description: Generate images on remote ComfyUI Docker instance at http://Hel:8188 using the HTTP API. Supports the default realistic Pony XL workflow (with prompt modifications) or any custom/external workflow JSON (used as-is). Downloads generated images locally to ~/Downloads/ComfyUI. Reports missing models clearly.
read_when:
  - User asks to generate images with ComfyUI
  - User describes an image to generate (subject, style, scene, NSFW)
  - User provides a custom workflow JSON or wants to run an external workflow
  - User pastes model weight URLs to download (use separate download_weights.py)
metadata: {"clawdbot":{"emoji":"🖼️","requires":{"bins":["python3"]}}}
---

# ComfyUI Skill (Remote Docker @ http://Hel:8188)

## Overview
All interaction is over HTTP with your remote ComfyUI server at **http://Hel:8188** (external host).

## Default Resolution: 1024x1024
**The default workflow generates at 1024x1024 resolution.** Use this resolution unless the user explicitly requests a different size (e.g., 512x512, 1920x1080, etc.).

## Default Timeout: 15 minutes
**Each image generation has 15 minutes (900 seconds) to complete.** The script will wait up to 15 minutes for each image. Do not assume failure if it takes time - check the queue!

## CLI Flags (REQUIRED)
```
--positive /path/to/positive.txt      # REQUIRED - positive prompt file
--negative-file /path/to/negative.txt # OPTIONAL - negative prompt file
--upscaler 2x                          # Upscaler: 2x (default, faster) or 4x (slower, higher res)
--follow                              # Same as default but shows verbose output (for debugging)
```

**The script does NOT accept prompts directly on the command line. You MUST use files.**

**Default upscaler is 2x** (1024→2048). Use `--upscaler 4x` for 4x upscaling (1024→4096, slower but higher resolution).

## How to Generate Images

**Write prompts to files, then run:**

```bash
echo "your prompt here" > /tmp/positive.txt
python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --positive /tmp/positive.txt
```

That's it! The script handles everything - queue, wait for completion, download.

**With negative prompt:**

```bash
echo "your positive prompt" > /tmp/positive.txt
echo "bad quality, blurry" > /tmp/negative.txt
python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --positive /tmp/positive.txt --negative-file /tmp/negative.txt
```

**--follow** does the same thing but shows verbose output (for debugging).

## CRITICAL: Multiple Images MUST be Parallel!

If the user wants 10 images, you MUST queue all 10 at once in PARALLEL:

```bash
# DO NOT wait for one to finish before starting the next!
# ALL OF THESE MUST RUN AT THE SAME TIME:

exec python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --positive /tmp/p1.txt &
exec python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --positive /tmp/p2.txt &
exec python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --positive /tmp/p3.txt &
exec python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --positive /tmp/p4.txt &
exec python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --positive /tmp/p5.txt &
exec python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --positive /tmp/p6.txt &
exec python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --positive /tmp/p7.txt &
exec python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --positive /tmp/p8.txt &
exec python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --positive /tmp/p9.txt &
exec python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --positive /tmp/p10.txt &

# Wait for all to complete
wait
```

The `&` runs each command in background so they all queue at once!

**DO NOT:**
- Wait for image 1 to finish before starting image 2
- Run them one by one
- Be slow

**DO:**
- Queue all at once using `&`
- They will all generate in parallel on the GPU
- The script will automatically wait and download each one

**DO NOT use these flags (they don't exist and will cause errors):**
- `--prompt`, `--prompt-file` (use `--positive` instead)
- `--negative` (use `--negative-file` instead)
- `--generate`, `--output`, `-g`, `-o`, `--queue-only`

## Troubleshooting

**If command seems to run but nothing queues:**
- Use `--positive` (not `--prompt-file` or `--prompt`)
- Check ComfyUI queue: `curl http://Hel:8188/queue`

## CRITICAL: Do NOT spawn sub-agents for image generation!
**Run the script DIRECTLY using exec. Do NOT use sessions_spawn.**

Wrong (FAILS):
- Spawning a sub-agent to run the generation
- Chaining multiple tool calls hoping one will work
- Using browser/UI tools

Correct (WORKS):
```bash
# ALWAYS use --positive - write prompt to file first:
echo "your prompt here" > /tmp/positive.txt
exec python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --positive /tmp/positive.txt
```
The script queues, waits for generation, and downloads automatically. Easy!

## Image generation process
- The script automatically queues, waits for completion, and downloads the image.
- No need for two-step process anymore!

## Verification

**Never tell the user an image was generated successfully without verifying it!**

Before claiming success, you MUST verify:

1. **Check the JSON output** - Look for `"status": "success"` AND `"local_images"` with actual file paths
2. **Verify the NEW file exists with CURRENT timestamp** - Run:
   ```bash
   ls -lat ~/Downloads/ComfyUI/ | head -5
   ```
   The newest file should have a recent timestamp (within the last few minutes). Do NOT use `tail` - it shows oldest files!
3. **Check ComfyUI queue** - Use the API to verify the prompt_id exists in history:
   ```bash
   curl http://Hel:8188/history/<prompt_id>
   ```
   If status is "success" and has images in outputs, the generation succeeded.

**Never accept these as success:**
- Script says "Queued!" without waiting for completion
- Script returns without JSON output
- JSON shows "status": "failed" or "error" is not null
- No file in ~/Downloads/ComfyUI/ with a recent timestamp (check with `ls -lat | head`)
- Using `ls | tail` to check - this shows OLDEST files, not newest!

**If verification fails:**
- Check the ComfyUI queue: `curl http://Hel:8188/queue`
- Check history: `curl http://Hel:8188/history`
- Report actual status to user, don't fake success

**Prompt Length Warning**
Keep prompts under 2000 characters when possible. Very long prompts may be truncated by language models or cause context overflow issues.

## Output Format - What to Report to User

**Single command handles everything:**
- `"status": "success"` → Report: "Image generated: [filepath]"
- `"status": "failed"` → Report: "Image generation failed: [error]"

**NEVER report "success" until you get `"status": "success"` from the script!**

**Agent must verify:**
- `"status": "success"` AND `"verified": true` must both be true
- File must exist at paths in `"local_images"`
- If `"verified": false` or `"error"` is not null, generation FAILED

## IMPORTANT: Use the skill script!
**Do NOT use any .sh or .json files from agent workspaces.** Only use:
- Script: `/home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py`
- Default workflow: `/home/en/.openclaw/skills/comfyui/assets/imagegen_workflow.json`
- Output directory: `/home/en/Downloads/ComfyUI/`

Always outputs structured JSON at the end for reliable agent parsing.
