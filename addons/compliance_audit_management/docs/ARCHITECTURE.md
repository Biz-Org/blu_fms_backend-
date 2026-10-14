# Compliance & Audit Management — Architecture

Standalone Odoo 19 addon (`compliance_audit_management`) for FMS module #24.

## Purpose

Statutory compliance requirements and checklists, compliance documents and
expiry tracking, audits and inspections, findings, non-compliance and
corrective actions, regulatory reporting, and compliance alerts/KPIs.

## Document foundation decision (gated)

Full investigation:
[`DOCUMENT_FOUNDATION_FEASIBILITY.md`](DOCUMENT_FOUNDATION_FEASIBILITY.md).

**Recommendation:** Conditional **Option A** — use Odoo Apps
`compliance_document_management` (OPL-1) as the **sole** document register and
extend it from FMS; keep non-document Compliance & Audit domain in this addon.

| Gate | Required before Option A code |
| --- | --- |
| Valid OPL-1 license for Apps module v19 | Blocking |
| Legal OK for LGPL-3 FMS extension depending on OPL (no source copy) + client deploy path | Blocking |

Until gates clear: this addon remains **standalone** (`depends`: `mail` only),
continues to own `compliance.document`, and must **not** install, depend on, or
copy source from `compliance_document_management`.

**Rejected:** Option B (Apps + separate FMS document models) — model-name
collision / two sources of truth.

**Fallback:** Option C (remain standalone) if licensing/deployment blocks A.

Both this addon and the Apps module currently define `_name = "compliance.document"`.
They cannot coexist as independent owners; Option A requires FMS to **inherit**
the Apps model and drop local ownership of that `_name`.

## Dependencies (current)

- `mail` only
- Does **not** currently depend on `compliance_document_management`,
  `community_communication`, `fire_safety_management`, `portal`, `hr`, or
  third-party QMS/ISO suites

## Model ownership (current / until Option A)

All domain models use the `compliance.*` namespace and are owned by this addon.

| Model | Role |
| --- | --- |
| `compliance.property` / `building` / `area` | INTEGRATION PLACEHOLDER location hierarchy |
| `compliance.requirement` | Statutory/regulatory requirement catalog |
| `compliance.checklist.template` / `item` | Reusable checklists |
| `compliance.check` / `line` | Scheduled/executed compliance activities |
| `compliance.audit` / `line` | Audits and inspections (`kind`) |
| `compliance.finding` | Observations that can convert to NC |
| `compliance.non.compliance` | Formal non-compliance issues |
| `compliance.action` | Corrective actions with verify/close |
| `compliance.document` / `history` | Licenses/certificates/permits + renewal history (**superseded under Option A**) |
| `compliance.regulatory.report` | Regulatory submissions |
| `compliance.alert` | Reminders / escalation alerts (non-document calendar under Option A) |
| `compliance.dashboard` | Abstract KPI aggregator for OWL UI |

Under Option A, document register ownership moves to Apps; FMS adds
`requirement_id` / property scope via `_inherit` and links evidence into
checks/audits/findings.

## RBAC groups (exactly two primary roles)

Stable XML IDs (FUTURE central RBAC #27 will map users → these groups):

| Role | XML ID | Access |
| --- | --- | --- |
| Compliance Manager | `group_compliance_manager` | Full ops + configuration + workflow actions |
| Compliance Auditor | `group_compliance_auditor` | Read-only (evidence, logs, reports) |

No other Compliance groups exist in v1. Python methods enforce verify/close and
restricted transitions; native buttons are not the security boundary.

Under Option A, map these onto Apps Reader / Officer / Administrator (or add
ACLs) so users are not managed in two conflicting trees.

## Data scope

Transactional records include: `company_id`, `property_id`, `building_id`,
`area_id`, `site_id`, `department_id`, `assigned_user_id`.

- Record rules enforce company boundaries
- Property-level row scope is FUTURE until Property Management (#2) and RBAC (#27)

## Canonical workflow

Compliance → Evidence → Review → Finding → Corrective Action → Close

Expanded:

Requirement → Checklist / Audit / Inspection → Finding → Non-Compliance →
Corrective Action → Verification → Closure → Reporting

## Phase status

Phase 1: installable foundation (models, security, native views/menus).
Phase 2: OWL shell + Dashboard (UI PDF Overview). Other sidebar screens are
placeholders until later phases.
Document subsystem: pending company license/legal gates before Option A
migration; until then improve only within this LGPL addon without copying OPL
source.
