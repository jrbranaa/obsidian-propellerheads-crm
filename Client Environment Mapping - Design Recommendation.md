---
type: design_recommendation
status: draft
created: 2026-09-02
---

# Client Environment Mapping — Design Recommendation

Goal: map each client's environment (devices, network, circuits, line-of-business apps, dependencies) into a structured record that (a) drives automated troubleshooting internally and (b) can be published to the client as a friendly read-only website.

Your vault already answers most of the shape question. `Companion Animal Hospital.md` surfaces People and Service Requests as folders of frontmatter notes pulled together by Dataview. And `Notes/CAH - Network and Infrastructure.md` already exists — a rich human narrative of CAH's environment, but with most inventory fields still prose placeholders and nothing a script can query. That note is the human half; this design adds the structured half (`environments/CAH/environment.yaml`) and keeps the two linked.

## Guiding principles

1. **Structured data is the API, prose is for humans.** The machine-readable inventory + dependency graph is the source of truth. Markdown notes wrap it with the "how it's wired and why" narrative.
2. **One source of truth per client, everything else generated.** Author once; generate the JSON for tooling, the Obsidian summary, and the client site from it. Never hand-maintain the same fact in two places.
3. **Stable IDs on every device, circuit, and app.** `srv01`, `fw01`, `prn-reception`, `circuit-primary`, `app-intravet`. Filenames and labels drift; IDs don't. Dependencies reference IDs.
4. **Secrets never enter the repo.** Store *references* to password-manager items, not credentials. The client site is built from a redacted projection anyway.
5. **Version control is the audit trail.** Git history of every environment change is gold for an MSP. Caveat for *this* repo: `.gitignore` tracks CRM *functionality* only (`Templates/`, `Scripts/`, `Runbooks/` template, a few docs) and deliberately excludes client data — including the new `environments/` folder. So `environments/CAH/environment.yaml` is **not tracked here** as written — see "Where the data is tracked" below for the decision.
6. **The dependency graph is the point.** "IntraVet down → check SQL on srv01 → check RDS licensing → check internal DNS" only works automatically if those edges are encoded as data.

## Format: layer them, don't pick one

| Layer                 | Format                        | Role                                                                                                                               |
| --------------------- | ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| Source of truth       | **YAML**, one file per client | Hand-editable, supports comments, clean git diffs, nested structure without pain. What scripts and any LLM-assisted triage read.   |
| Obsidian surface      | **Markdown**                  | The prose: architecture, rationale, links to runbooks and tickets. Graph participation. Generated or semi-generated from the YAML. |
| Tooling / client site | **JSON**                      | Build artifact from the YAML. Never hand-edited.                                                                                   |

MD-only breaks down once a client has 25 devices with 10 fields each — you can't query "all printers still on WSD ports" out of prose. JSON-only is miserable to author by hand. YAML is the spine; the rest is derived.

## Where it lives in the vault

Layout as built (2026-09-02, folder moved 2026-09-03):

```
environments/                           # top-level, one subfolder per client
  CAH/
    environment.yaml                    # source of truth (hand-authored)  ← BUILT
    workstations.observed.yaml          # collector-owned (not yet — collector step)
Notes/
  CAH - Network and Infrastructure.md   # existing human note; now points at the YAML,
                                        #   with <!-- env:begin/end --> markers for the
                                        #   generated inventory table               ← WIRED
Templates/
  Environment Template.yaml             # blank starting point                       ← BUILT
  environment.schema.json               # JSON Schema env-build.js validates against  ← BUILT
Scripts/
  env-build.js                          # validate + ref-check + emit dist/<CODE>.json ← BUILT (v1)
  package.json                          # js-yaml, ajv, ajv-formats
dist/                                   # generated JSON            (gitignored)
drift/                                  # generated drift reports   (gitignored)
```

`environments/<CODE>` is keyed by the client `code:` (matches `Companies/<Client>.md` frontmatter), not the client name — stable, path-safe, and what `env-build.js --code` takes.

