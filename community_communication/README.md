# Community & Communication

Odoo 18 addon for community engagement and communication. This repository
currently contains the **empty, installable module bootstrap**. Domain
features are added in later phases.

## Requirements

- Odoo 18.0
- Python 3.10–3.14 (Odoo 18.0 branch allows up to 3.14)
- PostgreSQL 13+

## Install

From the Odoo 18 source tree:

```bash
./odoo-bin \
  --addons-path=odoo/addons,addons,/Users/palakboricha/fmss \
  -d community_communication_dev \
  -i community_communication \
  --stop-after-init
```

Then start the server, update the Apps list if needed, and open **Community**.

## Groups

- **Resident** — portal users
- **Officer / Moderator / Administrator** — internal access levels

Settings and the user profile remain native Odoo.
# Check PG
pg_isready
brew services start postgresql@16
# Go to an Odoo 18 checkout (not the Odoo 19 tree at /Users/palakboricha/Documents/odoo)
cd /path/to/odoo-18
# Run Odoo Command
.venv/bin/python odoo-bin \
  --addons-path="/path/to/odoo-18/odoo/addons,/path/to/odoo-18/addons,/Users/palakboricha/fmss" \
  -d fms_odoo18 \
  --http-port=8073 \
  --db_host=localhost \
  --db_port=5432 \
  --dev=xml,assets
# Go to URL
http://127.0.0.1:8073
