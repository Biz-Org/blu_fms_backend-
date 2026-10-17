# -*- coding: utf-8 -*-
"""Load temporary Facility Management (FMS) demo data into the configured database.

Everything created here is tagged so fms_temp_demo_remove.py can delete it:
equipment serial numbers start with SN-TMP-FMS and technician logins with tmp.fms.
Requests are linked to that equipment and are removed with it.

Run from the odoo18 folder:
    .\\venv\\Scripts\\python.exe addons\\maintenance\\scripts\\fms_temp_demo_load.py
"""
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import odoo  # noqa: E402
from odoo import api  # noqa: E402
from odoo.tools import config  # noqa: E402

SERIAL_PREFIX = 'SN-TMP-FMS'
LOGIN_PREFIX = 'tmp.fms.'

TODAY = date.today()


def days(n):
    return TODAY + timedelta(days=n)


def at(day, hour):
    return datetime.combine(day, time(hour, 0))


def ensure_users(env):
    Users = env['res.users'].sudo().with_context(no_reset_password=True, active_test=False)
    group_user = env.ref('base.group_user')
    specs = [
        ('ravi', 'Ravi Kumar'),
        ('suresh', 'Suresh Patil'),
        ('anita', 'Anita Desai'),
    ]
    users = {}
    for key, name in specs:
        login = LOGIN_PREFIX + key
        user = Users.search([('login', '=', login)], limit=1)
        if not user:
            user = Users.create({
                'name': name,
                'login': login,
                'email': f'{key}@fms.example.com',
                'groups_id': [(6, 0, [group_user.id])],
                # Inbox only: no outgoing e-mail attempts without an SMTP server.
                'notification_type': 'inbox',
            })
        elif not user.active:
            user.active = True
        users[key] = user
    return users


def create_equipment(env, users, team):
    cat = lambda xid: env.ref(f'maintenance.{xid}').id  # noqa: E731
    specs = [
        ('ahu2', 'AHU-02 Roof AC', 'FMS-AC-002', 'equipment_category_hvac_ac',
         'Building B - Roof', 'Daikin RXYQ20', date(2023, 6, 1), 180, 920000),
        ('chiller', 'Chiller CH-01', 'FMS-AC-003', 'equipment_category_hvac_ac',
         'Plant Room - Basement', 'Carrier 30XW', date(2022, 9, 15), 240, 2450000),
        ('lift', 'Passenger Elevator L1', 'FMS-ELV-001', 'equipment_category_elevators',
         'Building A - Lobby', 'Otis Gen2', date(2022, 1, 15), 120, 1800000),
        ('pump', 'Booster Pump BP-02', 'FMS-PL-001', 'equipment_category_plumbing',
         'Utility Room B2', 'Grundfos CR 15', date(2024, 2, 1), 200, 185000),
        ('fire', 'Fire Panel FP-Main', 'FMS-FS-001', 'equipment_category_fire_safety',
         'Security Control Room', 'Notifier NFS2-3030', date(2021, 11, 1), 365, 640000),
        ('led', 'Parking LED Panel Bank', 'FMS-LT-001', 'equipment_category_lighting',
         'Basement Parking P1', 'Philips CoreLine', date(2024, 7, 10), 300, 95000),
    ]
    Equipment = env['maintenance.equipment']
    equipment = {}
    for i, (key, name, code, cat_xid, location, model, effective, mtbf, cost) in enumerate(specs, start=1):
        if Equipment.with_context(active_test=False).search_count([('equipment_code', '=', code)]):
            code = f'{code}-T'
        equipment[key] = Equipment.create({
            'name': name,
            'equipment_code': code,
            'serial_no': f'{SERIAL_PREFIX}-{i:03d}',
            'category_id': cat(cat_xid),
            'maintenance_domain': 'facility',
            'maintenance_team_id': team.id,
            'location': location,
            'model': model,
            'owner_user_id': users['anita'].id,
            'corrective_responsible_user_id': users['anita'].id,
            'preventive_responsible_user_id': users['anita'].id,
            'effective_date': effective,
            'expected_mtbf': mtbf,
            'cost': cost,
            'warranty_date': effective.replace(year=effective.year + 3),
            'note': '<p>Temporary FMS demo asset.</p>',
        })
    return equipment


def new_request(env, eq, team, **vals):
    base = {
        'equipment_id': eq.id,
        'maintenance_team_id': team.id,
        'work_area': eq.location,
        'maintenance_type': 'corrective',
        'priority': '2',
        'impact_level': 'medium',
        'affected_department': 'Facilities',
    }
    base.update(vals)
    if base['maintenance_type'] == 'preventive':
        base.setdefault('planning_maintenance_type', 'preventive')
    return env['maintenance.request'].create(base)


