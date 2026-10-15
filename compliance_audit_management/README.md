# Compliance & Audit Management

Standalone Odoo 19 addon (FMS module #24).

## Install

```bash
./odoo-bin \
  --addons-path=odoo/addons,addons,/Users/palakboricha/fmss \
  -d <database> \
  -i compliance_audit_management \
  --stop-after-init
```

## Primary roles (exactly two)

Assign under **Settings → Users → Access Rights → Compliance & Audit**:

- **Compliance Manager** — full operational rights (create/update, workflow, configuration)
- **Compliance Auditor** — read-only (evidence, logs, and reports)

XML IDs: `group_compliance_manager`, `group_compliance_auditor`.

## Phase

Phase 2: OWL shell and Compliance Overview dashboard are live. Remaining sidebar
screens are placeholders until later phases.

## Document foundation (architecture)

Investigation and gated recommendation:
[docs/DOCUMENT_FOUNDATION_FEASIBILITY.md](docs/DOCUMENT_FOUNDATION_FEASIBILITY.md).

**Conditional Option A:** reuse Apps Store `compliance_document_management` as the
document register (extend from FMS) once OPL-1 license + legal gates clear.
Until then this addon stays standalone (`mail` only) and must not install, depend
on, or copy that OPL module. Option B (parallel document models) is rejected.
