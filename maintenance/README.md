# Bizlem Plant Maintenance System (Odoo 18)

All plant maintenance code lives in this **single Odoo module** (`maintenance`).

## Module structure

```
maintenance/
├── README.md                 ← you are here
├── __manifest__.py           ← module config & version
├── models/                   ← Python business logic
├── views/                    ← screens, menus, forms
├── wizard/                   ← Excel import popups
├── controllers/              ← RUL & TOBM web routes
├── data/                     ← demo data & menu setup
├── security/                 ← roles & access rights
├── static/                   ← dashboards (JS, SCSS)
├── tests/                    ← automated tests
├── docs/                     ← demo script & commands
└── scripts/                  ← upgrade & test helpers
```

## Features

- Equipment master + **Excel import**
- Work orders (PM / CM) with **8-step workflow**
- Spares, manpower, planning, execution, Go/No-Go
- RCA dashboards (Fishbone, Why-Why, CAPA, Agile, Plant)
- RUL & TOBM dashboard
- Maintenance analytics
- Plant roles: **Operator**, **Supervisor**, **Manager**

## User roles

Assign in **Settings → Users → Maintenance**:

| Role | Access |
|------|--------|
| Plant Maintenance Operator | Own work orders, read equipment |
| Plant Maintenance Supervisor | + Excel import, create equipment |
| Plant Maintenance Manager | Full admin access |

## Install / upgrade

From your Odoo project root:

```bat
addons\maintenance\scripts\upgrade_maintenance.bat
```

Or manually:

```bash
python odoo-bin -c odoo.conf -u maintenance -d YOUR_DB --stop-after-init
```

## Run tests

```bat
addons\maintenance\scripts\run_tests.bat
```

## Documentation

- [Demo script](docs/PLANT_MAINTENANCE_DEMO_SCRIPT.md)
- [Commands](docs/COMMANDS.md)

## Requirements

- Odoo 18 with `mail`, `stock`, `bus`
- `openpyxl` for Excel import

## License

LGPL-3
