# openclaw-skills

Personal collection of OpenClaw skills for `en`'s agent(s). Each skill is a
self-contained directory with a `SKILL.md` (manifest), optional `config.yml`,
`scripts/`, and `assets/`.

## Skills

| Skill | Purpose | Stack |
|---|---|---|
| [`comfyui-api`](./comfyui-api/) | Low-level ComfyUI HTTP API client — generation, upscaling, img2img editing. Returns structured JSON for downstream consumers. | Python (stdlib only) |
| [`comfyui-image`](./comfyui-image/) | Channel-aware wrapper that picks generate/upscale/edit, calls `comfyui-api`, and returns results to the originating surface (Eden / Discord / Matrix) with explicit fallback. | Policy / dispatch |
| [`nc-upload`](./nc-upload/) | Minimal Nextcloud upload + share-link helper for binary files (esp. images). Reads creds from `~/.openclaw/nextcloud/.env`. Binary-safe (fixes upstream `openclaw-nextcloud` utf-8 read bug). | Node.js 24+ (stdlib only) |

## Conventions

- Every skill has a `SKILL.md` with at minimum:
  - `name`, `description`, `read_when`, `metadata.emoji`
  - "Scope" / "Usage" / "Safety" sections
- No required environment variables for install-time — runtime env loaded via `.env` or process env
- Scripts stay stdlib-only (no `pip install` or `npm install` for end users)
- Each skill is independently removable

## Install

These are personal skills, but the layout follows the standard OpenClaw
workspace-skill shape. Copy any skill directory to:

- Workspace skill: `~/.openclaw/workspace/skills/<name>/` (per-agent)
- Or use `openclaw skills install <name>` once they're indexed in ClawHub

## Changelog

See [`CHANGELOG.md`](./CHANGELOG.md) for version history of every skill.

## Contributing

This is a personal repo. PRs from `en` only.

## License

Private — not for redistribution.