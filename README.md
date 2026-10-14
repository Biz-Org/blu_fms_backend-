# blu_fms_backend

Odoo 19 backend for the Blu Facility Management System: custom addons, Docker deployment, and configuration.

This repository is **not** a standalone Python application. Run the official Odoo 19 server with `addons_path` pointing at the custom modules here (see [config/odoo.conf.example](config/odoo.conf.example)).

## Repository layout

```
blu_fms_backend/
├── addons/                          # FMS application suite (from fmss)
│   ├── ai_copilot/
│   ├── community_communication/
│   ├── compliance_audit_management/
│   ├── fire_safety_community/
│   ├── fire_safety_management/
│   ├── integration_iot_management/
│   ├── mobile_application/
│   └── reports_analytics/
├── apartment_management/            # Additional FMS modules (repo root)
├── esg_management/
├── gate_management/
├── owner_tenant_management/
├── property_management/
├── resident_management/
├── workforce_management/
├── config/odoo.conf.example
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

**Path mapping from local development:** if your Odoo checkout uses `/path/to/fmss` as addons path, modules under `addons/<name>/` here correspond to `fmss/<name>/`.

## FMS modules (`addons/`)

| Technical name | Depends on (Odoo modules) | Notes |
|----------------|---------------------------|--------|
| `community_communication` | `mail`, `portal` | Portal templates + OWL backend app |
| `compliance_audit_management` | `mail` | |
| `fire_safety_management` | `mail` | |
| `fire_safety_community` | `fire_safety_management`, `community_communication` | Bridge only; no UI |
| `integration_iot_management` | `mail` | |
| `reports_analytics` | `mail` | |
| `ai_copilot` | `web` | LLM via HTTP (stdlib); API keys in Odoo config |
| `mobile_application` | `mail`, `web` | JSON routes under `/mobile/api/*` |

Suggested install set for the core FMS apps:

```text
community_communication,fire_safety_management,fire_safety_community,compliance_audit_management,integration_iot_management,reports_analytics,ai_copilot,mobile_application
```

Install order is handled by Odoo from manifest `depends`; `fire_safety_community` must be installed after its two dependencies.

## Python dependencies

Custom addon Python code uses **Odoo**, **python-dateutil** (`relativedelta`), and the **standard library** (including `urllib` in AI Copilot). No extra pip packages are required beyond [requirements.txt](requirements.txt) for typical Odoo 19 environments.

Install into your Odoo virtualenv:

```bash
/path/to/odoo/.venv/bin/pip install -r requirements.txt
```

Do not `pip install odoo` into the same environment unless you maintain Odoo from source intentionally.

## Local development (without Docker)

1. PostgreSQL running (`pg_isready`).
2. Odoo 19 source with venv (see your `fmss/run_setup` in the source project).
3. Add both addon roots:

```bash
--addons-path="/path/to/odoo/odoo/addons,/path/to/odoo/addons,/path/to/blu_fms_backend,/path/to/blu_fms_backend/addons"
```

Example first-time install:

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

Open http://localhost:8069 and create a database. Install apps from **Apps** (developer mode) or use `-i` on the CLI.

The image extends `odoo:19.0`, copies all custom modules to `/mnt/extra-addons`, and uses `config/odoo.conf.example` as `/etc/odoo/odoo.conf`. Compose bind-mounts addon directories for development; remove volume mounts for production image-only deploys.

## Security

- Never commit `.env`, API keys, or `admin_passwd` production values.
- Assign FMS security groups per app (Community, Fire & Safety, Compliance, IoT, Analytics, Mobile, Copilot) after install.

## Tests

Each addon includes `tests/` tagged Odoo tests. Run from your Odoo source:

```bash
.venv/bin/python odoo-bin --addons-path="..." -d fms_test --test-enable --stop-after-init -i reports_analytics
```

## Related repositories

- UI assets mirror: `Biz-Org/blu_fms_ui` (OWL/SCSS sources under `ui/`).
