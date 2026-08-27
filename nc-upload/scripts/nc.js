#!/usr/bin/env node
// nc-upload — minimal Nextcloud upload/share helper
// Reads creds from /home/en/.openclaw/nextcloud/.env
// Binary-safe (unlike upstream skill's utf-8 read)

const fs = require("node:fs");
const path = require("node:path");
const { Buffer } = require("node:buffer");

// --- config ---
function loadEnv() {
  const envPath = "/home/en/.openclaw/nextcloud/.env";
  if (fs.existsSync(envPath)) {
    const text = fs.readFileSync(envPath, "utf8");
    for (const line of text.split("\n")) {
      const m = line.match(/^([A-Z_]+)=(.*)$/);
      if (m && !process.env[m[1]]) process.env[m[1]] = m[2].replace(/^["']|["']$/g, "");
    }
  }
  const url = process.env.NEXTCLOUD_URL;
  const user = process.env.NEXTCLOUD_USER;
  const token = process.env.NEXTCLOUD_TOKEN;
  if (!url || !user || !token) {
    console.error(JSON.stringify({ status: "error", message: "Missing NEXTCLOUD_URL/USER/TOKEN (in env or /home/en/.openclaw/nextcloud/.env)" }));
    process.exit(1);
  }
  return { url: url.replace(/\/$/, ""), user, token };
}

function auth(cfg) {
  return "Basic " + Buffer.from(`${cfg.user}:${cfg.token}`).toString("base64");
}

function encodePathSegments(p) {
  return p.split("/").filter(Boolean).map(encodeURIComponent).join("/");
}

async function request(cfg, endpoint, init = {}) {
  const url = `${cfg.url}${endpoint}`;
  const headers = {
    Authorization: auth(cfg),
    "User-Agent": "nc-upload/1.0",
    ...(init.headers || {}),
  };
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status}: ${res.text || res.statusText} — body: ${txt.slice(0, 200)}`);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return await res.json();
  if (ct.includes("xml")) {
    const t = await res.text();
    return t;
  }
  const buf = Buffer.from(await res.arrayBuffer());
  return buf;
}

// --- commands ---

async function cmdUpload(cfg, args) {
  const src = args["--src"];
  const dest = args["--dest"];
  if (!src || !dest) throw new Error("--src and --dest required");
  if (!fs.existsSync(src)) throw new Error(`Source not found: ${src}`);

  const body = fs.readFileSync(src); // BINARY, not utf8
  const mime = (() => {
    const ext = path.extname(src).toLowerCase().slice(1);
    return {
      png: "image/png", jpg: "image/jpeg", jpeg: "image/jpeg",
      webp: "image/webp", gif: "image/gif",
      txt: "text/plain", json: "application/json",
    }[ext] || "application/octet-stream";
  })();
  const safeDest = encodePathSegments(dest.replace(/^\/+/, ""));
  const endpoint = `/remote.php/dav/files/${encodeURIComponent(cfg.user)}/${safeDest}`;

  await request(cfg, endpoint, {
    method: "PUT",
    headers: { "Content-Type": mime, "Content-Length": String(body.length) },
    body,
  });
  return { path: dest, status: "uploaded", size: body.length, mime };
}

async function cmdList(cfg, args) {
  const p = (args["--path"] || "/").replace(/^\/+/, "") || "";
  const safe = encodePathSegments(p);
  const depth = args["--depth"] || "1";
  const body = `<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:prop>
    <d:displayname/><d:getcontentlength/><d:getlastmodified/><d:resourcetype/>
    <oc:fileid/>
  </d:prop>
</d:propfind>`;
  const endpoint = `/remote.php/dav/files/${encodeURIComponent(cfg.user)}${p ? "/" + safe : ""}`;
  const txt = await request(cfg, endpoint, {
    method: "PROPFIND",
    headers: { "Content-Type": "application/xml", Depth: depth },
    body,
  });
  return { path: "/" + p, raw: String(txt).slice(0, 2000) };
}

async function cmdShare(cfg, args) {
  const p = args["--path"];
  if (!p) throw new Error("--path required");
  const permissions = args["--permissions"] || "1";
  const body = new URLSearchParams({
    path: p,
    shareType: "3", // public link
    permissions,
  }).toString();
  const res = await request(cfg, "/ocs/v2.php/apps/files_sharing/api/v1/shares", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded", "OCS-APIRequest": "true" },
    body,
  });
  const data = res.ocs?.data || res.data || res;
  return data;
}

async function cmdUnshare(cfg, args) {
  const id = args["--id"];
  if (!id) throw new Error("--id required");
  await request(cfg, `/ocs/v2.php/apps/files_sharing/api/v1/shares/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: { "OCS-APIRequest": "true" },
  });
  return { id, status: "deleted" };
}

async function cmdDelete(cfg, args) {
  const p = args["--path"];
  if (!p) throw new Error("--path required");
  const safe = encodePathSegments(p.replace(/^\/+/, ""));
  const endpoint = `/remote.php/dav/files/${encodeURIComponent(cfg.user)}/${safe}`;
  await request(cfg, endpoint, { method: "DELETE" });
  return { path: p, status: "deleted" };
}

// --- main ---
async function main() {
  const cfg = loadEnv();
  const argv = process.argv.slice(2);
  const cmd = argv[0];
  const args = {};
  for (let i = 1; i < argv.length; i++) {
    if (argv[i].startsWith("--")) args[argv[i]] = argv[i + 1] || true, i++;
  }

  let result;
  switch (cmd) {
    case "upload":  result = await cmdUpload(cfg, args); break;
    case "list":    result = await cmdList(cfg, args); break;
    case "share":   result = await cmdShare(cfg, args); break;
    case "unshare": result = await cmdUnshare(cfg, args); break;
    case "delete":  result = await cmdDelete(cfg, args); break;
    default:
      console.error(JSON.stringify({ status: "error", message: `Unknown command: ${cmd}. Use upload|list|share|unshare|delete` }));
      process.exit(1);
  }
  console.log(JSON.stringify({ status: "success", data: result }, null, 2));
}

main().catch((e) => {
  console.error(JSON.stringify({ status: "error", message: e.message || String(e) }));
  process.exit(1);
});
