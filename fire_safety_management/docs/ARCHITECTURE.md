# Fire & Safety Management — Phase 1 Architecture

Standalone Odoo 18 addon (`fire_safety_management`) for FMS module #23.

## Purpose

Digital fire inspections, safety audits, incidents, mock drills, fire equipment,
emergency response, procedures, contacts, and compliance aggregation.

## Dependencies

- `mail` only
- Does **not** depend on `community_communication`, `portal`, `hr`, `maintenance`, or `stock`

## Model ownership

All domain models use the `fire.safety.*` namespace and are owned by this addon.

| Model | Role |
| --- | --- |
| `fire.safety.property` / `building` / `area` | INTEGRATION PLACEHOLDER location hierarchy |
| `fire.safety.inspection` | Single inspection model (`fire_inspection` / `safety_audit`) |
| `fire.safety.checklist.template` / `item` | Configurable checklist catalog |
| `fire.safety.inspection.line` | Checklist execution (Pass / Fail / N/A) |
| `fire.safety.finding` | Findings from inspections or incidents |
| `fire.safety.action` | Fire & Safety corrective actions |
| `fire.safety.incident` | Incident reports |
| `fire.safety.drill` | Mock drills |
| `fire.safety.equipment` | Fire equipment (not generic Asset Management) |
| `fire.safety.emergency` | Emergency activation/closure |
| `fire.safety.procedure` / `contact` | Catalogs |
| `fire.safety.dashboard` | Abstract aggregation for dashboards/reports |

## RBAC groups

Stable XML IDs (FUTURE central RBAC #27 will map users → these groups):

- `group_fire_safety_manager` — Safety Manager
- `group_fire_safety_security` — Security
- `group_fire_safety_guard` — Security Guard
- `group_fire_safety_facility` — Facility Manager
- `group_fire_safety_auditor` — Auditor
- `group_fire_safety_executive` — Management / CXO

FMS Admin uses `base.group_system` plus configuration ACLs. There is no Fire & Safety business role named Officer, Manager, or Administrator.

Groups are independently assignable. They share one application category and do not imply each other, so Odoo 18 shows them as checkboxes rather than a mutually exclusive ladder.

Python methods enforce verification, closure, emergency activation, and other restricted transitions. OWL/XML buttons are not the security boundary.

## Data scope

Transactional records include: `company_id`, `property_id`, `building_id`, `area_id`, `site_id`, `department_id`, `assigned_user_id`.

- `company_id` / assigned users use `res.company` / `res.users`
- `site_id` currently **aliases** `property_id`
- `department_id` is an optional Char placeholder for future Workforce/Admin
- Record rules enforce company boundaries
- Security Guard incidents are limited to `reported_by_id = user`
- Property-level row scope for Facility Manager is **FUTURE / NOT IMPLEMENTED** until Property Management (#2) and RBAC (#27) provide user↔property assignment

## Placeholder location strategy

`Property → Building / Tower → Floor / Zone / Area`

These models are **INTEGRATION PLACEHOLDERS**. They are not a Property Management system. They must be retargeted to FMS Property Management module #2. They do not reuse `community.communication.building`.

## Workflow states

Inspection: Scheduled → In Progress → Pending → Completed → Closed. Overdue is computed, not stored.

Canonical chain: Inspection → Finding → Corrective Action → Verification → Closure.

Corrective action: Open → Awaiting Verification (`done`) → Closed.

Incident: Open → Investigating → Resolved. There is no Pending Maintenance state.

Drill stored states: Scheduled / Rescheduled / Completed / Cancelled. UI may label Scheduled as Upcoming.

Emergency: Active → Closed. Maximum **one active emergency per company**. There is no stored `none` row; absence of an active record is “none”.

Equipment `condition` is manual (operational / under maintenance / faulty / replaced). `state` overlays computed inspection-due / service-due / expired.

## Mobile integration contract

No Fire & Safety mobile app is shipped here. Future Operations / Staff Mobile App (#26) should wrap these methods:

- `fire.safety.inspection.get_assigned_inspections()`
- `fire.safety.inspection.action_start_inspection()`
- `fire.safety.inspection.action_complete_inspection()`
- `fire.safety.inspection.action_update_checklist_line()`
- `fire.safety.incident.action_report_incident(vals)`
- `fire.safety.emergency.action_activate_emergency(vals)`

Evidence uses `ir.attachment`.

## Compliance calculation

Weighted: inspections (40%) + non-expired equipment (30%) + closed corrective actions (30%).

Target is `ir.config_parameter` `fire_safety_management.compliance_target` (default 95). The 95 figure is a target, not a hard-coded result.

## Future FMS integration points — FUTURE / NOT IMPLEMENTED

| Module | Contract |
| --- | --- |
| Property Management #2 | Retarget `property_id` / `building_id` / `area_id`; introduce canonical Site |
| Maintenance #11 | `maintenance_ref` / work orders — not implemented; equipment history stays in this addon |
| Reports #25 | Consume dashboard/report datasets and PDF export from this addon |
| Operations Mobile #26 | Wrap the Python methods above |
| RBAC #27 | Map users → the stable groups above, plus property scopes |
| Compliance & Audit #24 | Consume findings/actions; do not merge ownership |
| Command Center #33 | `command_center_ref` / response team — field reserved, no CC/CCTV/IoT/PBX |

## Deliberately out of scope (Phase 1 and product boundary)

- Other FMS modules
- `community_communication` changes or dependency
- Parallel REST backend, SPA, second database
- Fire & Safety-specific mobile application
- Central RBAC service
- Property Management / Maintenance work orders / Command Center / CCTV / IoT
- Generic Asset Management
- Polished Stitch OWL screens, p12 PDF export, and reminder UX (Phase 2+)