The collector node and the client-site content repos live **outside** this vault (they're infrastructure, not notes) — see their own sections.

### Where the data is tracked

The vault repo's `.gitignore` is "functionality only" — everything at the vault root is ignored, then `Templates/`, `Scripts/`, `Runbooks/`-template and a few docs are re-included; `Companies/`, `Notes/`, `Service Requests/` and `environments/` are not.

**Decided (2026-09-03):** `environments/` is its **own git repo**, nested inside the vault directory. `git init` in `environments/`, its own `.gitignore` + `README.md`, initial commit done. The vault repo ignores the whole folder (matched by `/*`) and the nested `.git` doesn't disturb it — two independent repos sharing a tree:

- **vault repo** → CRM functionality (`Templates/`, `Scripts/`, the design doc — all tracked)
- **`environments/` repo** → client environment data, its own history and access control

`env-build.js` reads the files by path and doesn't care about the git boundary. Still TODO: add a private remote and push.

**One monorepo for all clients, not repo-per-customer** (decided 2026-09-03) — few clients, small trusted team, `op://` refs only. Guardrail: collector nodes must **not** push to this repo (a node on a client LAN that can push here can clone here). The collector writes `*.observed.yaml` to its own isolated destination; you pull it in and commit. Full reasoning + the triggers that would flip this to per-client repos are in `environments/DECISIONS.md`.

Rejected: a submodule (only useful for pinning vault state to an exact environments commit — not needed); re-including `/environments/` in the vault repo (mixes client infra detail into the "how the CRM works" repo); relying on Obsidian Sync alone (snapshot restore, ~1-month rolling retention, no diffs on YAML, no attribution for collector writes).

## The environment.yaml schema

```yaml
client: Companion Animal Hospital
code: CAH

sites:
  - id: main
    name: Main clinic
    address: |
      ...
    hours: "M-F 8-6, Sat 8-12"
    primary_contact: "[[Chris Felton]]"

escalation:
  - { tier: 1, who: "[[Chris Felton]]", contact: "..." }
  - { tier: 2, who: practice manager, contact: "..." }

network:
  subnets:
    - { id: lan, cidr: 192.168.1.0/24, vlan: 1, dhcp_pool: ".100-.199", reserved_infra: ".240-.250" }
  dns:
    internal_namespace: lan.companionvet.com
    resolver: "UniFi gateway - Local DNS Records"
  gateway: { device: fw01, model: "UniFi UDM" }

circuits:
  - id: circuit-primary
    role: primary
    provider: Comcast
    account_ref: "op://PropellerHeads/CAH-Comcast"   # reference, not the number
    down_mbps: 300
    up_mbps: 30
    static_ips: ["x.x.x.x/29"]
    support_phone: "1-800-..."
  - id: circuit-backup
    role: backup
    provider: Verizon
    notes: "Installed under CAH20260420"

devices:
  - id: srv01
    type: server                 # server | workstation | printer | switch | ap | firewall | nas | ups | other
    make_model: "Dell PowerEdge ..."
    serial: "..."
    asset_tag: "..."
    site: main
    location: "server closet"
    mac: "..."
    ip: { address: 192.168.1.10, assignment: static }
    hostname: srv01
    os: "Windows Server 2019"
    firmware: "..."
    roles: [rds-host, intravet-sql, print-service-planned]
    purchased: 2020-02
    warranty_expires: 2027-03
    monitored_by: "..."
    internal_only: true
    notes: "Server rebuild project cancelled 2026-08-31; to be repurposed for local roles."

  - id: prn-reception
    type: printer
    make_model: "..."
    site: main
    location: "front desk"
    ip: { address: 192.168.1.241, assignment: static }
    hostname: prn-reception.lan.companionvet.com
    queue_name: reception        # owned by IntraVet - DO NOT RENAME (see CAH Printing runbook)
    port_type: "Standard TCP/IP RAW 9100"
    firmware: "..."
    source: declared             # declared | unifi | scan | snmp | endpoint | manual
    last_seen:                   # written by the collector merge

  # Devices that can't be agent-inventoried (x-ray consoles, lab analyzers, non-UniFi PBX)
  - id: xray-dr
    type: other
    subtype: imaging
    make_model: "Sound / DR panel + acquisition PC"
    site: main
    location: "radiology"
    ip: { address: 192.168.1.83, assignment: static }
    depends_on: [dns-internal]
    criticality: high
    vendor: vendor-sound
    source: manual
    last_verified: 2026-09-02
    notes: "Acquisition PC is Win10 LTSC, vendor-managed, do NOT patch or join anything. Console UI on :80."

  # Commodity workstations are NOT hand-authored here. The collector owns them
  # (environments/CAH/workstations.observed.yaml). Only hand-author a workstation in
  # this file when it has a role or quirk worth pinning:
  - id: ws-reception-1
    type: workstation
    site: main
    location: "front desk"
    roles: [rx-label-printer-host]
    notes: "Only machine with the Brady label-printer queue. Do not re-image without re-adding it."
    # ip / os / serial / firmware come from the collector merge, not from here

applications:
  - id: app-intravet
    name: IntraVet
    vendor: Patterson
    account_id_ref: "CAH phone number - see Companies/Intravet.md"
    runs_on: srv01
    depends_on: [srv01, dns-internal, prn-reception, rds-licensing]
    criticality: critical
    support: { phone: "800-422-8875", portal: "..." }
    notes: "Migrating to cloud/SaaS PMS - see CAH20260818 evaluation."

vendors:
  - { id: vendor-patterson, name: "Patterson / IntraVet", supports: [app-intravet], account_ref: "...", phone: "800-422-8875", portal: "..." }
  - { id: vendor-unifi, name: "Ubiquiti / UniFi", supports: [fw01, network] }

credentials:                      # REFERENCES ONLY - never secrets in git
  - { id: cred-srv01-admin, for: srv01, vault: 1Password, item: "op://PropellerHeads/CAH-SRV01" }
  - { id: cred-unifi, for: fw01, vault: 1Password, item: "op://PropellerHeads/CAH-UniFi" }

dependencies:                     # the troubleshooting graph - service -> what it needs
  - { service: printing, requires: [dns-internal, "prn-* static IPs", "TCP/IP RAW 9100 ports (no WSD)"] }
  - { service: intravet, requires: [srv01, "srv01 SQL service", rds-licensing, dns-internal] }
  - { service: internet, requires: [circuit-primary], failover: circuit-backup }

monitoring:
  - { target: srv01, by: "...", checks: [ping, disk, sql-service], alert_to: "..." }

runbooks:
  - "[[CAH Printing]]"
  - "[[Resetting RD License Grace Period]]"
  - "[[Adding Remote Access User]]"

related_tickets_query: 'FROM "Service Requests" WHERE customer = [[Companion Animal Hospital]]'
```

### Field conventions

- **IDs** are lowercase, dash-free where practical, unique within the file. Every `depends_on` / `requires` / `supports` entry is an ID defined elsewhere in the file (the build script validates this).
- **`ip.assignment`** is one of `static` | `dhcp` | `reservation`.
- **`criticality`** is `critical` | `high` | `normal` | `low` — drives triage order and monitoring.
- **`source`** is `declared` | `unifi` | `scan` | `snmp` | `endpoint` | `manual` — where the entry came from. Hand-authored entries are `declared`; the collector sets the rest.
- **`*_ref`** fields hold a pointer to where the real value lives (1Password, another note), never the value.

## Secrets — 1Password

Decided: **1Password** is the credential store, referenced by `op://` secret-reference URIs (`op://<vault>/<item>/<field>`). Nothing sensitive lands in the repo.

- `environment.yaml` `credentials:` and `*_ref` fields hold `op://` URIs only.
- Anything that needs a real secret at runtime — the build script, the collector node, the site deploy — resolves it with the **1Password CLI** (`op read "op://…"`) authenticated by a scoped **service-account token** (`OP_SERVICE_ACCOUNT_TOKEN` in the environment, never on disk), or a **1Password Connect** container for the always-on collector node.
- Give the collector node its own service account with read access to one vault per client (`PropellerHeads-CAH`, etc.), so a compromised node can't read every client's secrets.
- `.gitignore` already exists; add `dist/` and `drift/` (pure build artifacts). Keep `*.observed.yaml` tracked — it's redaction-safe (IPs/versions, no secrets) and the history is useful.

## Internal vs. client-facing

One source of truth, visibility flags, build-time filtering:

- `internal_only: true` on a device / circuit / app hides the whole entity from the client site.
- `visibility: internal` on a note or list entry hides that line.
- The client build (`env-build.js --target client`) strips anything flagged and emits a friendly view: sites, circuits (provider + speed, not account numbers), key equipment (what it is and does, not every IP), what each system is for, support contacts, "who to call" escalation.
- The client site never shows: full IP inventory, MACs, vendor account numbers, credential references, internal notes, warranty/budget commentary.

## The client website — on simple-webs

Decided: self-hosted on **simple-webs** (Traefik v3 + one `nginx:alpine` container per site, label-routed, Let's Encrypt HTTP-01, restart-free git-webhook deploys).

**Per-client isolation is structural — it's already how simple-webs works.** Each client gets its own site:

```
sites/
  cah/html/     -> container cah      -> Host(`cah.clients.propellerheads.tld`)
  wsc/html/     -> container wsc      -> Host(`wsc.clients.propellerheads.tld`)
```

A viewer of `cah.` literally cannot reach `wsc.`'s container or files. No path-based leakage to reason about.

**Static generation:** `env-build.js --target client <code>` renders the redacted projection to a small static site into `sites/<code>/html`. Generator choice (all output plain static files, so any is simple-webs-compatible):

- **Eleventy (11ty)** — recommended. Point it at `dist/<code>.client.json` as a data file, a handful of Nunjucks templates, done. Lightweight, no framework runtime.
- **MkDocs Material** — if you want polished docs-style navigation with near-zero template work; a macros plugin reads the JSON.
- **Plain template script inside `env-build.js`** — for a one-page "here's your environment" summary, skip the generator entirely and emit one `index.html`.

**Auth — add a Traefik forward-auth middleware** (simple-webs ships no auth; this is the one addition it needs):

- **Recommended: Authelia** (or `oauth2-proxy`) as one more label-routed container. Define one access rule per client subdomain mapping to that client's allowed emails/group. Self-contained, no third-party dependency, matches the "everything is a labeled container" model. Wire it as `forwardAuth` middleware on each client router.
- **MVP: Traefik `basicAuth` middleware per router**, one htpasswd entry set per client, credentials stored in that client's 1Password vault and shared with their contact. Fine for a handful of clients; migrate to Authelia when it gets tedious.
- **Note on Cloudflare:** if you proxy these hosts through Cloudflare, its proxy breaks Let's Encrypt **HTTP-01** (this is in simple-webs' own troubleshooting table). Switch Traefik to the **DNS-01** challenge with the Cloudflare provider if you want CF in front (and could then use Cloudflare Access instead of Authelia). Staying off the CF proxy keeps HTTP-01 working and Authelia is the natural fit.

**Deploy:** `env-build.js` writes into a per-client content repo (`client-site-cah`), push to `main`, the simple-webs webhook service runs `git pull` in `sites/cah/html` — live immediately, no restart. (The webhook service is spec-only in simple-webs today per its WEBHOOK.md; implementing that small Flask receiver is a prerequisite, or deploy via a plain `git pull` cron / SSH push in the meantime.)

## The build script (`Scripts/env-build.js`)

Standalone Node CLI (unlike `Scripts/sr-quickadd.js`, which is a QuickAdd script that runs inside Obsidian) — run it from a terminal, CI, or the collector-ingest side. Needs `cd Scripts && npm install` (js-yaml, ajv, ajv-formats). Responsibilities:

1. **Validate** every `environments/*/environment.yaml` against `environment.schema.json`, plus referential integrity (every `depends_on` / `requires` / `supports` ID resolves).
2. **Merge collector state** — overlay `environments/<code>/*.observed.yaml` onto the declared file per the merge rules below, producing the working model.
3. **Emit JSON** — `dist/<code>.json` (full, internal) and `dist/<code>.client.json` (redacted).
4. **Drift report** — diff declared vs. observed, write `drift/<code>-<date>.md`. "prn-reception is declared static .241 but currently answering on .118" is the alert that pre-empts a ticket.
5. **Refresh the Obsidian summary** — regenerate a fenced block (between `<!-- env:begin -->` / `<!-- env:end -->` markers) inside `<Client> - Network and Infrastructure.md` with the current inventory table, so the human note never goes stale.
6. **`--target client <code>`** — render the redacted static site into the client-site content repo.

Wire it to an npm script and a QuickAdd/Templater command to run from inside Obsidian; run the drift step on a schedule on the collector-ingest side.

### Merge / precedence rules

| Field class | Examples | Authority |
|---|---|---|
| Identity + intent | `id`, `roles`, `criticality`, `queue_name`, `internal_only`, `depends_on`, `notes` | **Hand-authored wins.** Collector never overwrites. |
| Observed state | `ip.address`, `mac`, `firmware`, `os` build, switch port, open ports, `last_seen` | **Collector wins.** Hand-authored value (if any) is treated as "expected" and a mismatch is drift. |
| Existence | device seen on the wire but no matching `id` | **Surfaced as drift** ("unmanaged device"), never silently added. |

## Collector tooling

Decided model: **an on-LAN collector node per client** (no RMM). A small always-on box — mini-PC / NUC, or a VM/container on the repurposed CAH server — running Debian + Docker. It runs scheduled collection, assembles an `observed-state.yaml` in the same schema shape as `environment.yaml`, and ships it back to you (git push to a private `client-<code>-observed` repo, or HTTPS POST to an endpoint on your infra). `env-build.js` ingests it.

### Data sources, in priority order

**1. UniFi Network controller API** — richest single source, near-zero effort, covers most of the fleet since networking is mostly Ubiquiti.
   - Per client on the wire: MAC, IP, hostname, the switch+port or AP it's attached to, wired/wireless, DHCP vs fixed-IP, OUI/manufacturer, first-seen / last-seen, uptime.
   - Gateway + WAN: uplink status, ISP, public IP, throughput → feeds `circuits`.
   - Newer controllers: local API key, `GET /proxy/network/api/s/<site>/stat/sta`. Self-hosted/older: `POST /api/login` → `/api/s/<site>/stat/sta` and `/api/s/<site>/rest/user` (fixed-IP config).
   - If they run **UniFi Talk**, its endpoints enumerate VoIP phones; **UniFi Protect** has its own API for cameras.
   - Poll every 15–30 min.

**2. Active LAN scan from the collector node** — catches what UniFi can't classify: x-ray consoles, lab analyzers, non-UniFi VoIP, IoT.
   - `nmap -sn` sweep per subnet → liveness + ARP MAC/vendor.
   - `nmap -sV -O --top-ports 200` on live hosts → service/OS fingerprint. This is how you identify an IDEXX analyzer or a DR x-ray box by its HTTP banner / TLS cert CN / open-port signature.
   - mDNS / SSDP / WS-Discovery listen (`avahi-browse`, a short `zeroconf` script) — printers and some medical gear announce themselves.
   - HTTP `<title>` + TLS cert grab on anything with 80/443 — cheap identification.
   - `ndiff` against the previous scan → change detection even before `env-build.js`.
   - Nightly (it's noisier and slower than the UniFi poll).

**3. SNMP sweep** — printers, UniFi switches, UPS, managed lab/network gear.
   - `snmpwalk` standard MIBs: `sysDescr`, `sysName`, `sysLocation`, `sysUpTime`, `ifTable`; **Printer-MIB** for page counts / toner / status; **UPS-MIB** for battery / load / runtime.
   - Community strings / SNMPv3 creds live in 1Password, pulled at runtime.

**4. Windows endpoint inventory** — no RMM, no AD, so the collector node reaches out to each Windows IP found in steps 1–2:
   - **WinRM** (`pypsrp` from Python, or PowerShell remoting) using a local-admin credential pulled from 1Password at runtime.
   - Fallback where WinRM is off: deploy once a **scheduled task** on each workstation that runs the inventory script daily / at logon and drops `C:\collector\out\<hostname>.json` to an SMB share the collector reads.
   - Collect: OS + build, model + serial (`Win32_BIOS` / `Win32_ComputerSystem`), CPU / RAM / free disk, uptime / last boot, installed software, **print queues + ports + drivers** (feeds the printing runbook directly), local admins, services of interest (SQL, IntraVet), Windows Update status, BitLocker, Defender/AV state, logged-on user.
   - Alternatives to building this layer: **osquery** (scheduled query packs, ship results — consistent SQL across hosts) or **PDQ Inventory** (workgroup-friendly, Windows-only, no AD, buy-not-build).

**5. Manual entries for the un-probeable** — some x-ray consoles and PBXes give up nothing past "port 80 is open," and several are vendor-managed (don't touch). Hand-author them in `environment.yaml` with `source: manual` and `last_verified: <date>`. The collector still logs their network presence, so an IP move / port change / disappearance still shows as drift.

### Off-the-shelf alternatives to the DIY scan+SNMP layers

Worth evaluating before building too much:

- **Open-AudIT (community edition)** — purpose-built "audit every device on a network," Windows + SNMP + SSH, has an API. Closest single tool to this whole requirement; could run *on* the collector node and be the source for layers 2–4.
- **NetBox + NetBox Discovery / Diode** — if you'd rather the CMDB itself be the source of truth than YAML files. Heavier, API-first, excellent data model. A plausible future migration target; the YAML approach doesn't foreclose it.
- **LibreNMS / Zabbix / Observium** — monitoring platforms that auto-discover via SNMP and expose inventory over an API. If you want monitoring anyway, inventory falls out as a side effect.

Reasonable middle path: **DIY the UniFi poller** (it's ~100 lines and the highest-value source), **run Open-AudIT on the collector node** for scan + SNMP + Windows, and let `env-build.js` ingest both.

### Collector node layout

```
/opt/collector/
  collectors/unifi.py      -> raw/unifi.json
  collectors/scan.py       -> raw/scan.json        (or Open-AudIT API pull)
  collectors/snmp.py       -> raw/snmp.json
  collectors/windows.py    -> raw/windows.json     (WinRM) or reads the SMB drop
  assemble.py              -> observed-state.yaml   (schema-shaped merge of raw/*)
  ship.py                  -> git push / HTTPS POST back to base
  systemd timers: unifi.timer (15m), sweep.timer (nightly)
```

1Password on the node: its own scoped **service account** (`OP_SERVICE_ACCOUNT_TOKEN`) or a **1Password Connect** container, with read access to that client's vault only.

### Drift alerts worth generating

- Device on the network, not in `environment.yaml` → onboarding gap or rogue device.
- `assignment: static` device now answering on a different IP.
- Device not seen in N days → offline / decommissioned.
- Print queue or port changed on an endpoint → pre-empts a printing ticket.
- Firmware / OS build changed on a `critical` device.
- New or closed port on a `criticality: critical` or medical/lab device.
- UPS on battery / low runtime, printer toner low (if you want the collector to double as light monitoring).

Output: `drift/<code>-<date>.md`, and optionally auto-create a note in the vault so it shows in the Dashboard.

## How this powers automated troubleshooting

Because inventory + dependency graph are structured:

- **Generate monitoring / ping-sweep configs** from `devices` and `monitoring` — no hand-maintained target lists.
- **Guided triage** — "printing broken" → walk `dependencies` → check `prn-*` DNS records resolve, check printer IPs match declared static, check the (planned) print service is up. This is the `CAH Printing.md` root-cause writeup, encoded once as data instead of re-derived each incident.
- **LLM-assisted first response** — feed `<code>.json` as context to a triage assistant so it reasons over the real environment, not generic advice.
- **Drift detection** — declared state vs. collected actual state, run on a schedule.
- **Onboarding / handoff** — a new tech gets the whole picture in one file instead of spelunking 20 service requests.

## Obsidian-native alternative

Instead of one YAML file per client, make a **note per infrastructure device** (server, firewall, each switch/AP, each printer, each circuit, each line-of-business app — roughly 15–25 notes for CAH) in a `Devices/` folder with `client:: [[Companion Animal Hospital]]` frontmatter. Dataview tables on the company hub note then "just work" exactly like the existing Contacts / Service Requests tables. Keep the ~25 commodity workstations in a single `workstations.yaml` or an inline table.

- **Pro:** fully in the graph, backlinks from tickets/runbooks to specific devices, no build step needed for internal use.
- **Con:** more notes to maintain, and the dependency graph is spread across many frontmatter blocks; a script still has to walk the folder to emit JSON for tooling and the client site.

Reasonable to run this for infrastructure and keep a small YAML for workstations + the dependency graph.

## Recommended path

**YAML source of truth + JSON Schema + `env-build.js`**, with the Obsidian note and client site generated/derived. Start with **CAH** — most of the data already exists, scattered across `Runbooks/CAH Printing.md` and the CAH service requests.

Implementation order:

1. ~~Lock the schema (`environment.schema.json`) and write `Templates/Environment Template.yaml`.~~ **Done 2026-09-02.**
2. ~~Build `environments/CAH/environment.yaml` by hand from the vault (printing runbook, infra note, cloud-migration notes, CAH service requests); wire the existing `Notes/CAH - Network and Infrastructure.md` to point at it.~~ **Done 2026-09-02** (moved from `Companies/CAH/` to `environments/CAH/` on 2026-09-03) — 16 devices, 8 apps, 13 known issues, full dependency graph. Well-evidenced on IntraVet/SQL/server; ~18 items in `unverified:` need an on-site or collector pass.
3. **`Scripts/env-build.js`** — v1 done (validate + ref-check + `dist/<CODE>.json`). Needs `cd Scripts && npm install` and a machine with Node to run. Next: collector merge, `drift/` reports, `--target client`, the `env:begin/end` summary refresh.
4. ~~Decide where `environment.yaml` is tracked.~~ **Done 2026-09-03** — `environments/` is its own nested git repo (see "Where the data is tracked"). Still needs a private remote + push.
5. Stand up the collector node at CAH: UniFi poller first (biggest payoff), then the scan/SNMP/Windows layers (DIY or Open-AudIT). Turn on drift detection.
6. Generate the redacted client site; add the `cah.` site to simple-webs with an Authelia (or basic-auth) middleware.
7. Roll the pattern to Western Sign Company and the next client.

## Decisions locked

- **Source of truth:** one `environment.yaml` per client (hybrid with a `Devices/` folder is still open — see below).
- **Secrets:** 1Password, referenced by `op://` URIs; runtime resolution via `op` CLI + scoped service accounts / Connect.
- **Client site host:** self-hosted on simple-webs — one nginx container per client (isolation is structural), Traefik forward-auth (Authelia recommended, basic-auth as MVP), git-webhook deploy.
- **Workstation detail:** collector-owned, one entry per machine in `<code>/workstations.observed.yaml`; hand-author a workstation in `environment.yaml` only when it has a role or quirk.
- **Collector:** on-LAN collector node per client (no RMM). UniFi API + LAN scan + SNMP + WinRM/scheduled-task Windows inventory. Evaluate Open-AudIT for layers 2–4.

## Still open

- **Private remote for the `environments/` repo** — GitHub private, self-hosted, etc. — then `git push`.
- **Pure YAML, or hybrid with a `Devices/` folder** for infrastructure so tickets/runbooks can backlink to specific devices? Leaning pure YAML to start; add device notes later if the backlink value proves real.
- **DIY the scan/SNMP/Windows collectors vs. run Open-AudIT** on the collector node. Decide after a spike — build the UniFi poller regardless.
- **Ship-back transport:** git push to a private per-client `*-observed` repo vs. HTTPS POST to an ingest endpoint. Git is simpler and gives free history; POST is better if you later want many clients reporting to one service.
- **Implement the simple-webs webhook service** (spec-only today) vs. deploy the client sites via a plain `git pull` cron / SSH push for now.
- **Does the collector double as monitoring?** (UPS-on-battery, toner-low, device-down alerts). Cheap to add once SNMP is in; decide whether that overlaps something you already run.
