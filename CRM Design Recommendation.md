# CRM Design Recommendation — Obsidian Vault as Billing Automation Source

Starting from the billing automation goal and working backwards is the right frame — the vault isn't just notes, it's the input schema for a pipeline, and the structure has to hold up when a script parses it.

## Guiding principles

1. **Frontmatter is the API.** Canonical data lives in YAML frontmatter with typed, consistent fields. The note body is for humans and context.
2. **Stable IDs on everything.** Clients, projects, tickets, time entries, invoices all get prefixed IDs (`CLI-0001`, `PRJ-0007`, `SR-2026-0032`, `INV-2026-0005`). Never rely on filenames for identity — names can drift.
3. **Clear field ownership.** Human-owned fields are never written by the sync script. Stripe-owned fields are never hand-edited. Separate them visually in every note.
4. **Version control is mandatory.** This is financial source of truth — Obsidian Git on a private repo gives you a free audit trail and lets you `git blame` a line item.
5. **Types are enforced by templates, not convention.** Every note type gets created through a Templater template that pre-fills the full schema. No blank notes.

## Note types

### Client (`Clients/CLI-0001 Companion Animal Hospital.md`)

```yaml
---
type: client
id: CLI-0001
status: active
billing_email: ap@cah.example
billing_address: |
  123 Main St
  Chico, CA 95926
tax_id:
default_rate_usd: 150
payment_terms_days: 15
# ---- Stripe sync (do not edit) ----
stripe_customer_id:
last_synced:
---
```

### Contact (`Contacts/PER-0001 Chris Felton.md`)

Lightweight, links back to client with `client: "[[CLI-0001 Companion Animal Hospital]]"`, plus role/email/phone.

### Project / Engagement (`Projects/PRJ-0007 CAH Server Rebuild.md`)

Groups related tickets and owns the pricing model.

```yaml
---
type: project
id: PRJ-0007
client: "[[CLI-0001 Companion Animal Hospital]]"
status: active              # active | on-hold | complete
billing_model: hourly       # hourly | fixed | retainer
rate_usd: 150
fixed_price_usd:
budget_hours: 40
sow: "[[SOW-PRJ-0007]]"
opened: 2026-03-15
---
```

### Service Request / Ticket (`Service Requests/SR-2026-0032 Network redundancy.md`)

```yaml
---
type: service_request
id: SR-2026-0032
client: "[[CLI-0001 ...]]"
project: "[[PRJ-0007 ...]]"
status: in-progress          # new | in-progress | blocked | ready-to-bill | billed | closed
opened: 2026-03-10
closed:
---
```

Inside the body, a structured time log that's parseable by both Dataview and any external script with a one-line regex:

```
## Time Log
- 2026-03-12 :: 1.25h :: Initial assessment with Chris :: rate=150 :: billable=true
- 2026-03-14 :: 0.50h :: Ordered second WAN gateway :: rate=150 :: billable=true
```

### Service / Rate Card (`Services/SVC-Hourly-Standard.md`)

One file per billable SKU with a `stripe_price_id` field so the script can map line items to Stripe products cleanly.

### Invoice (`Invoices/INV-2026-0005.md`)

The critical handoff note between you and the automation:

```yaml
---
type: invoice
id: INV-2026-0005
client: "[[CLI-0001 Companion Animal Hospital]]"
period_start: 2026-03-01
period_end: 2026-03-31
status: draft               # draft | approved | sent | paid | past_due | void
approved_by:
approved_at:
line_items:
  - sr: "[[SR-2026-0032]]"
    description: Network redundancy configuration
    hours: 1.75
    rate_usd: 150
    amount_usd: 262.50
subtotal_usd: 262.50
tax_usd: 0
total_usd: 262.50
# ---- Stripe sync (do not edit) ----
stripe_invoice_id:
stripe_hosted_url:
stripe_pdf_url:
stripe_status:
amount_paid_usd:
sent_at:
paid_at:
last_synced:
---
```

### Meetings, Runbooks, Notes

Keep largely as you have them. Add `billable: true|false` to meeting frontmatter if it should show up in invoicing. Runbooks and general notes aren't in the billing schema.

