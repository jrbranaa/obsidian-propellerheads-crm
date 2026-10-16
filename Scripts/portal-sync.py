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

Usage (from anywhere):
  python3 Scripts/portal-sync.py              sync everything
  python3 Scripts/portal-sync.py 12 15        only these portal SR numbers
  python3 Scripts/portal-sync.py --dry-run    show what would change
  python3 Scripts/portal-sync.py --all        also create notes for resolved/closed SRs

Config: ~/.config/propellerheads/portal-sync.json
  {"portal_url": "https://propellerheads.io/portal", "token": "<api token>"}
(or env PH_PORTAL_URL / PH_PORTAL_TOKEN). Kept outside the vault so the token
isn't spread to every device by Obsidian Sync.
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
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
    def __init__(self, url, token):
        self.url = url.rstrip("/")
        self.token = token

    def get(self, query):
        req = urllib.request.Request(
            f"{self.url}/api.php?{query}",
            headers={"Authorization": f"Bearer {self.token}", "User-Agent": "portal-sync"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as ex:
            hint = {401: "token rejected", 404: "API disabled (api_token_hash empty) or not found"}
            sys.exit(f"Portal error {ex.code} for {query}: {hint.get(ex.code, ex.reason)}")
        except urllib.error.URLError as ex:
            sys.exit(f"Can't reach {self.url}: {ex.reason}")


def load_config():
    cfg = {}
    if CONFIG_PATH.is_file():
        cfg = json.loads(CONFIG_PATH.read_text())
    url = os.environ.get("PH_PORTAL_URL") or cfg.get("portal_url")
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


# ── Sync ───────────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser(description="Pull portal service requests into the vault.")
    ap.add_argument("ids", nargs="*", type=int, help="only these portal SR numbers (created even if closed)")
    ap.add_argument("--all", action="store_true", help="also create notes for resolved/closed SRs")
    ap.add_argument("--dry-run", action="store_true", help="report what would change, write nothing")
    ap.add_argument("--vault", type=Path, default=Path(__file__).resolve().parent.parent)
    args = ap.parse_args()

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