def plan(req, planned_date, duration, *, elec=False, mech=False, notes='',
         elec_cost=0.0, mech_cost=0.0, spares=(), crew=()):
    req.write({
        'planned_date': planned_date,
        'planned_duration': duration,
        'electrician_required': elec,
        'mechanic_required': mech,
        'planning_notes': notes,
        'electrical_cost': elec_cost,
        'mechanical_cost': mech_cost,
        'spare_line_ids': [
            (0, 0, dict(sequence=(n + 1) * 10, **s)) for n, s in enumerate(spares)
        ],
        'manpower_line_ids': [
            (0, 0, dict(sequence=n + 1, **c)) for n, c in enumerate(crew)
        ],
    })
    req.message_post(body='Maintenance planning details were saved.')


def spare(name, code, qty, cost, available=True, lead='Same day'):
    return {
        'spare_name': name,
        'part_code': code,
        'quantity': qty,
        'cost': cost,
        'stock_status': 'available' if available else 'out_of_stock',
        'lead_time': lead,
    }


def tech(user, skill, task, hours, status='available', notes=''):
    return {
        'user_id': user.id,
        'skill_type': skill,
        'status': status,
        'assigned_task': task,
        'planned_hours': hours,
        'notes': notes,
    }


def issue_and_order(req):
    if req.spare_line_ids.filtered(lambda l: l.stock_status == 'available'):
        req.action_issue_from_store()
    if req.spare_line_ids.filtered(lambda l: l.stock_status == 'out_of_stock'):
        req.action_create_purchase_request()


def finish(req, *, actual, notes, decision, root_cause='', why=(), actions=(), fishbone=''):
    vals = {
        'actual_hours': actual,
        'execution_notes': notes,
        'decision_resolution_notes': decision,
    }
    if root_cause:
        vals['final_root_cause'] = root_cause
    if fishbone:
        vals['fishbone_summary'] = fishbone
    if why:
        vals['rca_line_ids'] = [
            (0, 0, {'sequence': n + 1, 'problem_statement': q, 'cause_statement': a})
            for n, (q, a) in enumerate(why)
        ]
    if actions:
        vals['corrective_action_ids'] = [(0, 0, {'name': a, 'done': d}) for a, d in actions]
    req.write(vals)
    req.action_mark_go()
    req.action_workflow_complete_maintenance()


def backdate(req, requested, closed=None):
    vals = {'request_date': requested, 'planned_date': requested,
            'schedule_date': at(requested, 10)}
    if closed:
        vals['close_date'] = closed
    req.write(vals)


