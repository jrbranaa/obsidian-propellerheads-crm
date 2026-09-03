---
type: project
client: "[[{{VALUE:client}}]]"
contact: "[[{{VALUE:contact}}]]"
status: active
billing_model: {{VALUE:billing_model}}
quote_usd: {{VALUE:quote_usd}}
budget_hours: {{VALUE:budget_hours}}
opened: {{VALUE:opened}}
closed:
---

## Scope / Deliverables

{{VALUE:scope}}

## Phases

- [ ] 

## Service Requests

```dataview
TABLE WITHOUT ID link(file.link, replace(file.folder, "Service Requests/", "")) AS "Service Request", status, opened, closed
FROM "Service Requests"
WHERE project = this.file.link
SORT opened ASC
```

## Time Rollup

```dataviewjs
const proj = dv.current().file.path;
const srs = dv.pages('"Service Requests"').where(p => p.project && p.project.path === proj);
let logged = 0, billable = 0;
for (const sr of srs) {
	const md = await dv.io.load(sr.file.path);
	if (!md) continue;
	for (const m of md.matchAll(/^\|[^|]*\|\s*([\d.]+)\s*\|\s*(true|false)\s*\|/gim)) {
		const h = parseFloat(m[1]) || 0;
		logged += h;
		if (m[2].toLowerCase() === "true") billable += h;
	}
}
const budget = dv.current().budget_hours;
const parts = [`**Logged:** ${logged.toFixed(2)} h`, `**Billable:** ${billable.toFixed(2)} h`];
if (budget) parts.push(`**Budget:** ${budget} h  ·  **Remaining:** ${(budget - logged).toFixed(2)} h`);
dv.paragraph(parts.join("  ·  "));
```

## Decisions

## Notes
