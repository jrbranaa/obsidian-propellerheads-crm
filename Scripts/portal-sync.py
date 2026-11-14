#!/usr/bin/env python3
"""
Portal sync: pull service requests from the propellerheads.io client portal
into this vault. One-way (portal -> vault), stdlib only.

For each portal SR:
  * New (not yet linked) and still active in the portal -> create
      Service Requests/<CODE><YYYYMMDD>-<title>/Initial Request.md
    from Templates/Service Request Template.md, with `status: inbox` and
    `portal_id: <n>` in the frontmatter. Written once, then it's yours.
  * Linked (any note directly inside an SR folder has `portal_id: <n>`) ->
    (re)write Portal.md in that folder: current fields, contact details, the
    full change log incl. internal notes, and attachments (downloaded to
    "Portal files/"). Portal.md is overwritten on every sync — don't edit it.

To link an SR you already created by hand, add `portal_id: <n>` to its note's
frontmatter before syncing; Portal.md then lands in that folder.

Customers are matched by `portal_client: <client login ID>` in the company
note's frontmatter, falling back to the company note's name equalling the
portal client name. Contacts are matched to People/ notes by exact name, then
`aliases:`, then first name alone when exactly one person there has it.

Vault `status` and portal status are kept separate on purpose (`bill` etc.
only exist here). The sync reports where they disagree, e.g. completed in the
vault but still open in the portal.

Documents (vault -> portal, with --push): any note whose frontmatter has
`portal_doc: draft` or `portal_doc: published` is pushed to the client portal's
Documents tab:

  portal_doc: published          # or draft (clients only ever see published)
  portal_category: infrastructure  # proposal | infrastructure | service_summary | other
  portal_client: sah             # optional if `customer: "[[Company]]"` is set
  portal_title: Network Overview # optional; defaults to the first # heading, then the file name
  portal_change: Replaced the firewall  # optional note shown with this version
  portal_slug: network-overview  # added automatically on the first push; keeps the link stable

Embedded/linked files (![[diagram.png]], [[spec.pdf]], ![x](img/a.png)) are
uploaded with the note. Unchanged notes are skipped without uploading. Each
push of changed content on top of a published version becomes a new version;
a draft is overwritten in place until it's published. Deleting or renaming a
note never removes it from the portal: do that in the portal admin.

Usage (from anywhere):
  python3 Scripts/portal-sync.py              sync everything
  python3 Scripts/portal-sync.py 12 15        only these portal SR numbers
  python3 Scripts/portal-sync.py --dry-run    show what would change
  python3 Scripts/portal-sync.py --all        also create notes for resolved/closed SRs
  python3 Scripts/portal-sync.py --push       push documents to the portal (no SR pull)
  python3 Scripts/portal-sync.py --push --dry-run

Config: ~/.config/propellerheads/portal-sync.json
  {"portal_url": "https://propellerheads.io/portal", "token": "<api token>",
   "write_token": "<api write token, only needed for --push>"}
(or env PH_PORTAL_URL / PH_PORTAL_TOKEN / PH_PORTAL_WRITE_TOKEN). Kept outside
the vault so the tokens aren't spread to every device by Obsidian Sync.
"""

import argparse
import hashlib
import json
import mimetypes
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CONFIG_PATH = Path.home() / ".config" / "propellerheads" / "portal-sync.json"
SR_ROOT = "Service Requests"
TEMPLATE_PATH = "Templates/Service Request Template.md"
PORTAL_NOTE = "Portal.md"
FILES_DIR = "Portal files"

ACTIVE_PORTAL = {"open", "in_progress", "waiting_client"}
DONE_VAULT = {"completed", "abandoned", "bill"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".bmp"}


# ── Helpers ────────────────────────────────────────────────


