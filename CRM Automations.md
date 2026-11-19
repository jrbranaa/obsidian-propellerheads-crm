# CRM Automations

Reconstructed 2026-09-01 after the originals were lost (never pushed, machine died). These are [[QuickAdd]] choices backed by templates in `Templates/`. **New Service Request**, **Add Contact**, and **New Project** use scripts (`Scripts/sr-quickadd.js`, `Scripts/contact-quickadd.js`, `Scripts/project-quickadd.js`); the rest are pure QuickAdd `{{VALUE:…}}` / `{{DATE:…}}` / `{{VDATE:…}}` tokens.

## The choices

| Choice | Type | What it does |
|---|---|---|
| **New Service Request** | Macro → `Scripts/sr-quickadd.js` | Pick customer from a list of `Companies/` → **auto-derives the code** from that company's `code:` frontmatter → prompts title → pick contact from that company's people (or none / free text) → optional description. Creates `Service Requests/{CODE}{YYYYMMDD}-{title}/Initial Request.md` from the SR template and opens it. |
| **New Service Request (manual)** | Template | Same output, no script. Every field is a free-text prompt (code, title, customer, contact, description). Fallback for mobile or if the script errors. |
| **Log Time (current SR)** | Capture | Adds a row to the **currently open** note's `## Time Log` table, directly under the header separator (newest first). Prompts: date (defaults today), hours, billable (true/false), notes. Produces `\| 2026-09-01 \| 1.25 \| true \| notes \|`. |
| **Add Company** | Template | Creates `Companies/{name}.md` from `Templates/Company Template.md`. Prompts: company name, `category` (Customer / Vendor / Prospect — a QuickAdd `{{VALUE:a,b,c}}` dropdown), phone, code. |
| **Add Contact** | Macro → `Scripts/contact-quickadd.js` | Prompts full name → pick company from a `Companies/` picker (or *none* / *add new company* — the latter prompts name/phone/code and creates the company first) → optional phone/email. Creates `People/{name}.md` from `Templates/Person Template.md` and opens it. |
| **New Project** | Macro → `Scripts/project-quickadd.js` | Prompts project name → pick client from `Companies/` → **derives code** from the company's `code:` frontmatter (else prompts) → pick contact from that client's `People/` (or none / free text) → pick billing model (`hourly` / `fixed` / `not-to-exceed`) → quote/cap and/or budget hours as the model warrants → opened date (defaults today) → optional scope. Creates `Projects/{CODE}-{name}/{CODE}-{name}.md` from `Templates/Project Template.md` and opens it; ancillary notes go in the same folder (SR-style). Empty `contact` / `quote_usd` / `budget_hours` lines are dropped. |

## Binding hotkeys

Each choice is registered as a command (`command: true`). In **Settings → Hotkeys**, search "QuickAdd" and bind, e.g.:

- `QuickAdd: New Service Request`
- `QuickAdd: Log Time (current SR)` — the highest-value one to bind; suggested `Ctrl/Cmd+Shift+T`
- `QuickAdd: Add Company`
- `QuickAdd: Add Contact`
- `QuickAdd: New Project`

Or run any of them from the QuickAdd command-palette entry / ribbon.

## Notes & known limitations

- **`Add Company` and manual SR prompts are free text.** Type the exact note name (no brackets) — the template wraps it in `[[ ]]`. A wrong name creates a broken link, not an error. (The scripted **New Service Request** and **Add Contact** avoid this by using pickers.)
- **Contact list in the SR script** is filtered to `People/` notes whose `company` frontmatter contains the chosen company name. A person with a blank/mismatched `company` won't show — use "type a name".
- **`Log Time` depends on the `\| --- \| --- \| --- \| --- \|` separator row** in the SR template's `## Time Log` table — that's the anchor new rows are inserted after. SRs created before this change have the old blank section; paste the two header rows in to start logging.
- The SR template contains `{{VALUE:…}}` / `{{DATE:…}}` tokens. QuickAdd (and the script) substitute them; the core **Templates** plugin does not — always create SRs through QuickAdd.
- `Scripts/sr-quickadd.js` re-implements the token substitution so one template serves both the scripted and manual choices.

## Projects

Multi-visit / scoped engagements get a **Project** folder (`Projects/{CODE}-{name}/`, SR-style) whose main note `{CODE}-{name}.md` (`type: project`) owns scope, phases, billing model, and a rollup — but **not** the work. Ancillary notes (quotes, diagrams, call notes) live in the same folder. Work, time, and billable status stay on child Service Requests.

