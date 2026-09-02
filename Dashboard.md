
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
WHERE status = "bill"
SORT closed ASC
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
