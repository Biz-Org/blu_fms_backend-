# -*- coding: utf-8 -*-
"""Plant Maintenance app dashboard — real operational metrics for the main dashboard screen."""

from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models

from odoo.addons.maintenance.models.maintenance_domain import (
    domain_filter_clause,
    domain_filter_options,
    domain_label,
)


class MaintenanceTeamPlantAppDashboard(models.Model):
    _inherit = 'maintenance.team'

    @api.model
    def get_plant_app_dashboard(self, filters=None):
        filters = filters or {}
        team_id = filters.get('team_id')
        maint_domain = (filters.get('maintenance_domain') or 'all')
        today = fields.Date.context_today(self)
        company_ids = [False, self.env.company.id]
        domain_clause = domain_filter_clause(maint_domain)

        Team = self.env['maintenance.team']
        Request = self.env['maintenance.request']
        Equipment = self.env['maintenance.equipment'].with_context(active_test=False)

        team_search = [('company_id', 'in', company_ids)] + domain_filter_clause(maint_domain)
        all_teams = Team.search(team_search, order='name')
        if team_id and team_id != 'all':
            try:
                team_id = int(team_id)
            except (TypeError, ValueError):
                team_id = False
        else:
            team_id = False

        def _team_clause(field_name='maintenance_team_id'):
            return [(field_name, '=', team_id)] if team_id else []

        # ---- Equipment ----
        eq_domain = [('company_id', 'in', company_ids)] + _team_clause() + domain_clause
        equipment = Equipment.search(eq_domain)
        total_equipment = len(equipment)
        active_equipment = equipment.filtered(lambda e: e.active and not e.scrap_date)
        inactive_equipment = equipment.filtered(lambda e: (not e.active) or bool(e.scrap_date))

        # ---- Requests / work orders (same model in this module) ----
        base_req = (
            [('company_id', 'in', company_ids), ('archive', '=', False)]
            + _team_clause()
            + domain_clause
        )
        all_requests = Request.search(base_req)
        open_requests = all_requests.filtered(lambda r: not r.stage_id.done)
        done_requests = all_requests.filtered(lambda r: r.stage_id.done)

        def _stage_bucket(req):
            name = (req.stage_id.name or '').strip().lower()
            if req.kanban_state == 'blocked':
                return 'on_hold'
            if 'new' in name:
                return 'new'
            if 'progress' in name:
                return 'in_progress'
            if 'scrap' in name or 'cancel' in name:
                return 'cancelled'
            if req.stage_id.done or 'repair' in name or 'complete' in name or 'done' in name:
                return 'completed'
            return 'in_progress' if not req.stage_id.done else 'completed'

        request_counts = {'new': 0, 'in_progress': 0, 'completed': 0, 'cancelled': 0}
        wo_counts = {'open': 0, 'in_progress': 0, 'completed': 0, 'on_hold': 0}
        for req in all_requests:
            bucket = _stage_bucket(req)
            if bucket == 'new':
                request_counts['new'] += 1
                wo_counts['open'] += 1
            elif bucket == 'in_progress':
                request_counts['in_progress'] += 1
                wo_counts['in_progress'] += 1
            elif bucket == 'cancelled':
                request_counts['cancelled'] += 1
                wo_counts['completed'] += 1
            elif bucket == 'on_hold':
                request_counts['in_progress'] += 1
                wo_counts['on_hold'] += 1
            else:
                request_counts['completed'] += 1
                wo_counts['completed'] += 1

        overdue = open_requests.filtered(
            lambda r: (r.schedule_date and fields.Datetime.to_datetime(r.schedule_date).date() < today)
            or (r.planned_date and r.planned_date < today)
        )

        preventive_open = open_requests.filtered(
            lambda r: (r.maintenance_type or '') == 'preventive'
            or (r.planning_maintenance_type or '') == 'preventive'
        )
        preventive_due = preventive_open.filtered(
            lambda r: (
                (r.schedule_date and fields.Datetime.to_datetime(r.schedule_date).date() <= today + timedelta(days=14))
                or (r.planned_date and r.planned_date <= today + timedelta(days=14))
                or (not r.schedule_date and not r.planned_date)
            )
        )

        # ---- Equipment health ----
        eq_open_map = defaultdict(list)
        for req in open_requests:
            if req.equipment_id:
                eq_open_map[req.equipment_id.id].append(req)

        health = {'healthy': 0, 'under_maintenance': 0, 'needs_attention': 0, 'inactive': 0}
        attention_rows = []
        for eq in equipment:
            opens = eq_open_map.get(eq.id, [])
            life = float(eq.life_consumed_percent or 0.0)
            has_overdue = any(
                (r.schedule_date and fields.Datetime.to_datetime(r.schedule_date).date() < today)
                or (r.planned_date and r.planned_date < today)
                for r in opens
            )
            high_pri = any(r.priority in ('2', '3') or r.impact_level == 'high' for r in opens)

            if (not eq.active) or eq.scrap_date:
                health['inactive'] += 1
                status_label, status_variant = _('Inactive'), 'muted'
            elif opens and (has_overdue or high_pri or life >= 75):
                health['needs_attention'] += 1
                status_label, status_variant = _('Needs Attention'), 'danger'
            elif opens:
                health['under_maintenance'] += 1
                status_label, status_variant = _('Under Maintenance'), 'warning'
            elif life >= 70:
                health['needs_attention'] += 1
                status_label, status_variant = _('Needs Attention'), 'danger'
            else:
                health['healthy'] += 1
                status_label, status_variant = _('Healthy'), 'success'

            issue_score = len(opens) * 10 + (20 if has_overdue else 0) + (15 if high_pri else 0) + int(life / 5)
            if status_variant in ('danger', 'warning') or issue_score >= 15:
                attention_rows.append({
                    'id': eq.id,
                    'name': eq.display_name,
                    'location': eq.location or '',
                    'openOrders': len(opens),
                    'lifeConsumed': int(round(life)),
                    'status': status_label,
                    'statusVariant': status_variant,
                    'score': issue_score,
                })

        attention_rows.sort(key=lambda r: (-r['score'], -r['openOrders'], -r['lifeConsumed']))
        attention_rows = attention_rows[:8]

        priority_map = {
            '0': _('Very Low'),
            '1': _('Low'),
            '2': _('Normal'),
            '3': _('High'),
        }

        def _priority_variant(code):
            if code == '3':
                return 'danger'
            if code == '2':
                return 'warning'
            return 'muted'

        def _type_label(req):
            selection = req._fields['maintenance_type']._description_selection(req.env)
            return dict(selection).get(req.maintenance_type, req.maintenance_type or _('—'))

        def _req_date(req):
            if req.schedule_date:
                return fields.Datetime.to_datetime(req.schedule_date).date()
            if req.planned_date:
                return req.planned_date
            return req.request_date

        upcoming = []
        upcoming_src = preventive_open.sorted(
            key=lambda r: _req_date(r) or today + timedelta(days=365)
        )[:8]
        for req in upcoming_src:
            d = _req_date(req)
            upcoming.append({
                'id': req.id,
                'date': fields.Date.to_string(d) if d else '',
                'equipment': req.equipment_id.display_name or _('No equipment'),
                'type': _type_label(req),
                'priority': priority_map.get(req.priority, _('Normal')),
                'priorityVariant': _priority_variant(req.priority),
                'status': req.stage_id.name or '',
                'statusVariant': 'warning' if _stage_bucket(req) != 'new' else 'info',
            })

        recent = []
        recent_src = all_requests.sorted(
            key=lambda r: r.request_date or fields.Date.from_string('1970-01-01'),
            reverse=True,
        )[:10]
        for req in recent_src:
            bucket = _stage_bucket(req)
            status_variant = {
                'new': 'info',
                'in_progress': 'warning',
                'on_hold': 'danger',
                'completed': 'success',
                'cancelled': 'muted',
            }.get(bucket, 'muted')
            recent.append({
                'id': req.id,
                'number': req.work_order_display or req.work_order_sequence or _('WO-%s') % req.id,
                'equipment': req.equipment_id.display_name or _('No equipment'),
                'type': _type_label(req),
                'priority': priority_map.get(req.priority, _('Normal')),
                'priorityVariant': _priority_variant(req.priority),
                'status': req.stage_id.name or '',
                'statusVariant': status_variant,
            })

        trend_start = today - timedelta(days=56)
        week_buckets = []
        for i in range(7, -1, -1):
            week_end = today - timedelta(days=i * 7)
            week_start = week_end - timedelta(days=6)
            week_buckets.append((week_start, week_end))

        created_by_week = [0] * 8
        closed_by_week = [0] * 8
        for req in all_requests:
            if req.request_date and req.request_date >= trend_start:
                for idx, (ws, we) in enumerate(week_buckets):
                    if ws <= req.request_date <= we:
                        created_by_week[idx] += 1
                        break
            if req.close_date and req.close_date >= trend_start:
                for idx, (ws, we) in enumerate(week_buckets):
                    if ws <= req.close_date <= we:
                        closed_by_week[idx] += 1
                        break

        max_trend = max(created_by_week + closed_by_week + [1])
        weekly = []
        for idx, (ws, _we) in enumerate(week_buckets):
            weekly.append({
                'label': ws.strftime('%d %b'),
                'created': created_by_week[idx],
                'closed': closed_by_week[idx],
                'createdPct': int(round(created_by_week[idx] * 100 / max_trend)),
                'closedPct': int(round(closed_by_week[idx] * 100 / max_trend)),
            })

        def _dist(items):
            total = sum(count for _k, _l, count, _v in items) or 1
            return [
                {
                    'key': key,
                    'label': label,
                    'count': count,
                    'pct': int(round(count * 100 / total)),
                    'variant': variant,
                }
                for key, label, count, variant in items
            ]

        equipment_health = _dist([
            ('healthy', _('Healthy'), health['healthy'], 'success'),
            ('under_maintenance', _('Under Maintenance'), health['under_maintenance'], 'warning'),
            ('needs_attention', _('Needs Attention'), health['needs_attention'], 'danger'),
            ('inactive', _('Inactive'), health['inactive'], 'muted'),
        ])
        request_status = _dist([
            ('new', _('New'), request_counts['new'], 'info'),
            ('in_progress', _('In Progress'), request_counts['in_progress'], 'warning'),
            ('completed', _('Completed'), request_counts['completed'], 'success'),
            ('cancelled', _('Cancelled'), request_counts['cancelled'], 'muted'),
        ])
        work_order_status = _dist([
            ('open', _('Open'), wo_counts['open'], 'info'),
            ('in_progress', _('In Progress'), wo_counts['in_progress'], 'warning'),
            ('completed', _('Completed'), wo_counts['completed'], 'success'),
            ('on_hold', _('On Hold'), wo_counts['on_hold'], 'danger'),
        ])

        scope_label = domain_label(self.env, maint_domain)
        kpis = [
            {
                'key': 'total_equipment',
                'label': _('Total Assets'),
                'value': str(total_equipment),
                'subtext': scope_label,
                'icon': 'fa-cogs',
                'iconVariant': 'purple',
            },
            {
                'key': 'active_equipment',
                'label': _('Active Assets'),
                'value': str(len(active_equipment)),
                'subtext': _('Currently operational'),
                'icon': 'fa-check-circle',
                'iconVariant': 'green',
            },
            {
                'key': 'open_requests',
                'label': _('Open Requests'),
                'value': str(len(open_requests)),
                'subtext': _('Not yet completed'),
                'icon': 'fa-ticket',
                'iconVariant': 'blue',
            },
            {
                'key': 'open_work_orders',
                'label': _('Open Work Orders'),
                'value': str(len(open_requests)),
                'subtext': _('Active execution jobs'),
                'icon': 'fa-wrench',
                'iconVariant': 'purple',
            },
            {
                'key': 'overdue',
                'label': _('Overdue Work Orders'),
                'value': str(len(overdue)),
                'subtext': _('Past planned schedule'),
                'icon': 'fa-clock-o',
                'iconVariant': 'red',
            },
            {
                'key': 'pm_due',
                'label': _('PM Due'),
                'value': str(len(preventive_due)),
                'subtext': _('Next 14 days / due'),
                'icon': 'fa-calendar-check-o',
                'iconVariant': 'yellow',
            },
        ]

        return {
            'kpis': kpis,
            'equipmentHealth': equipment_health,
            'requestStatus': request_status,
            'workOrderStatus': work_order_status,
            'upcomingMaintenance': upcoming,
            'recentWorkOrders': recent,
            'attentionEquipment': attention_rows,
            'weeklyTrend': weekly,
            'meta': {
                'totalEquipment': total_equipment,
                'activeEquipment': len(active_equipment),
                'inactiveEquipment': len(inactive_equipment),
                'openRequests': len(open_requests),
                'completedRequests': len(done_requests),
                'overdue': len(overdue),
                'maintenanceDomain': maint_domain if maint_domain in ('plant', 'facility') else 'all',
                'domainLabel': scope_label,
                'title': _('Maintenance Dashboard'),
                'subtitle': _(
                    'Plant equipment and facility assets — health, requests, work orders, and upcoming PM.'
                ),
            },
            'teamOptions': [{'value': 'all', 'label': _('All Teams')}] + [
                {'value': str(t.id), 'label': t.name} for t in all_teams
            ],
            'domainOptions': domain_filter_options(self.env),
            'rows': [],
            'summary': {},
            'warnings': [],
            'statusOptions': [],
            'tableSubtitle': '',
        }