def frontmatter(path):
    """`key: value` frontmatter as a dict; YAML block lists (`- item`) become lists."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    m = re.match(r"^---\r?\n(.*?)\r?\n---", text, re.S)
    if not m:
        return {}
    out, key = {}, None
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z0-9_-]+):\s*(.*?)\s*$", line)
        im = re.match(r"^\s*-\s+(.*?)\s*$", line)
        if km:
            key = km.group(1)
            out[key] = km.group(2).strip("\"'")
        elif im and key and (out[key] == "" or isinstance(out[key], list)):
            out[key] = (out[key] or []) + [im.group(1).strip("\"'")]
    return out


def as_list(value):
    """Frontmatter value -> list: block list, inline `[a, b]`, or a single string."""
    if isinstance(value, list):
        return value
    if value.startswith("[") and not value.startswith("[["):
        return [v.strip(" \"'") for v in value.strip("[]").split(",") if v.strip(" \"'")]
    return [value] if value else []


def unlink(value):
    """'[[Name]]' / '[[Name|alias]]' -> 'Name'."""
    m = re.match(r"^\[\[([^|\]]+)", value or "")
    return m.group(1) if m else (value or "")


def safe_name(s, limit=80):
    """Filename-safe on Windows/Android too, and harmless in wikilinks."""
    s = re.sub(r'["*?<>|#^\[\]]', "", s)
    s = re.sub(r"[\\/:]", "-", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"-{2,}", "-", s).strip(" -")
    return s[:limit].rstrip(" .-") or "untitled"


def quote(text):
    return "\n".join("> " + line if line else ">" for line in text.splitlines())


class Portal:
    def __init__(self, url, token, hash_key="api_token_hash"):
        self.url = url.rstrip("/")
        self.token = token
        self.hash_key = hash_key

    def _open(self, req, what):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except urllib.error.HTTPError as ex:
            try:
                detail = json.loads(ex.read()).get("error", "")
            except ValueError:
                detail = ""
            hint = {401: "token rejected", 404: f"API disabled ({self.hash_key} empty) or not found"}
            if ex.code == 422 and detail:  # validation error on one document: report, keep going
                raise PushRejected(detail)
            sys.exit(f"Portal error {ex.code} for {what}: {detail or hint.get(ex.code, ex.reason)}")
        except urllib.error.URLError as ex:
            sys.exit(f"Can't reach {self.url}: {ex.reason}")

    def get(self, query):
        req = urllib.request.Request(
            f"{self.url}/api.php?{query}",
            headers={"Authorization": f"Bearer {self.token}", "User-Agent": "portal-sync"},
        )
        return self._open(req, query)

    def post_multipart(self, query, fields, files):
        """fields: {name: str}; files: [(field name, filename, bytes)]."""
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in fields.items():
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode() + value.encode("utf-8") + b"\r\n"
            )
        for name, filename, data in files:
            quoted = urllib.parse.quote(filename)
            ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{quoted}"\r\n'
                f"Content-Type: {ctype}\r\n\r\n".encode() + data + b"\r\n"
            )
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            f"{self.url}/api.php?{query}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "portal-sync",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )
        return self._open(req, query)


class PushRejected(Exception):
    pass


def load_config(write=False):
    cfg = {}
    if CONFIG_PATH.is_file():
        cfg = json.loads(CONFIG_PATH.read_text())
    url = os.environ.get("PH_PORTAL_URL") or cfg.get("portal_url")
    if write:
        token = os.environ.get("PH_PORTAL_WRITE_TOKEN") or cfg.get("write_token")
        if not url or not token:
            sys.exit(f"Missing portal_url/write_token: add them to {CONFIG_PATH} (see the top of this script).")
        return url, token, "api_write_token_hash"
    token = os.environ.get("PH_PORTAL_TOKEN") or cfg.get("token")
    if not url or not token:
        sys.exit(f"Missing portal_url/token: create {CONFIG_PATH} (see the top of this script).")
    return url, token


# ── Vault index ────────────────────────────────────────────


class Vault:
    def __init__(self, root):
        self.root = root
        self.sr_root = root / SR_ROOT
        self.companies = []  # (name, code, portal_client)
        for p in sorted((root / "Companies").glob("*.md")):
            fm = frontmatter(p)
            self.companies.append((p.stem, fm.get("code", ""), fm.get("portal_client", "")))
        self.people = []  # (name, company, aliases)
        for p in sorted((root / "People").glob("*.md")):
            fm = frontmatter(p)
            company = fm.get("company", "")
            self.people.append((p.stem, unlink(company if isinstance(company, str) else ""), as_list(fm.get("aliases", ""))))
        # portal_id -> (folder, linking note's vault status)
        self.linked = {}
        for note in sorted(self.sr_root.glob("*/*.md")):
            if note.name == PORTAL_NOTE:
                continue
            fm = frontmatter(note)
            if fm.get("portal_id", "").isdigit():
                self.linked.setdefault(int(fm["portal_id"]), (note.parent, fm.get("status", "")))

    def company_for(self, client):
        for name, code, pc in self.companies:
            if pc and pc.lower() == client["login_id"].lower():
                return name, code
        for name, code, _ in self.companies:
            if name.lower() == client["name"].lower():
                return name, code
        return None, None

    def contact_for(self, contact_name, company):
        """Match a portal contact name to a People/ note at this company.

        Returns (name, how): how is "" for an exact match, "alias" for one of
        the note's `aliases:`, "first name" when the portal gave just a first
        name and exactly one person there has it. Ambiguous -> ("", "").
        """
        wanted = " ".join(contact_name.split()).lower()
        people = [(n, a) for n, c, a in self.people if c == company]
        for how, hits in (
            ("", [n for n, _ in people if n.lower() == wanted]),
            ("alias", [n for n, a in people if wanted in (x.lower() for x in a)]),
            ("first name", [n for n, _ in people if " " not in wanted and n.split()[0].lower() == wanted]),
        ):
            if len(hits) == 1:
                return hits[0], how
            if hits:
                return "", ""
        return "", ""


# ── Rendering ──────────────────────────────────────────────


class Renderer:
    def __init__(self, data):
        self.tz = ZoneInfo(data["timezone"])
        self.statuses = data["statuses"]
        self.priorities = data["priorities"]
        self.fields = data["fields"]

    def local(self, iso, fmt="%Y-%m-%d %H:%M"):
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone(self.tz).strftime(fmt)

    def value(self, field, v):
        if field == "status":
            return self.statuses.get(v, v)
        if field == "priority":
            return self.priorities.get(v, v)
        return v if v != "" else "(blank)"

    def initial_request(self, template, sr, customer, contact):
        opened = self.local(sr["created_at"], "%Y-%m-%d")
        submitter = sr["history"][0]["actor_name"] if sr["history"] else sr["contact_name"]
        description = (
            sr["description"].strip()
            + f"\n\n*Submitted through the client portal as {sr['ref']} by {submitter}"
            + f" on {opened}. Live portal data, history and files: `{PORTAL_NOTE}` in this folder.*"
        )
        body = (
            template.replace("{{VALUE:customer}}", customer)
            .replace("{{VALUE:contact}}", contact)
            .replace("{{VALUE:description}}", description)
            .replace("{{DATE:YYYY-MM-DD}}", opened)
        )
        if not contact:
            body = body.replace('contact: "[[]]"', "contact:")
        # portal_id is the link key; add it at the end of the frontmatter.
        return re.sub(r"^(---\r?\n.*?\r?\n)(---)", rf"\g<1>portal_id: {sr['id']}\n\2", body, count=1, flags=re.S)

    def portal_note(self, sr, local_files):
        def link(f):
            path = local_files.get(f["id"])
            if f["deleted_at"]:
                return f"~~{f['filename']}~~ (deleted in portal by {f['deleted_by']}" + (
                    f"; local copy kept: [[{path}|{Path(path).name}]])" if path else ")"
                )
            if not path:
                return f"{f['filename']} (not downloaded)"
            if Path(path).suffix.lower() in IMAGE_EXT:
                return f"{f['filename']}\n  ![[{path}|400]]"
            return f"[[{path}|{f['filename']}]]"

        contact = " · ".join(x for x in (sr["contact_name"], sr["contact_phone"], sr["contact_email"]) if x)
        lines = [
            "---",
            f"portal_ref: {sr['ref']}",
            f"portal_status: {sr['status']}",
            f"portal_priority: {sr['priority']}",
            f"portal_updated: {self.local(sr['updated_at'])}",
            f"portal_url: {sr['url']}",
            "---",
            "",
            "> [!info] Synced from the client portal by `Scripts/portal-sync.py`",
            "> Overwritten on every sync — keep your own notes in the other files in this folder.",
            "",
            f"# {sr['ref']} · {sr['title']}",
            "",
            "| | |",
            "| --- | --- |",
            f"| Client | {sr['client']['name']} (`{sr['client']['login_id']}`) |",
            f"| Status | {self.value('status', sr['status'])} |",
            f"| Priority | {self.value('priority', sr['priority'])} |",
            f"| Contact | {contact.replace('|', '/')} |",
            f"| Opened | {self.local(sr['created_at'])} |",
            f"| Updated | {self.local(sr['updated_at'])} |",
            f"| Portal | [Open in admin]({sr['url']}) |",
            "",
            "## Description (current)",
            "",
            sr["description"].strip(),
            "",
            "## History",
            "",
        ]
        for h in sr["history"]:
            label = {"created": "created", "updated": "updated", "file_deleted": "deleted a file"}.get(
                h["action"], h["action"]
            )
            head = f"### {self.local(h['at'])} · {h['actor_name']} ({h['actor_type']}) · {label}"
            if h["internal"]:
                head += " · 🔒 internal"
            lines += [head, ""]
            for field, (old, new) in h["changes"].items():
                name = self.fields.get(field, field)
                if field == "description":
                    lines += [f"- **{name}** changed to:", "", quote(new), ""]
                else:
                    lines.append(f"- **{name}:** {self.value(field, old)} → {self.value(field, new)}")
            if h["note"]:
                lines += ["", quote(h["note"].strip()), ""]
            for f in h["files"]:
                lines.append(f"- 📎 {link(f)}")
            lines.append("")
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).rstrip() + "\n"


# ── Documents (vault → portal) ─────────────────────────────

# Must match the portal's DOC_CATEGORIES (app/docs.php) and UPLOAD_TYPES (app/files.php).
DOC_CATEGORIES = {"proposal", "infrastructure", "service_summary", "other"}
UPLOAD_EXT = {
    "jpg", "jpeg", "png", "gif", "webp", "heic", "heif", "pdf", "txt", "log", "csv", "rtf", "doc", "docx",
    "xls", "xlsx", "ppt", "pptx", "odt", "ods", "eml", "msg", "zip", "7z", "mp4", "mov",
}
SKIP_DIRS = {"Templates", "Scripts", "node_modules"}
FRONTMATTER_RE = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n(?:---|\.\.\.)[ \t]*(?:\r?\n|\Z)", re.S)


def doc_slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:80].strip("-") or "document"


def category_key(s):
    k = re.sub(r"[\s-]+", "_", s.strip().lower()).strip("_")
    if k in DOC_CATEGORIES:
        return k
    plural = {"proposals": "proposal", "service_summaries": "service_summary"}
    return plural.get(k)


def content_hash(title, category, body, files):
    """Same fingerprint as the portal's doc_content_hash() (app/docs.php)."""
    lines = sorted(f"{sha} {name}" for name, sha in files.items())
    return hashlib.sha256("\n".join([title, category, body, "\n".join(lines)]).encode("utf-8")).hexdigest()


