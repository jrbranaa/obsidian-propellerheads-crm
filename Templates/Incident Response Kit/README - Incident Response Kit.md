# Incident Response Kit — How to Use This

Built from patterns across three real incidents (CAH20260619, CAH20260730, CAH20260806). Each one independently converged on the same shape — this kit just makes that shape reusable instead of rebuilding it from scratch every time.

---

## The Workflow

A typical incident moves through up to five stages. Not every incident needs all five — a quick fix (like the AUTO_CLOSE issue) might only need stages 1, 2, and 4. A multi-day outage (like the July 30 database-full incident) needs all five.

1. **Intake** — `Templates/Service Request Template.md` (existing). Customer, contact, initial description. This is the seed every other document links back to.
2. **Technical Analysis** — `2 - Technical Analysis.md`. Your own working document. Root cause, evidence, timeline, what you did. Written for yourself and for anyone technical (Patterson, a future you). Doesn't need to be pretty, needs to be complete.
3. **Vendor Escalation Email** — `3 - Vendor Escalation Email.md`. *Only if the fix isn't yours to make.* Structured, evidence-heavy, ends in a numbered action list a support tech can't wiggle out of.
4. **Client Update** — `4 - Client Update Email.md` for most incidents, or `5 - Client Summary Report (Major Incidents).md` when it's a multi-day incident, involves real financial/operational impact, or the client will want something they can forward to a business partner or keep on file.
5. **Vendor Call Log** — `6 - Vendor Call Log.md`. Use any time you get on the phone with a vendor. Takes two minutes and pays for itself the moment a vendor tries to tell you they never heard about this before.

Every stage's "open items" should use the same checkbox format (see below) so they roll up automatically — see **Standing Issue Tracker** below for why that matters.

---

## Naming Convention

Keep using what's already working: `{ClientCode}{YYYYMMDD}-{Short Description}` for the Service Request folder (e.g. `CAH20260806-Save_Issues`). Inside it, name files by what they are, not by date — `Analysis.md`, `Client Summary Email.md`, `Patterson Escalation Email.md` — the folder already carries the date.

---

## Open Items — Use Checkboxes, Not Just Tables

Tables read fine but they're dead ends — nothing outside that one document can see them. Write open items as checkboxes with inline Dataview fields instead:

```markdown
- [ ] Clean up orphaned InventoryInternal rows [owner:: Patterson] [priority:: High]
- [ ] Provide sysadmin SQL login [owner:: Patterson] [priority:: High]
```

This costs nothing extra to write, but it means you can build a query that rolls up every open item across every client and every incident in one place — e.g. a dashboard note with:

````markdown
```dataview
TASK
FROM "Service Requests"
WHERE !completed
GROUP BY owner
```
````

That's the difference between noticing on your own that Patterson has been asked for the same SQL query three times, and having it slap you in the face the moment you open the vault. Worth setting up once as a standing dashboard note — happy to build that with you if useful.

---

## The Standing Issue Tracker — the one genuinely new piece

The gap that showed up clearest across these three tickets: the same unresolved vendor request (the `InventoryInternal` cleanup query) was reported June 19, July 30, and again in August — and each time it took re-reading old tickets to notice the pattern. Per-incident docs reset to zero every time a new folder gets created; nothing *persists* the way a real relationship with a flaky vendor needs to.

`7 - Standing Issue Tracker.md` is a template for a note that lives at the **client or vendor level**, not the incident level — it doesn't get closed when the ticket does. Every time you escalate something that vendor doesn't fix, it gets a line here with a running count. A live example has been built for Companion Animal Hospital / Patterson — see `Companies/Companion Animal Hospital - Vendor Issue Tracker.md`. Next time you write a vendor escalation, check this first — "this is the third time we've requested this" is a much stronger sentence than starting from scratch.

---

## System Runbooks — separate from all of the above

Runbooks (`Runbooks/`) are not incident documents — they're standing reference for *how a system works*, independent of any one ticket, and get updated in place over time rather than recreated. Use `Runbooks/Runbook Template.md` when a fix or a procedure is something you (or the client) will need to do again — backup verification, service restarts, that kind of thing. The `backup-runbook.md` from the June incident is a good example of the shape.

---

## Brand Voice Cheat Sheet (client-facing docs only)

Internal docs (Technical Analysis, Vendor Escalation, Call Log) can be as dry and technical as they need to be — the audience is you or a Patterson support engineer, not the client. But anything the client reads should sound like **you**, not like a ticketing system:

- **Plain English over jargon.** If you use a technical term, explain it in the next sentence the way you did with WCF channels ("like an open phone call"). Assume zero technical background, zero condescension.
- **Lead with the answer.** TL;DR first, always. A hospital manager reading this on their phone between appointments should get the whole story in the first paragraph.
- **Own it directly.** "I identified," "I engaged Patterson," "I'll be re-escalating" — first person, active voice, no passive "it was determined that."
- **Be straight about what's not fixed yet.** Don't round up. If Patterson dropped the ball twice, say so plainly — that's the accountability and transparency the brand is built on, and it's also just useful information for the client to have.
- **Skip the corporate throat-clearing.** No "per my last email," no "please find attached," no filler. Say the thing.
- **Sign off the same way every time** — name, direct email, direct phone. No "the PropellerHeads team." There's one person answering, and that's the point.

---

## Files in This Kit

| File | Use for |
|---|---|
| `2 - Technical Analysis.md` | Your own root-cause investigation, every incident |
| `3 - Vendor Escalation Email.md` | Any time a vendor (Patterson, ISP, etc.) needs to act |
| `4 - Client Update Email.md` | Standard client-facing wrap-up |
| `5 - Client Summary Report (Major Incidents).md` | Multi-day or high-impact incidents |
| `6 - Vendor Call Log.md` | Any live call with a vendor |
| `7 - Standing Issue Tracker.md` | One per client or vendor relationship — persists across incidents |
