# blu_fms_backend

Odoo 18 custom addons for the Blu Facility Management System, with Docker deployment helpers.

Run the official Odoo 18 server with `addons_path` including this repository root (see [config/odoo.conf.example](config/odoo.conf.example)). Each subdirectory below is one installable Odoo module.

## Repository layout (15 modules at root)

All custom addons live **directly at the repository root** (no nested `addons/` directory):

| Module | Summary |
|--------|---------|
| `apartment_management` | Apartments (existing) |
| `esg_management` | ESG (existing) |
| `gate_management` | Gate (existing) |
| `owner_tenant_management` | Owners & tenants (existing) |
| `property_management` | Property portfolio (existing) |
| `resident_management` | Residents (existing) |
| `workforce_management` | Workforce (existing) |
| `ai_copilot` | AI assistant (OWL + HTTP providers) |
| `community_communication` | Community portal & backend app |
| `compliance_audit_management` | Compliance & audit |
| `fire_safety_community` | Fire safety ↔ community bridge |
| `fire_safety_management` | Fire & safety |
| `integration_iot_management` | IoT integration |
| `mobile_application` | Mobile JSON API + OWL shell |
| `reports_analytics` | Reports & analytics |

Supporting files:

```
blu_fms_backend/
├── <module_name>/          # 15 Odoo addons (see table)
├── config/odoo.conf.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── docs/
```

**Local fmss mapping:** `~/fmss/<module_name>/` corresponds to `~/blu_fms_backend/<module_name>/` for the eight FMS suite modules listed above.

## Module dependencies (eight-module suite)

| Technical name | `depends` (Odoo) | Notes |
|----------------|------------------|--------|
| `community_communication` | `mail`, `portal` | |
| `compliance_audit_management` | `mail` | |
| `fire_safety_management` | `mail` | |
| `fire_safety_community` | `fire_safety_management`, `community_communication` | No UI |
| `integration_iot_management` | `mail` | |
| `reports_analytics` | `mail` | |
| `ai_copilot` | `web` | API keys in Odoo settings |
| `mobile_application` | `mail`, `web` | `/mobile/api/*` routes |

Example install set:

```text
community_communication,fire_safety_management,fire_safety_community,compliance_audit_management,integration_iot_management,reports_analytics,ai_copilot,mobile_application
```

The seven property/resident modules are independent unless you add manifest dependencies later.

## Python dependencies

See [requirements.txt](requirements.txt). Custom code uses Odoo, **python-dateutil**, and the standard library. Install into your Odoo venv:

```bash
/path/to/odoo/.venv/bin/pip install -r requirements.txt
```

## Local development (without Docker)

1. PostgreSQL running.
2. Odoo 18 source + venv.
3. Point addons path at **this repo root**:

```bash
--addons-path="/path/to/odoo/odoo/addons,/path/to/odoo/addons,/path/to/blu_fms_backend"
```

Example install:

```bash
.venv/bin/python odoo-bin \
  --addons-path="..." \
  -d fms_dev \
  -i community_communication,fire_safety_management,fire_safety_community,compliance_audit_management \
  --stop-after-init
```

## Docker

```bash
cp .env.example .env   # edit passwords
docker compose build
docker compose up -d
```

- **Image:** `odoo:18.0` with repo copied to `/mnt/extra-addons` and [config/odoo.conf.example](config/odoo.conf.example) as `/etc/odoo/odoo.conf`.
- **addons_path:** standard Odoo addons + `/mnt/extra-addons` (all 15 root modules).
- **Compose:** PostgreSQL 16 + Odoo on port `8069`. Optional bind mount `.:/mnt/extra-addons:ro` for live code during development; remove that volume for production image-only runs.

Open http://localhost:8069, create a database, and install apps from **Apps** (developer mode).

## Databases

An Odoo 19 database cannot be opened by Odoo 18. Create a new PostgreSQL database and install the modules. Do not point this Odoo 18 runtime at the only copy of an existing database.

## Security

- Do not commit `.env`, API keys, or production `admin_passwd`.
- Assign module security groups after install (Community, Fire & Safety, Compliance, IoT, Analytics, Mobile, Copilot, etc.).

## Tests

Odoo tests live under each module’s `tests/`. Example:

```bash
.venv/bin/python odoo-bin --addons-path="..." -d fms_test --test-enable --stop-after-init -i reports_analytics
```

## Related repositories

- UI mirror: `Biz-Org/blu_fms_ui` (frontend sources under `ui/`).
