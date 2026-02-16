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

## CLI Flags
```
--prompt-file /path/to/prompt.txt  # REQUIRED - avoids CLI quoting issues!
--follow                          # Queue and return immediately (for parallel queuing)
--await <prompt_id>               # Wait for completion + download
```

## How to Generate Multiple Images (IMPORTANT!)

**For multiple images, you MUST queue them ALL FIRST, then wait for each:**

**Step 1: Queue all images at once (parallel)**
```bash
# For 5 images, use --follow to queue each quickly:
echo "prompt 1" > /tmp/p1.txt
python3 comfyui_run.py --prompt-file /tmp/p1.txt --follow

echo "prompt 2" > /tmp/p2.txt
python3 comfyui_run.py --prompt-file /tmp/p2.txt --follow

echo "prompt 3" > /tmp/p3.txt
python3 comfyui_run.py --prompt-file /tmp/p3.txt --follow

# ... continue for all 5
```
Each --follow returns a prompt_id. SAVE these IDs!

**Step 2: Wait for each to complete**
```bash
# Wait for each to finish and download (can be parallel or sequential)
python3 comfyui_run.py --await <prompt_id_1>
python3 comfyui_run.py --await <prompt_id_2>
python3 comfyui_run.py --await <prompt_id_3>
# ... etc
```

**Why?**
- --follow: queues and returns immediately (doesn't wait for generation)
- --await: waits for completion AND downloads the image
- This allows all 5 to queue at once and work in parallel on GPU
- Each --follow call should return: "status": "queued" with a prompt_id
- Each --await call should return: "status": "success" with local_images path when done

**Why?**
- --follow: queues and returns immediately (doesn't wait for generation)
- --await: waits for completion AND downloads the image
- This allows all 5 to queue at once and work in parallel on GPU
- Each --follow call should return: "status": "queued" with a prompt_id
- Each --await call should return: "status": "success" with local_images path when done

**For SINGLE image: Just use --prompt-file (it will wait for completion automatically)**

**For MULTIPLE images: Use --follow + --await as shown above!**

```bash
# CORRECT for single image:
echo "your prompt here" > /tmp/p.txt
python3 comfyui_run.py --prompt-file /tmp/p.txt
```

**DO NOT use these flags (they don't exist):**
- `--generate`, `--output`, `-g`, `-o`, `--queue-only` - these will cause errors!

## Troubleshooting

**If command seems to run but nothing queues:**
- Use `--prompt-file` instead of `--prompt` to avoid CLI quoting issues
- Check ComfyUI queue: `curl http://Hel:8188/queue`

## CRITICAL: Do NOT spawn sub-agents for image generation!
**Run the script DIRECTLY using exec. Do NOT use sessions_spawn.**

Wrong (FAILS):
- Spawning a sub-agent to run the generation
- Chaining multiple tool calls hoping one will work
- Using browser/UI tools

Correct (WORKS):
```bash
# ALWAYS use prompt-file - write prompt to file first:
echo "your prompt here" > /tmp/prompt.txt
exec python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --prompt-file /tmp/prompt.txt
```
The script queues, waits for generation, and downloads automatically. Easy!

## Image generation process
- The script automatically queues, waits for completion, and downloads the image.
- No need for two-step process anymore!

**For multiple images: Run them sequentially (one after another)**

## Simple Workflow

Just use `--prompt` - the script handles everything:
```bash
exec python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --prompt "your prompt here"
```

Returns `"status": "success"` with filepath when done. That's it!
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

## Usage Examples

### Single image generation
```bash
# Always use prompt-file:
echo "a beautiful sunset over the ocean" > /tmp/prompt.txt
python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --prompt-file /tmp/prompt.txt
```

### With negative prompt
```bash
echo "your prompt" > /tmp/p.txt
python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --prompt-file /tmp/p.txt --negative "bad quality, blurry"
```

### Using prompt file (recommended for long prompts)
Useful for complex prompts with special characters that might cause CLI quoting issues:
```bash
echo "your very long prompt with special characters :;'" > /tmp/prompt.txt
python3 /home/en/.openclaw/skills/comfyui/scripts/comfyui_run.py --prompt-file /tmp/prompt.txt
```

### Multiple images
Run them sequentially (wait for each to complete before starting next):
```bash
exec python3 comfyui_run.py --prompt "image 1 description"
# Wait for completion, then next...
exec python3 comfyui_run.py --prompt "image 2 description"
# Wait for completion, then next...
exec python3 comfyui_run.py --prompt "image 3 description"
```

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
- Default workflow: `/home/en/.openclaw/skills/comfyui/assets/default-workflow.json`
- Output directory: `/home/en/Downloads/ComfyUI/`

Always outputs structured JSON at the end for reliable agent parsing.