## Plugins

The essentials:

- **Dataview** — rollups, invoice preview queries, client dashboards, "all ready-to-bill tickets for client X" lists.
- **Templater** — enforces every schema. No note gets created without going through a template.
- **Metadata Menu** — underrated for this use case. Enforces frontmatter types, gives you dropdowns for enum fields (status, billing_model), and is the closest thing Obsidian has to a schema validator. Pair it with Templater.
- **Obsidian Tasks** — approval checkboxes with due dates, follow-ups, recurring invoice reminders.
- **Kanban** — your Billing Queue board (Draft / Approved / Sent / Paid / Past Due), plus the pipeline boards you already have.
- **QuickAdd** — bind a hotkey that appends a time-log line to whatever ticket is open. This is the single biggest determinant of whether you actually capture billable hours.
- **Obsidian Git** — auto-commit every N minutes; your audit trail.
- **Linter** — normalizes YAML formatting so diffs stay clean and the parser stays happy.
- **Periodic Notes** — daily journal; useful for end-of-day time reconciliation.

## The billing flow

The pipeline has five stages, and each one is represented by frontmatter state changes the script can watch for:

1. **Capture.** Hours accumulate in each SR's Time Log as you work, via QuickAdd.
2. **Close out.** When a ticket is done, set `status: ready-to-bill`.
3. **Draft.** A generator script (local Python or Node) scans all `ready-to-bill` tickets per client over a date range, creates `INV-YYYY-NNNN.md` with populated line items and totals, and sets invoice `status: draft`. Can also be kicked off as a Templater command.
4. **Approve.** Review the invoice note, adjust line items, flip `status: approved`, and stamp `approved_by` and `approved_at`. The Kanban "Billing Queue" board (backed by a Dataview query on invoice status) makes this visual.
5. **Sync.** The Stripe sync script, running on a schedule:
   - Finds invoices with `status: approved` and no `stripe_invoice_id`. Creates the Stripe invoice using `stripe_customer_id` + line items (mapping through `stripe_price_id` on the Service notes). Writes back `stripe_invoice_id`, `stripe_hosted_url`, `stripe_pdf_url`, `sent_at`. Flips vault `status: sent`.
   - For all invoices with a `stripe_invoice_id`, polls Stripe for status. Writes `stripe_status`, `amount_paid_usd`, `paid_at`, `last_synced`. Flips vault `status` to `paid` or `past_due` when appropriate.

## Keeping the script and the human out of each other's way

Two rules make the two-way sync robust:

**Strict field ownership.** The invoice template visually separates human fields from the Stripe block with a comment divider. Human edits never touch the Stripe block; the script never touches anything above it. The only field both care about is the top-level `status`, and its state machine is well-defined (human flips draft→approved; script flips approved→sent→paid/past_due).

**Idempotent writes.** The sync script uses `stripe_invoice_id` as the idempotency key when creating Stripe invoices, so re-runs can't double-charge. If the field is empty, create; if it's set, only read/update.

## Suggested implementation order

1. Lock the ID scheme and schemas first. Write the Templater templates for Client, Project, SR, Invoice.
2. Migrate existing notes in a one-time script pass — add IDs, add frontmatter.
3. Turn on Obsidian Git with auto-commit.
4. Build the draft-invoice generator — still all local, no Stripe. Validate the numbers against what you'd have billed manually for a month or two.
5. Add the Stripe create-invoice step.
6. Add the scheduled poll for payment status.

Shipping in that order keeps the risky parts (actually charging clients) behind a long local validation window.

## Decisions that would sharpen this further

The answers shape some specifics above:

- **Hourly, fixed-price, retainer, or a mix?** Affects Project schema and how the draft-invoice generator groups line items.
- **Who approves?** Solo operator means self-approval; multi-operator means `performed_by` on time entries and a rule that approver ≠ logger.
- **Hosted Stripe invoice vs. emailed PDF?** Changes how much of the send flow lives in the vault vs. in Stripe's UI.
- **Retainers or credits?** Adds a Credits/Retainer note type and a balance field on Client.