def note_body(text):
    body = FRONTMATTER_RE.sub("", text, count=1)
    return body.replace("\r\n", "\n").replace("\r", "\n").strip()


def file_refs(body):
    """Attachment targets the note embeds or links, as written (deduplicated, in order)."""
    scan = re.sub(r"^(`{3,}|~{3,}).*?^\1", "", body, flags=re.S | re.M)  # not inside fenced code
    scan = re.sub(r"`[^`\n]+`", "", scan)
    scan = re.sub(r"%%.*?%%", "", scan, flags=re.S)
    out = []
    for m in re.finditer(r"!?\[\[([^\[\]|#]+)(?:#[^\[\]|]*)?(?:\\?\|[^\[\]]*)?\]\]", scan):
        out.append(m.group(1).strip())
    for m in re.finditer(r"!?\[[^\]]*\]\(\s*(<[^>]+>|[^)\s]+)", scan):
        target = m.group(1).strip("<>")
        if not re.match(r"^[a-z][a-z0-9+.-]*:|^#", target, re.I):
            out.append(urllib.parse.unquote(target))
    seen, refs = set(), []
    for t in out:
        ext = Path(t).suffix.lower().lstrip(".")
        if ext and ext != "md" and t not in seen:
            seen.add(t)
            refs.append(t)
    return refs


