---
description: Pull service requests from the propellerheads.io client portal into the vault
argument-hint: "[SR numbers…] [--dry-run] [--all]"
allowed-tools: Bash(python3 Scripts/portal-sync.py:*)
---

Run `python3 Scripts/portal-sync.py $ARGUMENTS` from the vault root.

Report back briefly:
- SR folders created and Portal.md files updated (one line each)
- Every warning, with the fix it suggests (unmapped clients, missing company codes, status drift between the vault and the portal)

If specific SR numbers were given, read the synced folder's `Initial Request.md`, `Portal.md`, and any other notes there, and summarize where the request stands, ready to start troubleshooting.

`Portal.md` is regenerated on every sync: never edit it. Put findings in `Initial Request.md`, `Analysis.md`, or another note in the folder.
