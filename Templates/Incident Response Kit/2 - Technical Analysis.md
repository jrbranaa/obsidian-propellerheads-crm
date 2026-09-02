# {{Incident}} — Technical Analysis

**Client:**
**Contact:**
**Date of Analysis:**
**Severity:** <!-- Low / Medium / High / Critical — e.g. "cosmetic" vs "clinic-wide outage" -->
**System(s) affected:**
**Status:** <!-- Investigating / Root cause identified / Fix applied / Awaiting vendor / Resolved -->

---

## Reported Issue

What the client actually said, in their words where possible. Include how they noticed it, what they tried, whether anyone else reproduced it.

---

## Timeline

| Date/Time | Event |
|---|---|
| | |

---

## Investigation & Findings

Number each distinct finding. For each one: what you found, the evidence, and why it matters. Don't skip the "why it matters" — a log line means nothing to future-you without the interpretation attached.

### Finding 1 —

**Evidence:**

**Significance:**

### Finding 2 —

**Evidence:**

**Significance:**

---

## Root Cause vs. Contributing Factors

Be explicit about which is which — it's easy to fix a contributing factor, declare victory, and have the real problem resurface. (See: Patterson freeing disk space in July and believing that also fixed the orphaned-records FK issue. It didn't — those were two separate problems that happened to be discovered together.)

**Root cause:**

**Contributing factors:**

**Ruled out:** <!-- What you checked and eliminated — worth recording so you don't re-check it next time -->

---

## Actions Taken

1.

---

## Outcome

Resolved / partially resolved / mitigated / still open. If retested by the client, say so and how.

---

## Open Items

<!-- Use checkboxes + inline fields so these roll up in a vault-wide Dataview query. See kit README. -->

- [ ] [owner:: ] [priority:: ]

---

## Related

-