def load(env):
    Equipment = env['maintenance.equipment'].with_context(active_test=False)
    if Equipment.search_count([('serial_no', '=like', f'{SERIAL_PREFIX}%')]):
        print('Temporary FMS demo data is already loaded. Run fms_temp_demo_remove.py first to reload it.')
        return False

    team = env.ref('maintenance.maintenance_team_facility_fms')
    users = ensure_users(env)
    team.sudo().write({'member_ids': [(4, u.id) for u in users.values()]})
    eq = create_equipment(env, users, team)
    ravi, suresh, anita = users['ravi'], users['suresh'], users['anita']

    # 1. Just reported (step 1 only)
    r1 = new_request(
        env, eq['lift'], team,
        name='Elevator door not closing fully',
        priority='3', impact_level='high', affected_department='Building A occupants',
        request_date=TODAY, schedule_date=at(TODAY, 15), duration=2.0,
        description='<p>Door reopens 2-3 times before closing on floors 2 and 4. Reported by front desk.</p>',
    )

    # 2. Planned with crew and spares, work order not created yet (steps 1-4)
    r2 = new_request(
        env, eq['pump'], team,
        name='Booster pump leaking at mechanical seal',
        request_date=days(-1), schedule_date=at(days(1), 9), duration=3.0,
        description='<p>Steady drip at seal housing, water pooling under the skid.</p>',
    )
    plan(r2, days(1), 3.0, mech=True, notes='Isolate pump, drain line, replace seal kit.',
         mech_cost=60.0,
         spares=[
             spare('Mechanical seal kit 22 mm', 'MS-22', 1, 85.0),
             spare('Casing gasket set', 'GK-CR15', 1, 18.0, available=False, lead='3-4 days'),
         ],
         crew=[
             tech(suresh, 'mechanical', 'Replace mechanical seal and gasket', 3.0),
         ])
    issue_and_order(r2)

    # 3. Work order in progress, running over plan, decision still NO GO
    r3 = new_request(
        env, eq['fire'], team,
        name='Fire panel showing earth fault on Zone 3',
        priority='3', impact_level='high', affected_department='Safety / Security',
        request_date=TODAY, schedule_date=at(TODAY, 9), duration=3.0,
        description='<p>Panel buzzer active, earth fault LED on Zone 3 loop.</p>',
    )
    plan(r3, TODAY, 3.0, elec=True, notes='Loop test Zone 3; check junction boxes on level 3.',
         elec_cost=90.0,
         spares=[spare('Fire-rated cable 1.5 mm (50 m)', 'FRC-15', 1, 65.0)],
         crew=[
             tech(ravi, 'electrical', 'Trace earth fault on Zone 3 loop', 3.0, status='busy'),
         ])
    issue_and_order(r3)
    r3.action_create_maintenance_order()
    r3.write({
        'actual_hours': 4.5,
        'execution_notes': 'Fault traced to water ingress in JB-3.2; junction box replaced, loop re-tested. Waiting for fire officer sign-off.',
    })

    # 4. Held as NO GO and paused
    r4 = new_request(
        env, eq['chiller'], team,
        name='Chiller tripping on high condenser pressure',
        priority='3', impact_level='high', affected_department='Whole building cooling',
        request_date=days(-2), schedule_date=at(days(-2), 11), duration=6.0,
        description='<p>Chiller trips 20-30 min after start. Condenser pressure alarm.</p>',
    )
    plan(r4, days(-1), 6.0, elec=True, mech=True,
         notes='Inspect condenser tubes and cooling tower flow; OEM support on standby.',
         elec_cost=120.0, mech_cost=200.0,
         spares=[
             spare('Condenser tube cleaning kit', 'CTC-01', 1, 140.0),
             spare('Compressor bearing set', 'CB-30XW', 1, 1250.0, available=False, lead='10-14 days'),
         ],
         crew=[
             tech(ravi, 'electrical', 'Check control circuit and pressure switch', 2.0),
             tech(suresh, 'mechanical', 'Clean condenser tubes, inspect compressor', 4.0),
         ])
    issue_and_order(r4)
    r4.action_create_maintenance_order()
    r4.write({
        'actual_hours': 5.0,
        'execution_notes': 'Condenser tubes cleaned. Abnormal bearing noise from compressor during test run.',
        'decision_resolution_notes': 'Unit isolated - unsafe to restart until compressor bearing set is replaced by OEM.',
    })
    r4.action_mark_no_go()
    r4.action_pause_work()

    # 5. Completed, waiting for Verify / Close (with RCA content for the analysis screens)
    r5 = new_request(
        env, eq['led'], team,
        name='Parking LED bank - 12 fittings not working',
        impact_level='medium', affected_department='Parking / Security',
        request_date=days(-1), schedule_date=at(days(-1), 14), duration=3.0,
        description='<p>Row C and D fittings dark since last night.</p>',
    )
    plan(r5, days(-1), 3.0, elec=True, notes='Check drivers and MCB on DB-P1.', elec_cost=45.0,
         spares=[spare('LED driver 40 W', 'LDR-40', 4, 22.0)],
         crew=[tech(ravi, 'electrical', 'Replace failed drivers, test circuit', 3.0)])
    issue_and_order(r5)
    r5.action_create_maintenance_order()
    finish(
        r5, actual=2.5,
        notes='Replaced 4 LED drivers, reset MCB, all 12 fittings working.',
        decision='All rows lit, handed over to security.',
        root_cause='Voltage surge from DB-P1 damaged LED drivers',
        why=[
            ('Why are 12 fittings dark?', 'Their LED drivers failed'),
            ('Why did the drivers fail?', 'Over-voltage on the parking lighting circuit'),
            ('Why was there over-voltage?', 'Surge from DB-P1 during grid switchover'),
            ('Why did the surge reach the drivers?', 'No surge protection device on DB-P1'),
        ],
        actions=[('Install SPD on DB-P1', False), ('Add DB-P1 to quarterly thermography', False)],
        fishbone='Man: none; Machine: LED drivers without surge rating; Method: no SPD standard; '
                 'Material: low-cost drivers; Environment: grid switchover surges',
    )

    # 6-7. Closed corrective history on AHU-02 (gives MTBF / MTTR)
    r6 = new_request(env, eq['ahu2'], team, name='AHU-02 compressor tripping on overload',
                     priority='3', impact_level='high', request_date=days(-221))
    plan(r6, days(-221), 5.0, elec=True, mech=True, elec_cost=80.0, mech_cost=120.0,
         spares=[spare('Contactor 32 A', 'CT-32', 1, 38.0), spare('Overload relay', 'OLR-25', 1, 52.0)],
         crew=[tech(ravi, 'electrical', 'Replace contactor and overload relay', 3.0),
               tech(suresh, 'mechanical', 'Check compressor amps and refrigerant', 2.0)])
    issue_and_order(r6)
    r6.action_create_maintenance_order()
    finish(r6, actual=6.0,
           notes='Contactor contacts pitted; contactor and overload relay replaced. Amps normal.',
           decision='Run-tested 1 hour, cooling normal.',
           root_cause='Worn contactor contacts caused single-phasing and overload trips',
           why=[('Why did the compressor trip?', 'Overload relay operated'),
                ('Why did the overload operate?', 'Compressor single-phasing'),
                ('Why single-phasing?', 'Pitted contactor contacts')],
           actions=[('Add contactor inspection to quarterly PM', True)])
    r6.action_workflow_verify_close()
    backdate(r6, days(-221), days(-219))

    r7 = new_request(env, eq['ahu2'], team, name='AHU-02 low airflow - blower belt slipping',
                     impact_level='medium', request_date=days(-73))
    plan(r7, days(-73), 2.0, mech=True, mech_cost=40.0,
         spares=[spare('Blower V-belt B-48', 'VB-B48', 2, 14.0)],
         crew=[tech(suresh, 'mechanical', 'Replace and tension blower belts', 2.0)])
    issue_and_order(r7)
    r7.action_create_maintenance_order()
    finish(r7, actual=1.5,
           notes='Both belts glazed; replaced and tensioned. Airflow restored.',
           decision='Airflow checked at diffusers, normal.',
           root_cause='Belt tension not checked since installation; belts glazed and slipped',
           actions=[('Add belt tension check to monthly PM', True)])
    r7.action_workflow_verify_close()
    backdate(r7, days(-73), days(-72))

    # 8. Closed preventive job (no root cause needed)
    r8 = new_request(env, eq['ahu2'], team, name='AHU-02 quarterly filter and coil service',
                     maintenance_type='preventive', priority='1', impact_level='low',
                     request_date=days(-27))
    plan(r8, days(-27), 3.0, mech=True, mech_cost=50.0,
         spares=[spare('Pleated filter 24x24', 'PF-2424', 4, 9.0)],
         crew=[tech(suresh, 'mechanical', 'Replace filters, wash coil', 3.0)])
    issue_and_order(r8)
    r8.action_create_maintenance_order()
    finish(r8, actual=2.5, notes='Filters replaced, coil washed, drain pan cleaned.',
           decision='Routine PM complete, unit running normally.')
    r8.action_workflow_verify_close()
    backdate(r8, days(-27), days(-27))

    # 9. Upcoming recurring preventive job (calendar)
    r9 = new_request(env, eq['lift'], team, name='Elevator monthly safety inspection',
                     maintenance_type='preventive', priority='1', impact_level='low',
                     request_date=TODAY, schedule_date=at(days(7), 10), duration=2.0,
                     recurring_maintenance=True, repeat_interval=1, repeat_unit='month',
                     repeat_type='forever')
    plan(r9, days(7), 2.0, elec=True, mech=True,
         notes='Monthly statutory inspection with OEM technician.',
         crew=[tech(ravi, 'electrical', 'Controller and safety circuit checks', 1.0),
               tech(suresh, 'mechanical', 'Door operator, ropes and brake checks', 1.0)])

    requests = r1 | r2 | r3 | r4 | r5 | r6 | r7 | r8 | r9
    print(f'Created {len(users)} technicians, {len(eq)} equipment, {len(requests)} requests:')
    for r in requests:
        print(f'  MR-{r.id:<4} {r.stage_id.name:<12} {r.execution_status:<11} '
              f'{(r.work_order_sequence or "-"):<8} {r.go_no_go_decision:<6} {r.name}')
    return True


def main():
    config.parse_config(['-c', str(ROOT / 'odoo.conf')])
    registry = odoo.modules.registry.Registry(config['db_name'])
    with registry.cursor() as cr:
        env = api.Environment(cr, odoo.SUPERUSER_ID, {})
        admin = env.ref('base.user_admin')
        env = api.Environment(cr, admin.id, {'lang': admin.lang or 'en_US', 'tz': admin.tz})
        if load(env):
            cr.commit()
            print('Done. Refresh the browser.')


if __name__ == '__main__':
    main()
