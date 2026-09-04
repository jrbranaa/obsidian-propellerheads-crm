---
phone: "{{VALUE:phone}}"
code: {{VALUE:code}}
---

---
## Contacts

```dataview
LIST
FROM "People"
WHERE company = this.file.link
```

---
## Service Requests

```dataview
TABLE WITHOUT ID link(file.link, replace(file.folder, "Service Requests/", "")) AS "Service Request", status, opened, closed
FROM "Service Requests"
WHERE customer = this.file.link
SORT opened DESC
```

---
## Open Vendor Issues

<!-- Only fill this in if there's a recurring, unresolved issue with a vendor on this client's behalf worth tracking across multiple incidents. Link a Standing Issue Tracker note (see Templates/Incident Response Kit/7 - Standing Issue Tracker.md) rather than writing status here directly — e.g. "See [[{Client} - Vendor Issue Tracker]]." Most companies won't need this section filled in. -->

---
## Projects

```dataview
TABLE WITHOUT ID file.link AS "Project", contact, status, billing_model, opened, closed
FROM "Projects"
WHERE client = this.file.link
SORT opened DESC
```

---
## Notes

<!-- Anything durable about this client that isn't tied to one ticket — e.g. how to identify their account when calling a vendor, access quirks, billing notes. -->
