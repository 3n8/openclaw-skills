# Changelog

All notable changes to skills in this repository. Newest first.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/).

---

## [Unreleased]

### Added — nc-upload 1.0.0 (2026-08-27)

New skill. Minimal Nextcloud upload + share-link helper for binary files.
Replaces the full `openclaw-nextcloud` skill (19,900 lines) for the only
operations actually needed for image delivery.

- **upload** — WebDAV `PUT /remote.php/dav/files/<user>/<path>`. Binary-safe
  (reads source as raw `Buffer`, not utf-8). Auto-MIMEs from extension.
- **share** — OCS `POST /ocs/v2.php/apps/files_sharing/api/v1/shares` (public
  read-only link). Requires `--confirm shares:create-link` token.
- **unshare** — OCS `DELETE` on share id. Requires `--confirm shares:delete`.
- **delete** — WebDAV `DELETE`. Requires `--confirm files:delete`.
- **list** — WebDAV `PROPFIND` for directory listing.

**Bug fix carried over:** the upstream skill's
`readTextOption(path, "utf8")` corrupted PNG/JPG bytes — UTF-8 decoding
mangled binary bytes, round-trip md5 failed, Nextcloud preview showed a
permanent rotating spinner. This skill reads sources as raw `Buffer`.

**Single-link Matrix rule:** one `<a href>` per `formatted_body`, one URL in
`body`. Multiple URLs cause Element/SchildiChat to render the image preview
N times.

Configuration: reads `NEXTCLOUD_URL` / `NEXTCLOUD_USER` / `NEXTCLOUD_TOKEN`
from `~/.openclaw/nextcloud/.env` (mode 600) automatically, falls back to
process env.

Committed as `822343d` by Eve (OpenClaw).

---

## History

The repo started in February 2026. The ComfyUI skills went through a series
of refactors documented below (auto-extracted from `git log` for that period).

### 2026-02-24 — comfyui-api refinements

- `ddb4622` — Add ComfyUI view URLs and no-download mode
- `5411d2b` — Remove upscale stage from default edit workflow
- `6d05e9b` — Replace fake variation with upscale and edit modes
- `c78fc80` — Add ComfyUI variation count flag
- `5966295` — Add ComfyUI config and server overrides
- `f27dc84` — Split ComfyUI skills and add config scaffold

All by `OpenClaw Raven`.

### 2026-02-17 / 18 — parallel queue + 2x default upscaler

- `92b0e49` — 2x default upscaler, improved error messages, parallel queue
- `efdd6c0` — `--upscaler` option (2x default), rename `--prompt` →
  `--positive`, force file-based prompts
- `57e7830` — Parallel queuing instructions
- `9b53189` — Default now queues + waits + downloads (sequential-by-default)

### 2026-02-16 — initial scaffolding

- `8d279fe` — Add Beads (issue tracker)
- `81d5a1e` — Add ComfyUI skill (initial)

---

## Skill inventory snapshot

| Skill | Added | Last touched | Notes |
|---|---|---|---|
| comfyui-api | 2026-02-16 (`81d5a1e`) | 2026-02-24 (`ddb4622`) | Most refined; active |
| comfyui-image | 2026-02-24 (`f27dc84`) | 2026-02-24 (`f27dc84`) | Wrapper skill; stable |
| nc-upload | 2026-08-27 (`822343d`) | 2026-08-27 (`822343d`) | New; replaces `openclaw-nextcloud` for image delivery |