- SRs link up via a `project:` frontmatter field (blank for break/fix). **New Service Request** offers a project picker filtered to `Projects/` notes whose `client` matches the chosen customer; add it by hand on existing SRs.
- The Project template's Dataview / `dataviewjs` blocks list the linked SRs and sum logged + billable hours (parsed from each SR's `## Time Log` table), plus remaining vs. `budget_hours` when set.
- Rule of thumb: default to an SR; promote to a Project when the work spans 3+ sessions / 2+ weeks, has a quote or fixed price, or has phases to report on. See `CRM Design Recommendation.md` for the fuller rationale.

## Proactive improvements (value add, no charge)

Improvements you make on your own, which the client didn't ask for and isn't paying for, are ordinary SRs marked `origin: proactive`. Client-initiated SRs are `origin: client`. Everything else works the same: same folder, time log, `project:` link and promotion to a Project.

- **Creating one:** **New Service Request** asks "Client request / Proactive improvement (no charge)" right after the customer. The manual choice shows the same dropdown. Portal-synced SRs are always `client`.
- **Time:** log it as usual with `billable` = `false`, so Project rollups still show the effort. (The Log Time capture can't change its default by origin, so pick `false` yourself.)
- **Closing:** set these to `completed`, never `bill`. The Dashboard's Ready to Bill list leaves out `proactive` SRs anyway.
- **Reporting:** the Dashboard's **Proactive Improvements** table lists them by client. In each Summary of Services, add a **"Proactive improvements (no charge)"** section that says what you did and how it helps the client (reliability, security, less staff hassle). Don't show hours or a dollar value, and keep these items off the Invoice Line Items document.
- **Telling them apart:** if the client asked for it, it's `origin: client`, even if you choose to waive the charge. Log that time as `billable: false` with a note. This keeps the value-add list to work you actually started yourself.
- All existing SRs were set to `origin: client` on 2026-11-18.

## Version control

`git init` at the vault root, 2026-09-01. The repo tracks **CRM functionality only** — see `.gitignore`. Notes and CRM data (Companies, People, Service Requests, Meetings, Notes, Sales, images) are **not** tracked; Obsidian Sync remains the source of truth for those.

**Tracked:** `.obsidian/*.json`, each plugin's `manifest.json` + `data.json`, `Templates/`, `Scripts/`, `Dashboard.md`, `Runbooks/Runbook Template.md`, this file, `CRM Design Recommendation.md`.

**Not tracked:** plugin `main.js` / `styles.css` (re-installed from the community store), `workspace.json`, `.claude/`, all note folders and images.

### Reconstructing on a fresh machine

1. Clone the repo over an (empty or Sync-populated) vault folder.
2. In Obsidian, enable community plugins and install: **Dataview, QuickAdd, Templater, Meta Bind, Kanban** — versions are pinned in each `.obsidian/plugins/*/manifest.json`.
   - Kanban 2.0.51 came from the `community-archive/obsidian-kanban` fork (original repo was taken down). *(Kanban is being retired — `Service Requests/Service Requests.md` board is defunct.)*
3. The tracked `data.json` files restore all plugin config (QuickAdd choices, etc.). Reload Obsidian.
4. Re-bind hotkeys (Settings → Hotkeys — not tracked, they live in `.obsidian/hotkeys.json` which *is* tracked, so this may already be done).

## Files touched in the reconstruction

- `.obsidian/plugins/quickadd/data.json` — 6 `choices` (3 Macro, 2 Template, 1 Capture)
- `Scripts/sr-quickadd.js` — new; the **New Service Request** macro script (also does the project picker)
- `Scripts/contact-quickadd.js` — new; the **Add Contact** macro script (company picker + inline add-company)
- `Scripts/project-quickadd.js` — new; the **New Project** macro script
- `Templates/Service Request Template.md` — switched placeholders to `{{VALUE:…}}`; `## Time Log` is now a Markdown table; added `project:` frontmatter
- `Templates/Company Template.md` — `{{phone}}`/`{{code}}` → `{{VALUE:…}}`; added `category` frontmatter (Customer / Vendor / Prospect dropdown) and a `## Projects` Dataview (Project / contact / status / billing_model / opened / closed). Both backfilled into existing company notes.
- `Templates/Person Template.md` — new
- `Templates/Project Template.md` — new; `type: project`, SR rollup + time rollup. Lives at `Projects/{CODE}-{name}/{CODE}-{name}.md`

## Portal sync (client portal → vault)

Service requests submitted through the client portal (`propellerheads.io/portal`) are pulled into the vault by `Scripts/portal-sync.py`. It only reads from the portal and never writes back. Run it with `/sync-portal` in Claude Code (from the vault root; `.claude/commands/sync-portal.md`) or directly: `python3 Scripts/portal-sync.py [SR numbers…] [--dry-run] [--all]`. Needs only Python 3.9+.

- **New portal SR (still open there)** → creates `Service Requests/{CODE}{YYYYMMDD}-{title}/Initial Request.md` from the SR template, `status: inbox`, plus `portal_id: N` in the frontmatter. That note is written once and then belongs to you, so it shows up on the Dashboard like any other SR.
- **Every linked SR** → (re)writes `Portal.md` in the same folder: current portal fields, contact phone/email, the full change log (including 🔒 internal notes) and attachments, which download to `Portal files/`. **Portal.md is overwritten on every sync, so never edit it.** It has no `status`/`customer`/`opened` fields, so Dataview queries ignore it.
- **Linking an SR you created by hand**: add `portal_id: N` (the number from `SR-000N`) to its note's frontmatter. The next sync puts `Portal.md` in that folder instead of creating a new one.
- **Customer mapping**: `portal_client: <client login ID>` in the company note's frontmatter (now in the Company template). If it's missing, the sync falls back to matching the company note's name to the portal client name. Contacts are matched to that company's `People/` notes by exact name, then by the person's `aliases:` (e.g. `Candace`, `Candice Smoot`), then by first name alone if exactly one person there has it. Alias and first-name matches are listed in the sync output so a wrong guess is easy to spot. If nothing matches, or more than one person does, `contact:` is left blank and the portal contact details stay in Portal.md. The contact is only filled in when the note is created.
- **Status**: vault `status` (inbox/next/…/bill) and portal status (what the client sees) are separate. The sync never changes either one, but it warns when they disagree: completed here but still open in the portal, or the other way round.
- Resolved/closed portal SRs only get a new note with `--all`, or when you name them by number.
- **Config**: `~/.config/propellerheads/portal-sync.json` → `{"portal_url": "https://propellerheads.io/portal", "token": "…"}`. It's kept outside the vault so Obsidian Sync doesn't copy the token to every device. The server stores only the token's hash (`api_token_hash` in the portal's `app/config.php`; `php app/bin/api-token.php` generates a pair).

