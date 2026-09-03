# CRM Automations

Reconstructed 2026-09-01 after the originals were lost (never pushed, machine died). These are [[QuickAdd]] choices backed by templates in `Templates/`. **New Service Request**, **Add Contact**, and **New Project** use scripts (`Scripts/sr-quickadd.js`, `Scripts/contact-quickadd.js`, `Scripts/project-quickadd.js`); the rest are pure QuickAdd `{{VALUE:…}}` / `{{DATE:…}}` / `{{VDATE:…}}` tokens.

## The choices

| Choice | Type | What it does |
|---|---|---|
| **New Service Request** | Macro → `Scripts/sr-quickadd.js` | Pick customer from a list of `Companies/` → **auto-derives the code** from that company's `code:` frontmatter → prompts title → pick contact from that company's people (or none / free text) → optional description. Creates `Service Requests/{CODE}{YYYYMMDD}-{title}/Initial Request.md` from the SR template and opens it. |
| **New Service Request (manual)** | Template | Same output, no script. Every field is a free-text prompt (code, title, customer, contact, description). Fallback for mobile or if the script errors. |
| **Log Time (current SR)** | Capture | Adds a row to the **currently open** note's `## Time Log` table, directly under the header separator (newest first). Prompts: date (defaults today), hours, billable (true/false), notes. Produces `\| 2026-09-01 \| 1.25 \| true \| notes \|`. |
| **Add Company** | Template | Creates `Companies/{name}.md` from `Templates/Company Template.md`. Prompts: company name, phone, code. |
| **Add Contact** | Macro → `Scripts/contact-quickadd.js` | Prompts full name → pick company from a `Companies/` picker (or *none* / *add new company* — the latter prompts name/phone/code and creates the company first) → optional phone/email. Creates `People/{name}.md` from `Templates/Person Template.md` and opens it. |
| **New Project** | Macro → `Scripts/project-quickadd.js` | Prompts project name → pick client from `Companies/` → pick contact from that client's `People/` (or none / free text) → pick billing model (`hourly` / `fixed` / `not-to-exceed`) → quote/cap and/or budget hours as the model warrants → opened date (defaults today) → optional scope. Creates `Projects/{name}.md` from `Templates/Project Template.md` and opens it. Empty `contact` / `quote_usd` / `budget_hours` lines are dropped. |

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

Multi-visit / scoped engagements get a **Project** note (`Projects/{name}.md`, `type: project`) that owns scope, phases, billing model, and a rollup — but **not** the work. Work, time, and billable status stay on child Service Requests.

- SRs link up via a `project:` frontmatter field (blank for break/fix). **New Service Request** offers a project picker filtered to `Projects/` notes whose `client` matches the chosen customer; add it by hand on existing SRs.
- The Project template's Dataview / `dataviewjs` blocks list the linked SRs and sum logged + billable hours (parsed from each SR's `## Time Log` table), plus remaining vs. `budget_hours` when set.
- Rule of thumb: default to an SR; promote to a Project when the work spans 3+ sessions / 2+ weeks, has a quote or fixed price, or has phases to report on. See `CRM Design Recommendation.md` for the fuller rationale.

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
- `Templates/Company Template.md` — `{{phone}}`/`{{code}}` → `{{VALUE:…}}`
- `Templates/Person Template.md` — new
- `Templates/Project Template.md` — new; `type: project`, SR rollup + time rollup
