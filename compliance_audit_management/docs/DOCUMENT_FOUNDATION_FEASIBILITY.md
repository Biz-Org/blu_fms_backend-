# Compliance Document Foundation — Investigation & Recommendation

**Runtime:** this FMS addon targets **Odoo 18**. The third-party notes below describe the external `compliance_document_management` 19.0 app that was reviewed. Those 19.0 pins belong to that product, not to this module's runtime.

**Status:** Investigation complete. No OPL module install, no database change, and no
Option A code migration in this deliverable. Architecture is **license-gated**.

**Sources:** Odoo Apps listing and GitHub `19.0` branch of
[compliance_document_management](https://apps.odoo.com/apps/modules/19.0/compliance_document_management)
([repo](https://github.com/ZetriSofu40/odoo-compliance-document-management));
local `compliance_audit_management`; published OPL-1 text from that repo’s `LICENSE`.

**Manager rule applied:** If an existing Odoo app already provides needed
functionality and is technically/licensing-compatible, prefer extending/reusing it
rather than rebuilding from scratch.

---

## 1. Can the Apps module be the document foundation?

**Yes — for the document register only**, and only if licensing allows use. It is a
mature Odoo 19 document-expiry product and is technically extensible via standard
`_inherit` / view inheritance. It is **not** a foundation for the full Compliance &
Audit scope.

### Apps module provides (stronger than FMS document code today)

| Area | `compliance_document_management` |
| --- | --- |
| Models | `compliance.document`, `compliance.document.type`, `compliance.document.tag`, `compliance.document.reminder.rule`, `compliance.document.reminder.log`; extends `res.partner` |
| Workflow | `workflow_state`: draft → active → renewal → superseded / cancelled |
| Compliance status | Computed `compliance_state`: missing / permanent / valid / due_soon / expired |
| Document types | Policy-driven: validity mode, warning days, required number/issue date/attachment, default responsible, escalation user |
| Reminders | Multi-threshold rules; activities + email; daily cron; idempotent reminder log |
| Renewal / supersede | `previous_document_id` / `renewal_document_ids`; renewal draft; activate supersedes previous |
| Audit history | Immutable reminder logs (unlink blocked); chatter |
| RBAC | Reader (Auditor) → Officer → Administrator |
| UI | Native Odoo: dashboard, documents, expiring/expired/renewals, analysis, reminder history, config |
| Depends | `base`, `mail`, `contacts` |

### FMS document code today (weaker / incomplete)

- Same technical name: **`compliance.document`** (collision — see below)
- Selection-based `document_type` (not a configurable type master)
- Single `renewal_reminder_days`; expiry cron **only flips states** (no activities/emails/alerts)
- In-place renewal + `compliance.document.history`; **no supersede chain**
- FMS location scope and optional `requirement_id` (Apps lacks these)
- OWL Documents screen still a placeholder
- `compliance.alert` has document renewal types but **nothing generates them from documents**

### Hard technical fact: model-name collision

Both modules define `_name = "compliance.document"`. They cannot both own that
model as independent definitions in one database.

- Clean reuse = FMS **depends on** Apps and **inherits** `compliance.document`
  (remove FMS’s own `_name` definition for documents).
- Keeping a separate FMS document model requires renaming → two registers → two
  sources of truth.

### Extension points (Odoo-standard, no source copy)

- `_inherit` on document / type / reminder models
- Extra FMS fields: `requirement_id`, `property_id`, `building_id`, `area_id`, links
- Inherit views/menus; hide Apps root or embed under FMS OWL shell
- Map FMS Manager/Auditor groups onto Apps groups or add ACLs
- Leave OPL module stock; keep FMS delta in the extension addon

### Full Compliance scope (Apps does not cover)

Requirements/checklists/checks, audits/inspections, findings, non-compliance,
corrective actions, verify/close, cross-type calendar, regulatory submissions,
FMS KPI OWL dashboard — remain in `compliance_audit_management` regardless of
document foundation.

```text
Document foundation:  compliance_document_management (OPL) + FMS inherit extensions
FMS domain:           requirement → checklist/check → audit → finding → NC → action
                      + regulatory + alerts/calendar + OWL KPIs
Evidence link:        FMS records → compliance.document (Apps)
```

---

## 2. Licensing (OPL-1)

### Established from published OPL-1 text

If the company has a **valid purchase / written agreement** from the author:

- May **use, execute, and modify** the Software.
- May develop **separate Odoo modules that use it as a library** (depend, import,
  use resources) **without copying** its source/material.
- Those separate modules may use a license of choice **provided it is compatible
  with OPL**.
- **Forbidden** to publish, distribute, sublicense, or sell **copies of the
  Software or modified copies** of the Software.

### Intended patterns (technical reading — not legal advice)

| Intended action | OPL text reading | Company confirmation? |
| --- | --- | --- |
| Purchase + install on company/client Odoo | Allowed if licensed | Purchase + deployment terms |
| FMS addon `depends` + `_inherit` (no source copy) | Contemplated as library use | LGPL-3 + OPL “compatible” |
| Keep FMS addon LGPL-3 | Possibly for the *extension* only | **Legal decision** |
| Modify original module in private deploy | Use/modify if licensed | Redistribution of modified OPL package forbidden |
| Copy Apps source into LGPL FMS repo | **Not allowed** | Do not do |
| Ship/redistribute OPL module or fork | Forbidden for copies / modified copies | Client obtainment path |
| Use without purchase | **Not allowed** | Blocking |

**Legal/licensing decisions the company must close** (this investigation cannot):

1. Valid Odoo Apps purchase (or written license) for `compliance_document_management` v19?
2. Deployment model: single internal DB vs multiple clients — how is OPL licensed per instance?
3. Written confirmation that an **LGPL-3 extension addon** depending on OPL (inherit only, no source copy) is acceptable.
4. Prefer leaving OPL stock with all FMS deltas in a separate addon (recommended technically).

---

## 3. Option comparison

### OPTION A — Apps as document foundation; FMS extends it

| Dimension | Assessment |
| --- | --- |
| Advantages | Follows manager reuse rule; mature reminders/renewal/types/logs; one `compliance.document` truth; vendor upgrades for core doc engine |
| Disadvantages | OPL forever; RBAC mapping (3 Apps roles vs 2 FMS); native Apps UI vs Stitch/OWL; migrate/remove FMS doc ownership |
| Licensing | Requires valid OPL license; extension-without-copy; LGPL-3 extension needs legal OK |
| Effort | Medium |
| Duplication | Low if FMS doc model ownership retired |
| UI | Wrap/hide Apps menus; OWL Documents → Apps model |
| RBAC | Map Manager↔Officer/Admin, Auditor↔Reader |
| Maintenance / upgrades | Track Apps 19.x; keep OPL stock |
| Full scope | Documents via Apps+extend; rest via FMS |

### OPTION B — Depend on Apps but keep separate FMS document models

| Dimension | Assessment |
| --- | --- |
| Advantages | Superficial “reuse” while keeping FMS schema |
| Disadvantages | `_name` collision or rename → **two document systems**; sync bugs |
| Licensing | Same OPL purchase; little benefit if FMS still reimplements documents |
| Effort / duplication | High / high — violates one source of truth |
| Verdict | **Reject** |

### OPTION C — Do not use Apps; FMS standalone

| Dimension | Assessment |
| --- | --- |
| Advantages | No OPL risk; one LGPL codebase; full OWL + 2-role control |
| Disadvantages | Continues building document policies/reminders/supersede that Apps already has — against manager preference **if** license is available |
| Licensing | Clean LGPL-3 |
| Effort | Ongoing (FMS document reminders incomplete today) |
| When correct | License/deploy terms block A |

---

## 4. Existing FMS code — keep / migrate / retire (under Option A)

| FMS piece | Overlap | Disposition under A |
| --- | --- | --- |
| `compliance.document` | Direct collision | Inherit Apps; remove FMS `_name` ownership; migrate or drop early data |
| `compliance.document.history` | Partial | Retire or map to Apps renewal/chatter; not parallel truth |
| Expiry cron / state machine | Overlaps Apps | Remove FMS doc expiry cron; use Apps |
| `renewal_reminder_days` | Weaker than Apps rules | Drop; use type reminder rules |
| `compliance.alert` document types | Parallel channels | Keep alerts for **non-document** items; don’t dual-send doc reminders |
| Attachments | Both | Prefer Apps `document_file`; extend if multi-file needed |
| `requirement_id`, property/building/area | FMS-only | Add via inherit |
| requirement / checklist / check / audit / finding / NC / action / regulatory / dashboard | None | **Keep in FMS** |
| OWL shell / 2-role RBAC | Orthogonal | Keep; wire Documents UI to Apps model |

Hybrid is clean **only if** documents have a single owner (Apps + inherit) and FMS
owns the audit lifecycle.

---

## 5. Manager rule application

1. Apps provides required **document** functionality and is Odoo-19 extensible →
   prefer reuse when license-compatible.
2. It covers only a portion of full scope → keep audits/NC/CA/reporting in FMS.
3. Do not rebuild type policies / multi-threshold reminders / supersede / reminder
   audit if A is allowed.
4. Do not add OPL merely for optics if license/deploy fails → Option C for cause.
5. One truth: `compliance.document` = Apps (+ FMS inherit). Never parallel registers (B).

---

## 6. Non-document ownership (unchanged)

Remain in `compliance_audit_management`:

- statutory requirements, checklists, checks
- audits / inspections, findings
- non-compliance, corrective actions, verification / closure
- multi-type calendar / alerts (non-document)
- regulatory reporting
- FMS KPI OWL dashboard

Link to Apps documents for evidence where needed.

---

## 7. Final recommendation

### Conditional **OPTION A** (preferred under the manager’s instruction)

Use `compliance_document_management` as the **sole document foundation**; extend it
from FMS; keep non-document Compliance & Audit domain in
`compliance_audit_management`.

- **Do not** choose B.
- Choose **C only if** licensing/deployment blocks A.

### Gates before any Option A implementation

| Gate | If NO | If YES |
| --- | --- | --- |
| Valid OPL-1 license for v19 | Option C; improve FMS document reminders **without copying** Apps source | Proceed to legal check |
| Legal OK for LGPL-3 FMS extension depending on OPL + clear client deployment path | Option C or renegotiate | Execute Option A |

### Company checklist (blocking)

1. Proof of purchase / license for `compliance_document_management` 19.0
2. Allowed deployment model for client FMS instances
3. Counsel sign-off on LGPL-3 extension addon depending on OPL-1
4. Confirm OPL left stock; FMS deltas only in extension addon

### Implementation freeze

Until gates clear: **do not** add `compliance_document_management` to
`depends`, **do not** install it, **do not** copy its source into this repo, and
**do not** remove FMS `compliance.document` ownership.

---

## 8. Investigation constraints (honored)

- No plan-file edits as part of this deliverable’s source of truth (this doc is the
  repo copy).
- No module install.
- No database changes.
- No Option A coding until license gates are confirmed.
