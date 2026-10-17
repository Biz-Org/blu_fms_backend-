# -*- coding: utf-8 -*-
"""Equipment overview dashboard — card/list screen with live KPIs."""

from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models

from odoo.addons.maintenance.models.maintenance_domain import (
    domain_filter_clause,
    domain_filter_options,
    domain_label,
)


class MaintenanceEquipmentOverview(models.Model):
    _inherit = 'maintenance.equipment'

    @api.model
    def get_equipment_overview(self, filters=None):
        filters = filters or {}
        search = (filters.get('search') or '').strip().lower()
        status_filter = (filters.get('status') or 'all').lower()
        team_id = filters.get('team_id')
        category_id = filters.get('category_id')
        maint_domain = filters.get('maintenance_domain') or 'all'
        sort = (filters.get('sort') or 'name_asc').lower()
        today = fields.Date.context_today(self)
        company_ids = [False, self.env.company.id]
        domain_clause = domain_filter_clause(maint_domain)

        Equipment = self.with_context(active_test=False)
        Request = self.env['maintenance.request']
        Team = self.env['maintenance.team']
        Category = self.env['maintenance.equipment.category']

        domain = [('company_id', 'in', company_ids)] + domain_clause
        if team_id and team_id != 'all':
            try:
                domain.append(('maintenance_team_id', '=', int(team_id)))
            except (TypeError, ValueError):
                pass
        if category_id and category_id != 'all':
            try:
                domain.append(('category_id', '=', int(category_id)))
            except (TypeError, ValueError):
                pass

        equipment = Equipment.search(domain)
        open_requests = Request.search([
            ('company_id', 'in', company_ids),
            ('archive', '=', False),
            ('stage_id.done', '=', False),
            ('equipment_id', 'in', equipment.ids),
        ] + domain_clause) if equipment else Request.browse()

        eq_open_map = defaultdict(list)
        for req in open_requests:
            if req.equipment_id:
                eq_open_map[req.equipment_id.id].append(req)

        month_start = today.replace(day=1)
        new_this_month = 0

        cards = []
        counts = {
            'total': 0,
            'active': 0,
            'under_maintenance': 0,
            'inactive': 0,
        }

        for eq in equipment:
            opens = eq_open_map.get(eq.id, [])
            life = float(eq.life_consumed_percent or 0.0)
            inactive = (not eq.active) or bool(eq.scrap_date)
            under = bool(opens) and not inactive
            active = (not inactive) and not under

            if inactive:
                status, status_variant = _('Inactive'), 'muted'
                counts['inactive'] += 1
            elif under:
                status, status_variant = _('Under Maintenance'), 'danger'
                counts['under_maintenance'] += 1
            else:
                status, status_variant = _('Active'), 'success'
                counts['active'] += 1
            counts['total'] += 1

            create_date = fields.Datetime.to_datetime(eq.create_date).date() if eq.create_date else None
            if create_date and create_date >= month_start:
                new_this_month += 1

            cat_name = eq.category_id.name or ''
            domain_key = eq.maintenance_domain or 'plant'
            icon = 'fa-cogs'
            cat_l = cat_name.lower()
            if 'truck' in cat_l or 'vehicle' in cat_l:
                icon = 'fa-truck'
            elif 'crane' in cat_l or 'hoist' in cat_l:
                icon = 'fa-industry'
            elif 'fork' in cat_l:
                icon = 'fa-cubes'
            elif 'compress' in cat_l:
                icon = 'fa-tachometer'
            elif 'machine' in cat_l or 'cnc' in cat_l:
                icon = 'fa-cogs'
            elif 'trailer' in cat_l:
                icon = 'fa-bus'
            elif 'ac' in cat_l or 'hvac' in cat_l or 'air condition' in cat_l:
                icon = 'fa-snowflake-o'
            elif 'elevator' in cat_l or 'lift' in cat_l:
                icon = 'fa-building'
            elif 'light' in cat_l:
                icon = 'fa-lightbulb-o'
            elif 'plumb' in cat_l or 'water' in cat_l:
                icon = 'fa-tint'
            elif 'fire' in cat_l or 'safety' in cat_l:
                icon = 'fa-fire-extinguisher'
            elif domain_key == 'facility':
                icon = 'fa-building-o'

            row = {
                'id': eq.id,
                'name': eq.display_name or eq.name,
                'code': eq.equipment_code or '',
                'model': eq.model or '',
                'serial': eq.serial_no or '',
                'category': cat_name or _('Uncategorized'),
                'location': eq.location or '',
                'team': eq.maintenance_team_id.name or '',
                'teamId': eq.maintenance_team_id.id or False,
                'categoryId': eq.category_id.id or False,
                'maintenanceDomain': domain_key,
                'domainLabel': domain_label(self.env, domain_key),
                'status': status,
                'statusVariant': status_variant,
                'openOrders': len(opens),
                'lifeConsumed': int(round(life)),
                'icon': icon,
                'active': bool(eq.active) and not eq.scrap_date,
            }

            if search:
                blob = ' '.join([
                    row['name'], row['code'], row['model'], row['serial'],
                    row['category'], row['location'], row['team'], row['domainLabel'],
                ]).lower()
                if search not in blob:
                    continue

            if status_filter == 'active' and status_variant != 'success':
                continue
            if status_filter == 'under_maintenance' and status_variant != 'danger':
                continue
            if status_filter == 'inactive' and status_variant != 'muted':
                continue

            cards.append(row)

        if sort == 'name_desc':
            cards.sort(key=lambda r: (r['name'] or '').lower(), reverse=True)
        elif sort == 'open_desc':
            cards.sort(key=lambda r: (-r['openOrders'], (r['name'] or '').lower()))
        else:
            cards.sort(key=lambda r: (r['name'] or '').lower())

        total = counts['total'] or 1
        kpis = [
            {
                'key': 'total',
                'label': _('Total Equipment'),
                'value': str(counts['total']),
                'subtext': (
                    _('↑ %s new this month') % new_this_month
                    if new_this_month
                    else domain_label(self.env, maint_domain)
                ),
                'subVariant': 'success' if new_this_month else 'muted',
                'icon': 'fa-cube',
                'iconVariant': 'purple',
            },
            {
                'key': 'active',
                'label': _('Active Assets'),
                'value': str(counts['active']),
                'subtext': _('%s%% of total') % int(round(counts['active'] * 100 / total)),
                'subVariant': 'success',
                'icon': 'fa-check-circle',
                'iconVariant': 'green',
            },
            {
                'key': 'under_maintenance',
                'label': _('Under Maintenance'),
                'value': str(counts['under_maintenance']),
                'subtext': _('%s%% of total') % int(round(counts['under_maintenance'] * 100 / total)),
                'subVariant': 'danger',
                'icon': 'fa-wrench',
                'iconVariant': 'red',
            },
            {
                'key': 'inactive',
                'label': _('Inactive Assets'),
                'value': str(counts['inactive']),
                'subtext': _('%s%% of total') % int(round(counts['inactive'] * 100 / total)),
                'subVariant': 'muted',
                'icon': 'fa-pause-circle',
                'iconVariant': 'muted',
            },
        ]

        teams = Team.search(
            [('company_id', 'in', company_ids)] + domain_filter_clause(maint_domain),
            order='name',
        )
        categories = Category.search(domain_filter_clause(maint_domain), order='name')

        return {
            'kpis': kpis,
            'cards': cards,
            'counts': counts,
            'meta': {
                'maintenanceDomain': maint_domain if maint_domain in ('plant', 'facility') else 'all',
                'domainLabel': domain_label(self.env, maint_domain),
                'title': _('Equipment & Assets'),
                'subtitle': _(
                    'Industrial equipment and facility assets — filter by Plant, Facility, or All.'
                ),
            },
            'teamOptions': [{'value': 'all', 'label': _('All Teams')}] + [
                {'value': str(t.id), 'label': t.name} for t in teams
            ],
            'categoryOptions': [{'value': 'all', 'label': _('All Types')}] + [
                {'value': str(c.id), 'label': c.name} for c in categories
            ],
            'domainOptions': domain_filter_options(self.env),
            'statusOptions': [
                {'value': 'all', 'label': _('All Status')},
                {'value': 'active', 'label': _('Active')},
                {'value': 'under_maintenance', 'label': _('Under Maintenance')},
                {'value': 'inactive', 'label': _('Inactive')},
            ],
            'sortOptions': [
                {'value': 'name_asc', 'label': _('Name (A-Z)')},
                {'value': 'name_desc', 'label': _('Name (Z-A)')},
                {'value': 'open_desc', 'label': _('Open WO (High)')},
            ],
        }
