# Plant Maintenance — Commands

All helper scripts are inside this module: `addons/maintenance/scripts/`

## Start Odoo (recommended — prevents broken CSS)

Duplicate Odoo processes on port 8069 break page styling. Use:

```bat
addons\maintenance\scripts\start_odoo_clean.bat
```

This stops any old Odoo on 8069, checks PostgreSQL, then starts **one** server.

## Upgrade module (after code changes)

```bat
addons\maintenance\scripts\upgrade_maintenance.bat
```

## Run automated tests

```bat
addons\maintenance\scripts\run_tests.bat
```

## Manual upgrade (from Odoo project root)

```bat
venv\Scripts\activate
python odoo-bin -c odoo.conf -u maintenance -d odoo_dev --stop-after-init
```

## Browser

- URL: `http://localhost:8069/web?db=odoo_dev`
- After changes: **Ctrl+Shift+R** (hard refresh)

## Key menus

Use the **vertical sidebar** inside Maintenance (top horizontal section menus are hidden).

| Area | Path |
|------|------|
| Dashboard | Maintenance → Dashboard (sidebar) |
| Work orders | Sidebar → Operations |
| Planning / Analysis / Reporting / Configuration | Sidebar groups |
| RUL & TOBM | Sidebar → Reporting → RUL & TOBM |

## Push to GitHub

Copy this entire `maintenance/` folder to your GitHub repo, then commit and push.