class AttachmentIndex:
    """Find vault files the way Obsidian resolves links: path, then same folder, then by name."""

    def __init__(self, root):
        self.root = root
        self.by_name = {}
        for path in root.rglob("*"):
            rel = path.relative_to(root)
            if any(part.startswith(".") or part == "node_modules" for part in rel.parts) or not path.is_file():
                continue
            if path.suffix.lower() != ".md":
                self.by_name.setdefault(path.name.lower(), []).append(path)

    def resolve(self, target, note):
        for candidate in (note.parent / target, self.root / target):
            if candidate.is_file():
                return candidate
        hits = self.by_name.get(Path(target).name.lower(), [])
        same_dir = [h for h in hits if h.parent == note.parent]
        if same_dir or hits:
            return (same_dir or sorted(hits, key=lambda h: len(h.parts)))[0]
        return None


def set_frontmatter_key(path, key, value):
    """Add `key: value` at the end of the note's frontmatter (only if it isn't there)."""
    text = path.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m or re.search(rf"^{re.escape(key)}:", m.group(1), re.M):
        return
    end = m.start(1) + len(m.group(1))
    path.write_text(text[:end] + f"\n{key}: {value}" + text[end:], encoding="utf-8")


def find_portal_notes(root):
    for note in sorted(root.rglob("*.md")):
        rel = note.relative_to(root)
        if any(part.startswith(".") or part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        fm = frontmatter(note)
        if fm.get("portal_doc"):
            yield note, fm


def push_documents(args):
    portal = Portal(*load_config(write=True))
    vault = Vault(args.vault)
    index = AttachmentIndex(args.vault)
    remote = {(d["client"].lower(), d["slug"]): d for d in json.loads(portal.get("p=docs"))["docs"]}
    company_client = {name.lower(): pc for name, _, pc in vault.companies if pc}

    results, warnings, unchanged, claimed = [], [], 0, {}
    for note, fm in find_portal_notes(args.vault):
        rel = note.relative_to(args.vault).as_posix()
        status = fm.get("portal_doc", "").strip().lower()
        if status not in ("draft", "published"):
            warnings.append(f"{rel}: portal_doc must be draft or published (got {status!r}); skipped")
            continue
        client = fm.get("portal_client", "") or company_client.get(unlink(fm.get("customer", "")).lower(), "")
        if not client:
            warnings.append(f"{rel}: no portal client: add `portal_client: <client ID>`, or a `customer:` whose company note has portal_client; skipped")
            continue
        category = category_key(fm.get("portal_category", ""))
        if not category:
            warnings.append(f"{rel}: portal_category must be one of {', '.join(sorted(DOC_CATEGORIES))}; skipped")
            continue
        text = note.read_text(encoding="utf-8")
        body = note_body(text)
        h1 = re.search(r"^#[ \t]+(.+?)[ \t#]*$", body, re.M)
        title = fm.get("portal_title", "") or (h1.group(1).strip() if h1 else note.stem)
        slug = fm.get("portal_slug", "") or doc_slug(note.stem)
        key = (client.lower(), slug)
        if key in claimed:
            warnings.append(f"{rel}: same portal_slug {slug!r} as {claimed[key]}; set a different portal_slug; skipped")
            continue
        claimed[key] = rel

        files = {}  # reference name -> (path, sha256)
        for ref in file_refs(body):
            path = index.resolve(ref, note)
            ext = Path(ref).suffix.lower().lstrip(".")
            if not path:
                warnings.append(f"{rel}: can't find {ref!r} in the vault (it'll show as missing)")
            elif ext not in UPLOAD_EXT:
                warnings.append(f"{rel}: {ref!r} — .{ext} files can't be uploaded to the portal (it'll show as missing)")
            else:
                files[ref] = (path, hashlib.sha256(path.read_bytes()).hexdigest())

        local_hash = content_hash(title, category, body, {n: sha for n, (_, sha) in files.items()})
        existing = remote.get(key)
        if existing:
            latest = existing["latest"]
            same = latest["content_hash"] == local_hash and (latest["status"] == status or latest["status"] == "published")
            if same and existing["source_name"] == note.stem:
                unchanged += 1
                if existing["archived"]:
                    warnings.append(f"{rel}: removed from the portal in admin, so the client doesn't see it")
                continue

        label = f"{client}/{slug} ({rel})"
        if args.dry_run:
            what = "new document" if not existing else ("new version" if existing["latest"]["status"] == "published" else "update draft")
            results.append(f"[dry run] {what:<13} {status:<9} {label}" + (f"  +{len(files)} files" if files else ""))
            continue

        meta = {
            "client": client, "slug": slug, "title": title, "category": category, "status": status,
            "change_note": fm.get("portal_change", ""), "source_name": note.stem, "files": list(files),
        }
        uploads = [("files[]", Path(n).name, p.read_bytes()) for n, (p, _) in files.items()]
        try:
            r = json.loads(portal.post_multipart("p=doc_push", {"meta": json.dumps(meta), "body": body}, uploads))
        except PushRejected as ex:
            warnings.append(f"{rel}: portal rejected it: {ex}")
            continue
        words = {
            "created": "created", "new_version": "new version", "draft_updated": "draft updated",
            "published": "published", "unchanged": "unchanged",
        }
        results.append(f"{words.get(r['action'], r['action']):<13} v{r['num']} {status:<9} {label}")
        if r.get("archived"):
            warnings.append(f"{rel}: removed from the portal in admin, so the client doesn't see it")
        if not fm.get("portal_slug"):
            set_frontmatter_key(note, "portal_slug", slug)

    for line in results:
        print(line)
    for w in warnings:
        print(f"warning  {w}")
    pushed = len([r for r in results if not r.startswith("[dry run]")])
    prefix = "[dry run] " if args.dry_run else ""
    print(f"{prefix}{pushed if not args.dry_run else len(results)} pushed, {unchanged} unchanged, {len(warnings)} warnings")


# ── Sync ───────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(description="Pull portal service requests into the vault.")
    ap.add_argument("ids", nargs="*", type=int, help="only these portal SR numbers (created even if closed)")
    ap.add_argument("--all", action="store_true", help="also create notes for resolved/closed SRs")
    ap.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    ap.add_argument("--push", action="store_true", help="push portal_doc notes to the portal's Documents (no SR pull)")
    ap.add_argument("--vault", type=Path, default=Path(__file__).resolve().parent.parent)
    args = ap.parse_args()

    if args.push:
        push_documents(args)
        return

    portal = Portal(*load_config())
    vault = Vault(args.vault)
    data = json.loads(portal.get("p=srs"))
    r = Renderer(data)
    template = (args.vault / TEMPLATE_PATH).read_text(encoding="utf-8")

    created, updated, unchanged, warnings = [], [], 0, []
    for sr in data["srs"]:
        if args.ids and sr["id"] not in args.ids:
            continue
        tag = f"{sr['ref']} {sr['title']!r}"
        link = vault.linked.get(sr["id"])

        if link:
            folder, vault_status = link
        else:
            if not (args.ids or args.all or sr["status"] in ACTIVE_PORTAL):
                continue
            customer, code = vault.company_for(sr["client"])
            if not customer:
                warnings.append(
                    f"{tag}: no company note for portal client {sr['client']['name']!r} "
                    f"— add `portal_client: {sr['client']['login_id']}` to its Companies/ note"
                )
                continue
            if not code:
                warnings.append(f"{tag}: Companies/{customer}.md has no `code:` — needed for the folder name")
                continue
            stamp = r.local(sr["created_at"], "%Y%m%d")
            folder = vault.sr_root / f"{code}{stamp}-{safe_name(sr['title'])}"
            if folder.exists():
                folder = folder.with_name(f"{folder.name} ({sr['ref']})")
            contact, how = vault.contact_for(sr["contact_name"], customer)
            note = r.initial_request(template, sr, customer, contact)
            vault_status = "inbox"
            if not args.dry_run:
                folder.mkdir(parents=True)
                (folder / "Initial Request.md").write_text(note, encoding="utf-8")
            if not contact:
                note_on_contact = f"  (contact {sr['contact_name']!r} not matched to People/)"
            elif how:
                note_on_contact = f"  (contact {sr['contact_name']!r} → {contact}, by {how})"
            else:
                note_on_contact = ""
            created.append(f"{tag} → {SR_ROOT}/{folder.name}/{note_on_contact}")

        # Attachments: download any we don't have yet.
        folder_rel = folder.relative_to(args.vault).as_posix()
        local_files = {}
        for h in sr["history"]:
            for f in h["files"]:
                name = f"{f['id']}-{safe_name(f['filename'], 120)}"
                path = folder / FILES_DIR / name
                if not path.exists() and not f["deleted_at"] and not args.dry_run:
                    path.parent.mkdir(exist_ok=True)
                    path.write_bytes(portal.get(f"p=file&id={f['id']}"))
                if path.exists() or (args.dry_run and not f["deleted_at"]):
                    local_files[f["id"]] = f"{folder_rel}/{FILES_DIR}/{name}"

        content = r.portal_note(sr, local_files)
        pn = folder / PORTAL_NOTE
        if pn.exists() and pn.read_text(encoding="utf-8") == content:
            unchanged += 1
        else:
            if not args.dry_run:
                pn.write_text(content, encoding="utf-8")
            if link:
                updated.append(tag)

        # Status drift between the vault workflow and what the client sees.
        if vault_status in DONE_VAULT and sr["status"] in ACTIVE_PORTAL:
            warnings.append(f"{tag}: `{vault_status}` in the vault but still {r.value('status', sr['status'])!r} in the portal")
        elif vault_status not in DONE_VAULT and sr["status"] not in ACTIVE_PORTAL:
            warnings.append(f"{tag}: {r.value('status', sr['status'])!r} in the portal but `{vault_status or '(none)'}` in the vault")

    prefix = "[dry run] " if args.dry_run else ""
    for c in created:
        print(f"{prefix}created  {c}")
    for u in updated:
        print(f"{prefix}updated  {u}")
    for w in warnings:
        print(f"warning  {w}")
    print(f"{prefix}{len(created)} created, {len(updated)} updated, {unchanged} unchanged, {len(warnings)} warnings")


if __name__ == "__main__":
    main()
