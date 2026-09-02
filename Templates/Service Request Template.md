---
customer: "[[{{VALUE:customer}}]]"
contact: "[[{{VALUE:contact}}]]"
status: inbox
opened: {{DATE:YYYY-MM-DD}}
closed:
---

## Description

{{VALUE:description}}

---
## Time Log



---
## Related Service Requests

```dataview
TABLE WITHOUT ID link(file.link, replace(file.folder, "Service Requests/", "")) AS "Service Request", status, opened, closed
FROM "Service Requests"
WHERE customer = this.customer AND file.name != this.file.name
SORT opened DESC
```
