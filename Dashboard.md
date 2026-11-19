
## Open Service Requests

Status is editable directly in the table below — changing it writes straight to that SR's frontmatter. Once you set it to `completed` or `abandoned`, the row will drop off this list on next refresh.

```dataviewjs
const pages = dv.pages('"Service Requests"')
	.where(p => p.status && p.status !== "completed" && p.status !== "abandoned")
	.array()
	.sort((a, b) => {
		if (a.status !== b.status) return a.status < b.status ? -1 : 1;
		const ao = a.opened ?? "";
		const bo = b.opened ?? "";
		return ao < bo ? -1 : ao > bo ? 1 : 0;
	});

dv.table(
	["Service Request", "Customer", "Contact", "Status", "Opened"],
	pages.map(p => {
		const label = p.file.folder.replace("Service Requests/", "");
		const srLink = `[[${p.file.path}|${label}]]`;
		const statusInput = `\`INPUT[inlineSelect(option(inbox), option(next), option(in-progress), option(blocked), option(bill), option(completed), option(abandoned)):${p.file.path}#status]\``;
		return [srLink, p.customer ?? "", p.contact ?? "", statusInput, p.opened ?? ""];
	})
);
```

## Ready to Bill

```dataview
TABLE WITHOUT ID link(file.link, replace(file.folder, "Service Requests/", "")) AS "Service Request", customer, contact, opened, closed
FROM "Service Requests"
WHERE status = "bill" AND origin != "proactive"
SORT closed ASC
```

## Proactive Improvements (value add, no charge)

Work you started on your own (`origin: proactive`), by client and newest first. Use this list when you write the "Proactive improvements (no charge)" section of a client's Summary of Services. Describe what was done and why it helps. Never include hours or a dollar value. Close these as `completed`, never `bill`.

```dataviewjs
const all = dv.pages('"Service Requests"').where(p => p.status);
const norm = v => String(Array.isArray(v) ? v[0] : (v ?? "")).trim().toLowerCase();
const rows = all.where(p => norm(p.origin) === "proactive")
	.sort(p => p.opened ?? "", "desc")
	.sort(p => String(p.customer ?? ""), "asc");
if (rows.length) {
	dv.table(["Improvement", "Customer", "Status", "Project", "Opened", "Closed"],
		rows.map(p => [
			`[[${p.file.path}|${p.file.folder.replace("Service Requests/", "")}]]`,
			p.customer ?? "", p.status ?? "", p.project ?? "", p.opened ?? "", p.closed ?? "",
		]));
} else {
	// Diagnostic: shows what Dataview actually sees for `origin`
	const counts = {};
	for (const p of all) {
		const k = `${typeof p.origin}:${JSON.stringify(p.origin ?? null)}`;
		counts[k] = (counts[k] ?? 0) + 1;
	}
	const newest = all.sort(p => p.opened ?? "", "desc").limit(3).map(p => p.file.folder).array();
	dv.paragraph(`No proactive SRs found. SR notes indexed: ${all.length}. origin values: ${JSON.stringify(counts)}. Newest: ${newest.join(" · ")}`);
}
```

## Stale Inbox (opened 30+ days ago, never triaged)

```dataview
TABLE WITHOUT ID link(file.link, replace(file.folder, "Service Requests/", "")) AS "Service Request", customer, opened
FROM "Service Requests"
WHERE status = "inbox" AND opened <= date(today) - dur(30 days)
SORT opened ASC
```

## Open Follow-Up Items Across All Tickets

Owner-tagged checkboxes anywhere under Service Requests — e.g. `- [ ] Clean up X [owner:: Patterson] [priority:: High]`.

```dataview
TASK
FROM "Service Requests"
WHERE !completed
GROUP BY owner
```

## Recently Opened (last 90 days)

```dataview
TABLE WITHOUT ID link(file.link, replace(file.folder, "Service Requests/", "")) AS "Service Request", customer, status, opened
FROM "Service Requests"
WHERE opened >= date(today) - dur(90 days)
SORT opened DESC
```
