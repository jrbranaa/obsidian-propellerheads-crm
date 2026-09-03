---
customer: "[[{{VALUE:customer}}]]"
contact: "[[{{VALUE:contact}}]]"
project:
status: inbox
opened: {{DATE:YYYY-MM-DD}}
closed:
---

## Description

{{VALUE:description}}

---
## Time Log

| Date | Hours | Billable | Notes |
| --- | --- | --- | --- |

---
## Related Service Requests

```dataview
TABLE WITHOUT ID link(file.link, replace(file.folder, "Service Requests/", "")) AS "Service Request", status, opened, closed
FROM "Service Requests"
WHERE customer = this.customer AND file.name != this.file.name
SORT opened DESC
```
