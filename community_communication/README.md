# Community & Communication

Odoo 19 addon for community engagement and communication. This repository
currently contains the **empty, installable module bootstrap**. Domain
features are added in later phases.

## Requirements

- Odoo 19.0
- Python 3.10–3.14 (Odoo 19 venv)
- PostgreSQL 13+

## Install

From the Odoo 19 source tree:

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
- **Officer / Moderator / Administrator** — internal privilege levels

Settings and the user profile remain native Odoo.
# Check PG
pg_isready
brew services start postgresql@16
# Go to Odoo
cd /Users/palakboricha/Documents/odoo
# Run Odoo Command
.venv/bin/python odoo-bin \
  --addons-path="/Users/palakboricha/Documents/odoo/odoo/addons,/Users/palakboricha/Documents/odoo/addons,/Users/palakboricha/fmss" \
  -d community_communication_test \
  --http-port=8071 \
  --db_host=localhost \
  --db_port=5432 \
  --dev=xml,assets
# Go to URL
http://127.0.0.1:8071
