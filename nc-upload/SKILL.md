---
name: nc-upload
description: Minimal Nextcloud upload + share-link helper for binary files (especially large images). Reads creds from /home/en/.openclaw/nextcloud/.env. WebDAV PUT with proper binary handling, OCS share API for public link.
metadata: {"openclaw":{"emoji":"☁️"}}
---

# nc-upload

Tiny Nextcloud client for **upload + public share link** of binary files.
Replaces the full `openclaw-nextcloud` skill (19,900 lines) for the only
operations we actually need for image delivery.

**Fixed critical bug:** the upstream skill reads files via
`fs.readFileSync(path, "utf8")` which **corrupts binary content**
(PNG/JPG bytes get UTF-8-decoded, invalid sequences become `U+FFFD`,
round-trip md5 fails, Nextcloud preview never loads → "rotating loader").
This skill reads files as raw bytes and sends as `Buffer` body.

## Configuration

Reads from **`/home/en/.openclaw/nextcloud/.env`** (mode 600):

```
NEXTCLOUD_URL=https://sky.nettsi.de
NEXTCLOUD_USER=openclaw
NEXTCLOUD_TOKEN=*** password from Nextcloud Security > Devices & sessions>
```

Override per-call via env vars if needed.

## Commands

```bash
# Upload a file (binary-safe, mtime preserved)
node scripts/nc.js upload --src /path/to/file.png --dest /ComfyUI/foo.png

# Make a public read-only share link
node scripts/nc.js share --path /ComfyUI/foo.png

# Delete a file
node scripts/nc.js delete --path /ComfyUI/foo.png

# Delete a share by id
node scripts/nc.js unshare --id 7

# List directory
node scripts/nc.js list --path /ComfyUI
```

## Safety

- `delete` and `share` (which creates a public link) require `--confirm` token
- `upload` overwrites silently — same as the upstream skill
- Share links are **public read-only** by default

## Delivery pattern (verified 2026-08-27)

```bash
# 1. Upload (byte-perfect)
nc.js upload --src <local.png> --dest /ComfyUI/foo.png

# 2. Make share link (returns XML in data field; parse <url> + <id>)
nc.js share --path /ComfyUI/foo.png

# 3. Post to Matrix as m.text with ONE url only (no duplicate links!)
#    Body mentions URL once, formatted_body has ONE <a href>.
#    Multiple links cause the Matrix client to render the image preview
#    multiple times. See master session 2026-08-27 for the fix.
```

## Lessons baked in

- **Binary-safe:** reads source as raw `Buffer`, not utf-8 string. The upstream
  `openclaw-nextcloud` skill's `readTextOption(path, "utf8")` corrupted PNG/JPG bytes.
  Symptom: upload said "success", but Nextcloud preview showed a permanent rotating
  loader (file content was decoded as UTF-8 and re-encoded, mangling binary data).
- **Single URL per Matrix message:** duplicate `<a href>` in `formatted_body`
  (or duplicate URLs in `body`) makes Element/SchildiChat render the image
  preview N times. Always use exactly one link.
- **Share-link download equals WebDAV download:** the same file is served, with
  correct `Content-Type` (`image/png`) when uploaded with the right MIME. So
  md5 round-trips through both paths.

## API used

- WebDAV `PUT /remote.php/dav/files/<user>/<path>` for upload (binary body)
- WebDAV `DELETE /remote.php/dav/files/<user>/<path>` for file delete
- OCS `POST /ocs/v2.php/apps/files_sharing/api/v1/shares` for share create
- OCS `DELETE /ocs/v2.php/apps/files_sharing/api/v1/shares/<id>` for share delete
- WebDAV `PROPFIND /remote.php/dav/files/<user>/<path>` for listing
