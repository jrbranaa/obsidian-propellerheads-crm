# CRM Automations

Reconstructed 2026-09-01 after the originals were lost (never pushed, machine died). These are [[QuickAdd]] choices backed by templates in `Templates/`. Only **New Service Request** uses a script (`Scripts/sr-quickadd.js`); the rest are pure QuickAdd `{{VALUE:…}}` / `{{DATE:…}}` / `{{VDATE:…}}` tokens.

## The choices

| Choice | Type | What it does |
|---|---|---|
| **New Service Request** | Macro → `Scripts/sr-quickadd.js` | Pick customer from a list of `Companies/` → **auto-derives the code** from that company's `code:` frontmatter → prompts title → pick contact from that company's people (or none / free text) → optional description. Creates `Service Requests/{CODE}{YYYYMMDD}-{title}/Initial Request.md` from the SR template and opens it. |
| **New Service Request (manual)** | Template | Same output, no script. Every field is a free-text prompt (code, title, customer, contact, description). Fallback for mobile or if the script errors. |
| **Log Time (current SR)** | Capture | Appends a time-log line to the **currently open** note, at the end of its `## Time Log` section. Prompts: date (defaults today), hours, billable (true/false), notes. Produces `- [date:: 2026-09-01] [hours:: 1.25] [billable:: true] notes` — the inline-field format Dataview rolls up. |
| **Add Company** | Template | Creates `Companies/{name}.md` from `Templates/Company Template.md`. Prompts: company name, phone, code. |
| **Add Contact** | Template | Creates `People/{name}.md` from `Templates/Person Template.md`. Prompts: full name, company, phone, email. |

## Binding hotkeys

Each choice is registered as a command (`command: true`). In **Settings → Hotkeys**, search "QuickAdd" and bind, e.g.:

- `QuickAdd: New Service Request`
- `QuickAdd: Log Time (current SR)` — the highest-value one to bind; suggested `Ctrl/Cmd+Shift+T`
- `QuickAdd: Add Company`
- `QuickAdd: Add Contact`

Or run any of them from the QuickAdd command-palette entry / ribbon.

## Notes & known limitations

- **`Add Company` / `Add Contact` / manual SR prompts are free text.** Type the exact note name (no brackets) — the template wraps it in `[[ ]]`. A wrong name creates a broken link, not an error. (The scripted **New Service Request** avoids this by using pickers.)
- **Contact list in the script** is filtered to `People/` notes whose `company` frontmatter contains the chosen company name. A person with a blank/mismatched `company` won't show — use "type a name".
- The SR template contains `{{VALUE:…}}` / `{{DATE:…}}` tokens. QuickAdd (and the script) substitute them; the core **Templates** plugin does not — always create SRs through QuickAdd.
- `Scripts/sr-quickadd.js` re-implements the token substitution so one template serves both the scripted and manual choices.

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

- `.obsidian/plugins/quickadd/data.json` — 5 `choices` (1 Macro, 3 Template, 1 Capture)
- `Scripts/sr-quickadd.js` — new; the **New Service Request** macro script
- `Templates/Service Request Template.md` — switched placeholders to `{{VALUE:…}}`
- `Templates/Company Template.md` — `{{phone}}`/`{{code}}` → `{{VALUE:…}}`
- `Templates/Person Template.md` — new