## Portal documents (vault → client portal)

Any note can be published to a client's **Documents** tab in the portal (proposals, infrastructure docs, service summaries). Mark it in the frontmatter (or start from `Templates/Portal Document Template.md`):

```yaml
portal_doc: published            # or draft (clients never see drafts)
portal_category: infrastructure  # proposal | infrastructure | service_summary | other
portal_client: sah               # optional if customer: "[[Company]]" is set and that company has portal_client
portal_title: Network Overview   # optional; defaults to the first # heading, then the file name
portal_change: Replaced the firewall  # optional; shown to the client next to this version
```

Then run `python3 Scripts/portal-sync.py --push` (or `--push --dry-run` first). It only pushes notes that changed since the last push, and reports anything it skipped and why.

- **Versions**: pushing changed content on top of a published version makes a new version (v2, v3…). The client sees the newest published one with its "Updated" date and can open older ones. While a note is `draft`, each push overwrites the same draft, so the client keeps seeing the last published version until you flip it to `published`.
- **`portal_slug`** is added to the note on its first push. It's the document's identity, so you can rename or move the note freely. Change it only if you want a new, separate document.
- **Images and files**: `![[diagram.png]]`, `[[Quote.pdf]]` and `![x](attachments/a.png)` are uploaded with the note. Same file types as SR attachments: images, PDF, Office, text, zip. SVG and Excalidraw can't be uploaded, so export them to PNG.
- **Links** to other notes (`[[SAH Firewall]]`) become portal links only if that note is also a published document for the same client. Otherwise they show as plain text.
- **Rendered on the portal**: headings, tables, callouts, task lists, code blocks, highlights. Not rendered: Dataview blocks (dropped), `%% comments %%` (dropped), embedded notes (shown as a link).
- **Removing** a document: deleting or un-marking the note does **not** take it off the portal. Use the portal admin (Documents → the document → Remove from portal, or Hide from client on one version).
- **Config**: needs `"write_token"` in `~/.config/propellerheads/portal-sync.json`. It's separate from the read token, and its hash goes in the portal's `api_write_token_hash`. Generate it with `php app/bin/api-token.php`.
