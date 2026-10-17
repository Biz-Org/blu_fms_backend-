# -*- coding: utf-8 -*-
"""Remove the temporary FMS demo data created by fms_temp_demo_load.py.

Deletes equipment whose serial number starts with SN-TMP-FMS, every maintenance
request linked to that equipment (including ones you created on it while testing),
and the tmp.fms.* technician users (archived instead if they cannot be deleted).

Run from the odoo18 folder:
    .\\venv\\Scripts\\python.exe addons\\maintenance\\scripts\\fms_temp_demo_remove.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import odoo  # noqa: E402
from odoo import api  # noqa: E402
from odoo.tools import config  # noqa: E402

SERIAL_PREFIX = 'SN-TMP-FMS'
LOGIN_PREFIX = 'tmp.fms.'


def main():
    config.parse_config(['-c', str(ROOT / 'odoo.conf')])
    registry = odoo.modules.registry.Registry(config['db_name'])
    with registry.cursor() as cr:
        env = api.Environment(cr, odoo.SUPERUSER_ID, {'active_test': False})
        Equipment = env['maintenance.equipment'].sudo()
        Request = env['maintenance.request'].sudo()

        equipment = Equipment.search([('serial_no', '=like', f'{SERIAL_PREFIX}%')])
        requests = Request.search([('equipment_id', 'in', equipment.ids)])
        removed_requests = env['maintenance.demo.cleanup']._unlink_request_tree(requests)
        env['maintenance.rul.tobm.dashboard'].sudo().search([
            ('equipment_id', 'in', equipment.ids),
        ]).write({'equipment_id': False})
        removed_equipment = len(equipment)
        equipment.unlink()

        users = env['res.users'].sudo().search([('login', '=like', f'{LOGIN_PREFIX}%')])
        user_note = 'deleted'
        try:
            with cr.savepoint():
                users.unlink()
        except Exception:
            users.write({'active': False})
            user_note = 'archived'

        cr.commit()
        print(f'Removed {removed_requests} requests, {removed_equipment} equipment, '
              f'{len(users)} technicians ({user_note}).')


if __name__ == '__main__':
    main()
