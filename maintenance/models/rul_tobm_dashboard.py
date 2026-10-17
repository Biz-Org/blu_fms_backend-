# -*- coding: utf-8 -*-

import json
import logging
from datetime import timedelta

from markupsafe import Markup, escape

_logger = logging.getLogger(__name__)
from odoo.exceptions import ValidationError
from odoo.osv import expression
from odoo import api, fields, models, _

from .rul_tobm_embed_css import RUL_TOBM_EMBED_CSS, RUL_TOBM_EMBED_VERSION


class MaintenanceRulTobmDashboard(models.Model):
    _name = 'maintenance.rul.tobm.dashboard'
    _description = 'Maintenance RUL & TOBM Report'

    FAILURE_LIFE_PCT = 75.0
    FAILURE_RUL_PCT = 25.0
    TOBM_WINDOW_START = 65.0
    MAINTENANCE_START = 85.0

    name = fields.Char(default='Maintenance RUL & TOBM', required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    analysis_period_days = fields.Integer(
        string='Analysis period (days)',
        default=30,
        help='Include maintenance requests whose request date is within this many days.',
    )
    category_id = fields.Many2one(
        'maintenance.equipment.category',
        string='Equipment category',
        help='Leave empty to include all categories in scope.',
    )
    fleet_vehicle_scope = fields.Boolean(
        string='Fleet / vehicle equipment only',
        default=False,
    )
    equipment_id = fields.Many2one(
        'maintenance.equipment',
        string='Detail equipment',
        domain="[('company_id', '=', company_id)]",
    )
    dashboard_html = fields.Html(
        string='RUL & TOBM HTML',
        compute='_compute_rul_tobm_dashboard',
        sanitize=False,
    )

    @api.constrains('analysis_period_days')
    def _check_rul_analysis_period_days(self):
        for rec in self:
            d = rec.analysis_period_days or 0
            if d < 1 or d > 365:
                raise ValidationError(_('Analysis period must be between 1 and 365 days.'))

    def _action_reload_rul_tobm_form(self):
        """Open full-page RUL mockup (HTTP dashboard)."""
        self.ensure_one()
        action = self.env.ref(
            'maintenance.maintenance_rul_tobm_dashboard_action',
            raise_if_not_found=False,
        )
        if action and action._name == 'ir.actions.act_url':
            return action.read()[0]
        return {
            'type': 'ir.actions.act_url',
            'url': f'/maintenance/rul_tobm/dashboard/{self.id}',
            'target': 'self',
            'name': self.name or _('RUL & TOBM Report'),
        }

    def action_refresh_rul_tobm_data(self):
        """RPC helper for the web client (invalidate only)."""
        self.invalidate_recordset(['dashboard_html'])
        return True

    def action_refresh_rul_tobm(self):
        return self._action_reload_rul_tobm_form()

    def action_apply_filters(self):
        return self._action_reload_rul_tobm_form()

    def write(self, vals):
        res = super().write(vals)
        if {'analysis_period_days', 'fleet_vehicle_scope', 'category_id', 'equipment_id'} & set(vals):
            self.invalidate_recordset(['dashboard_html'])
        return res

    @api.model
    def _period_options(self):
        return [7, 14, 30, 60, 90, 180, 365]

    @api.model
    def _equipment_short_label(self, equipment):
        """UI label without serial — matches reference mockup titles."""
        if not equipment:
            return ''
        name = (equipment.name or '').strip()
        if '/' in name:
            name = name.split('/')[0].strip()
        if name:
            return name
        full = str(equipment.display_name or '').strip()
        return full.split('/')[0].strip() if '/' in full else full

    def _next_critical_display_name(self, row):
        """KPI card: compact name like mockup (Vehicle-03)."""
        short = row.get('short') or ''
        if short.lower().startswith('vehicle-'):
            return short.split('(')[0].strip()
        return short

    @api.model
    def _get_company_dashboard(self, res_id=None):
        if res_id:
            dash = self.browse(res_id).exists()
            if dash:
                return dash
        dash = self.search([('company_id', '=', self.env.company.id)], limit=1)
        if not dash:
            dash = self.create({
                'name': _('Maintenance RUL & TOBM'),
                'company_id': self.env.company.id,
            })
        return dash

    def _filters_payload(self):
        self.ensure_one()
        if self.category_id:
            category_label = self.category_id.name
        elif self.fleet_vehicle_scope:
            category_label = _('Fleet / vehicle equipment')
        else:
            category_label = _('All equipment categories')
        days = self.analysis_period_days or 30
        return {
            'category_id': self.category_id.id if self.category_id else False,
            'category_label': category_label,
            'period_days': days,
            'period_label': _('Last %(n)s days') % {'n': days},
            'fleet_vehicle_scope': bool(self.fleet_vehicle_scope),
        }

    def _build_kpis_payload(self, stats):
        """KPI cards always reflect the current filter scope (all equipment in view)."""
        self.ensure_one()
        nc = stats.get('next_critical')
        if nc:
            nc_name = self._next_critical_display_name(nc)
            nc_days = nc['days_to_threshold']
            if nc.get('past_threshold'):
                nc_desc = _('Past failure threshold')
            elif nc_days:
                nc_desc = _('Closest to threshold - %(days)s days') % {'days': nc_days}
            else:
                nc_desc = _('Threshold date unavailable')
        else:
            nc_name = '—'
            nc_desc = _('No equipment in scope')

        return {
            'avg_rul_display': f'{stats["avg_rul"]}%',
            'failure_threshold_display': f'{int(self.FAILURE_LIFE_PCT)}%',
            'tobm_count': stats['tobm_count'],
            'next_critical_name': nc_name,
            'next_critical_desc': nc_desc,
        }

    def _categories_for_company(self):
        """Categories that have at least one equipment record in this company."""
        self.ensure_one()
        used = self.env['maintenance.equipment'].search([
            ('company_id', '=', self.company_id.id),
            ('category_id', '!=', False),
        ]).mapped('category_id')
        return used.sorted(key=lambda c: (c.name or '').lower())

    def _meta_line(self, stats, filters):
        self.ensure_one()
        return _(
            '%(req)s request(s) · %(eq)s equipment · %(scope)s · updates when you save maintenance data'
        ) % {
            'req': stats['req_count'],
            'eq': stats['equipment_count'],
            'scope': filters['category_label'],
        }

    def _build_dashboard_payload(self):
        self.ensure_one()
        stats = self._rul_stats()
        filters = self._filters_payload()
        kpis = self._build_kpis_payload(stats)

        detail = stats.get('detail_row')
        detail_eq_id = detail['equipment'].id if detail else False
        detail_title = detail['short'] if detail else _('No equipment selected')
        detail_label = detail['short'] if detail else _('Select equipment')

        categories = [
            {'id': cat.id, 'name': cat.name}
            for cat in self._categories_for_company()
        ]
        period_options = [
            {'days': d, 'label': _('Last %(n)s days') % {'n': d}}
            for d in self._period_options()
        ]
        equipment_options = [
            {'id': row['equipment'].id, 'name': row['short']}
            for row in (stats.get('rows') or [])
        ]

        phases = self._phase_bar_payload()
        chart = self._build_chart_payload(detail, stats)

        return {
            'record_id': self.id,
            'build': RUL_TOBM_EMBED_VERSION,
            'phases': phases,
            'chart': chart,
            'meta': self._meta_line(stats, filters),
            'type_counts': stats.get('type_counts') or {},
            'filters': filters,
            'categories': categories,
            'period_options': period_options,
            'kpis': kpis,
            'detail': {
                'title': detail_title,
                'subtitle': self._detail_subtitle_text(),
                'equipment_id': detail_eq_id,
                'equipment_label': detail_label,
            },
            'equipment_options': equipment_options,
        }

    @api.model
    def get_dashboard_payload(self, res_id=None):
        dash = self._get_company_dashboard(res_id=res_id)
        return dash._build_dashboard_payload()

    def _sync_detail_equipment_to_scope(self, stats):
        """Keep timeline equipment inside the active category/period scope."""
        self.ensure_one()
        rows = stats.get('rows') or []
        row_ids = {r['equipment'].id for r in rows}
        if self.equipment_id and self.equipment_id.id in row_ids:
            return stats
        new_eq = rows[0]['equipment'].id if rows else False
        if (self.equipment_id.id if self.equipment_id else False) != new_eq:
            self.write({'equipment_id': new_eq})
            return self._rul_stats()
        return stats

    def apply_dashboard_filters(self, filter_vals):
        self.ensure_one()
        filter_vals = dict(filter_vals or {})
        filter_vals.pop('kpi_mode', None)  # legacy client param — KPIs are always scope-wide
        allowed = {'category_id', 'analysis_period_days', 'equipment_id', 'fleet_vehicle_scope'}
        vals = {k: v for k, v in filter_vals.items() if k in allowed}
        if 'category_id' in vals and vals['category_id']:
            vals['fleet_vehicle_scope'] = False
        if 'analysis_period_days' in vals:
            days = int(vals['analysis_period_days'] or 30)
            vals['analysis_period_days'] = max(1, min(days, 365))
        if vals:
            self.write(vals)
        stats = self._rul_stats()
        row_ids = {r['equipment'].id for r in (stats.get('rows') or [])}
        eq_id = vals.get('equipment_id') if 'equipment_id' in vals else self.equipment_id.id
        if not eq_id or eq_id not in row_ids:
            stats = self._sync_detail_equipment_to_scope(stats)
        return self._build_dashboard_payload()

    @api.model
    def action_open_rul_tobm_dashboard_client(self, res_id=None):
        return {
            'type': 'ir.actions.client',
            'tag': 'maintenance_rul_tobm_dashboard',
            'name': _('RUL & TOBM Report'),
            'params': {'res_id': res_id},
        }

    @api.model
    def _rul_tobm_client_action(self):
        return self.env.ref(
            'maintenance.maintenance_rul_tobm_dashboard_action',
            raise_if_not_found=False,
        )

    @api.model
    def _recreate_legacy_rul_action_326(self):
        """Legacy id 326: point to current RUL act_window if the old client action was removed."""
        existing = self.env['ir.actions.actions'].sudo().browse(326).exists()
        main = self.env.ref(
            'maintenance.maintenance_rul_tobm_dashboard_action',
            raise_if_not_found=False,
        )
        if main and main._name == 'ir.actions.act_window' and existing and existing.id == 326:
            return
        if existing:
            return
        dash = self.env.ref(
            'maintenance.maintenance_rul_tobm_dashboard_main',
            raise_if_not_found=False,
        )
        res_id = dash.id if dash else False
        params_store = repr({'res_id': res_id}).encode('utf-8')
        name_json = json.dumps({'en_US': _('RUL & TOBM Report')})
        uid = self.env.uid or 1
        try:
            self.env.cr.execute(
                """
                INSERT INTO ir_act_client (
                    id, name, type, tag, target, binding_type, binding_view_types,
                    context, params_store, path, create_uid, write_uid,
                    create_date, write_date
                ) VALUES (
                    326, %s::jsonb, 'ir.actions.client', 'maintenance_rul_tobm_dashboard',
                    'current', 'action', 'list,form', %s, %s, 'rul-tobm-legacy',
                    %s, %s, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC'
                )
                """,
                (name_json, '{}', params_store, uid, uid),
            )
            self.env.cr.execute(
                "SELECT setval(pg_get_serial_sequence('ir_actions', 'id'), "
                "(SELECT MAX(id) FROM ir_actions))"
            )
            self.env.registry.clear_cache()
            _logger.info('Recreated RUL client action id=326 for legacy URLs.')
        except Exception as err:
            _logger.warning('Could not recreate RUL action 326: %s', err)

    @api.model
    def _repair_stale_rul_user_home_actions(self, client_action):
        """Point users home action away from deleted action ids."""
        if not client_action:
            return
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        stale = Users.search([('action_id', '!=', False)]).filtered(
            lambda u: (
                not u.action_id.exists()
                or (
                    u.action_id._name == 'ir.actions.act_window'
                    and getattr(u.action_id, 'res_model', None) == 'maintenance.rul.tobm.dashboard'
                )
            )
        )
        if stale:
            stale.write({'action_id': client_action.id})

    @api.model
    def fix_rul_tobm_dashboard_defaults(self):
        """Reset RUL dashboard filters to company-wide scope (skip when plant demo is loaded)."""
        if self.env['maintenance.equipment'].sudo().search_count([
            ('serial_no', 'ilike', 'SN-DEMO%'),
        ]):
            return True
        dash = self.env.ref(
            'maintenance.maintenance_rul_tobm_dashboard_main',
            raise_if_not_found=False,
        )
        if dash:
            vals = {
                'fleet_vehicle_scope': False,
                'category_id': False,
                'analysis_period_days': 365,
            }
            if dash.equipment_id and not dash.equipment_id.exists():
                vals['equipment_id'] = False
            dash.sudo().write(vals)

    @api.model
    def migrate_rul_tobm_action_to_client(self):
        """Legacy hook — ensure Owl client action is registered."""
        return self.setup_rul_tobm_dashboard_ui()

    @api.model
    def migrate_rul_tobm_action_to_url(self):
        """Legacy hook — migrate URL actions to client action."""
        return self.setup_rul_tobm_dashboard_ui()

    @api.model
    def _migrate_rul_action_to_act_window(self):
        """Drop legacy client action xmlid so act_window can reuse the same external id."""
        ClientAction = self.env['ir.actions.client'].sudo()
        ClientAction.search([('tag', '=', 'maintenance_rul_tobm_dashboard')]).unlink()
        imd = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'maintenance'),
            ('name', '=', 'maintenance_rul_tobm_dashboard_action'),
        ], limit=1)
        if imd and imd.model == 'ir.actions.client':
            ClientAction.browse(imd.res_id).exists() and ClientAction.browse(imd.res_id).unlink()
            imd.unlink()

    @api.model
    def setup_rul_tobm_dashboard_ui(self):
        """Register RUL & TOBM act_window (purple menu bar), reporting menu, legacy paths."""
        self.fix_rul_tobm_dashboard_defaults()
        dash = self.env.ref(
            'maintenance.maintenance_rul_tobm_dashboard_main',
            raise_if_not_found=False,
        )
        res_id = dash.id if dash else False

        ActWindow = self.env['ir.actions.act_window'].sudo()
        ClientAction = self.env['ir.actions.client'].sudo()
        action = self.env.ref(
            'maintenance.maintenance_rul_tobm_dashboard_action',
            raise_if_not_found=False,
        )
        view = self.env.ref(
            'maintenance.maintenance_rul_tobm_dashboard_form_view',
            raise_if_not_found=False,
        )
        ClientAction.search([
            ('tag', '=', 'maintenance_rul_tobm_dashboard'),
        ]).unlink()
        ClientAction.search([('path', '=', 'rul-tobm')]).unlink()

        action_vals = {
            'name': _('RUL & TOBM Report'),
            'res_model': 'maintenance.rul.tobm.dashboard',
            'view_mode': 'form',
            'view_id': view.id if view else False,
            'res_id': res_id,
            'target': 'current',
            'context': {'create': False, 'delete': False},
        }
        imd = self.env['ir.model.data'].sudo().search([
            ('module', '=', 'maintenance'),
            ('name', '=', 'maintenance_rul_tobm_dashboard_action'),
        ], limit=1)
        if action and action._name == 'ir.actions.act_window':
            action.sudo().write(action_vals)
        else:
            if action:
                action.sudo().unlink()
            new_action = ActWindow.create(action_vals)
            if imd:
                imd.write({'model': 'ir.actions.act_window', 'res_id': new_action.id})
            else:
                self.env['ir.model.data'].sudo().create({
                    'name': 'maintenance_rul_tobm_dashboard_action',
                    'module': 'maintenance',
                    'model': 'ir.actions.act_window',
                    'res_id': new_action.id,
                    'noupdate': True,
                })
            action = new_action

        self.env['ir.actions.act_url'].sudo().search([
            ('url', 'ilike', 'rul_tobm'),
        ]).unlink()

        Menu = self.env['ir.ui.menu'].sudo()
        menu = self.env.ref('maintenance.menu_m_reports_rul_tobm', raise_if_not_found=False)
        binding = f'{action._name},{action.id}'
        if menu:
            menu.write({'action': binding, 'active': True})
        else:
            reports = self.env.ref('maintenance.menu_m_reports', raise_if_not_found=False)
            if reports:
                menu = Menu.create({
                    'name': _('RUL & TOBM'),
                    'parent_id': reports.id,
                    'action': binding,
                    'sequence': 2,
                })
                self.env['ir.model.data'].sudo().create({
                    'name': 'menu_m_reports_rul_tobm',
                    'module': 'maintenance',
                    'model': 'ir.ui.menu',
                    'res_id': menu.id,
                    'noupdate': True,
                })

        path_redirect = self.env.ref(
            'maintenance.maintenance_rul_tobm_path_redirect',
            raise_if_not_found=False,
        )
        if path_redirect and path_redirect._name == 'ir.actions.act_url':
            path_redirect.sudo().unlink()

        self._recreate_legacy_rul_action_326()
        self._repair_stale_rul_user_home_actions(action)
        self.env.registry.clear_cache()
        _logger.info('RUL & TOBM dashboard UI registered.')
        return True

    @api.model
    def remove_rul_tobm_from_odoo(self):
        """Remove RUL & TOBM menus, actions, routes, and user home entries."""
        teams_action = self.env.ref(
            'maintenance.maintenance_dashboard_action',
            raise_if_not_found=False,
        )
        teams_binding = (
            f'{teams_action._name},{teams_action.id}' if teams_action else False
        )
        for menu_xmlid in (
            'menu_m_dashboard_rul_tobm',
            'menu_m_reports_rul_tobm',
            'menu_m_workflow_rul_tobm',
        ):
            menu = self.env.ref(f'maintenance.{menu_xmlid}', raise_if_not_found=False)
            if menu:
                menu.sudo().unlink()
        dash_menu = self.env.ref('maintenance.menu_m_dashboard', raise_if_not_found=False)
        if dash_menu and teams_binding:
            dash_menu.sudo().write({'action': teams_binding})

        Users = self.env['res.users'].sudo().with_context(active_test=False)
        dashboard_action = self.env.ref(
            'maintenance.maintenance_rul_tobm_dashboard_action',
            raise_if_not_found=False,
        )
        path_redirect = self.env.ref(
            'maintenance.maintenance_rul_tobm_path_redirect',
            raise_if_not_found=False,
        )
        url_actions = self.env['ir.actions.act_url'].sudo().search([
            ('url', 'ilike', 'rul_tobm'),
        ])
        if path_redirect:
            url_actions = url_actions.filtered(lambda a: a.id != path_redirect.id)
        client_actions = self.env['ir.actions.client'].sudo().search([
            '|',
            ('path', '=', 'rul-tobm'),
            ('tag', 'in', (
                'maintenance_rul_tobm_dashboard',
                'maintenance_rul_tobm_redirect',
                'maintenance_rul_tobm_embed',
            )),
        ])
        action_ids = []
        if dashboard_action:
            action_ids.append(dashboard_action.id)
        action_ids.extend(url_actions.ids)
        action_ids.extend(client_actions.ids)
        if action_ids:
            Users.search([('action_id', 'in', action_ids)]).write(
                {'action_id': teams_action.id if teams_action else False}
            )
        if dashboard_action:
            self.env[dashboard_action._name].sudo().browse(dashboard_action.id).exists().unlink()
        url_actions.unlink()
        client_actions.unlink()

        self.env['ir.actions.act_window'].sudo().search([
            ('res_model', '=', 'maintenance.rul.tobm.dashboard'),
        ]).unlink()
        self.env['ir.ui.view'].sudo().search([
            ('model', '=', 'maintenance.rul.tobm.dashboard'),
            ('type', '=', 'form'),
        ]).unlink()

        self.env.cr.execute(
            """
            DELETE FROM ir_act_client
             WHERE tag IN (
                   'maintenance_rul_tobm_dashboard',
                   'maintenance_rul_tobm_redirect',
                   'maintenance_rul_tobm_embed'
               )
                OR path = 'rul-tobm'
            """
        )
        self.env.cr.execute(
            """
            DELETE FROM ir_act_url
             WHERE url ILIKE '%rul_tobm%'
               AND (path IS NULL OR path != 'rul-tobm')
            """
        )
        self.ensure_rul_tobm_redirect_action()
        self.restore_maintenance_app()
        self.env.registry.clear_cache()
        _logger.info('RUL & TOBM report removed from Odoo.')

    @api.model
    def restore_maintenance_app(self):
        """Restore Maintenance home action and activate the full menu tree."""
        teams_action = self.env.ref(
            'maintenance.maintenance_dashboard_action',
            raise_if_not_found=False,
        )
        if not teams_action:
            _logger.warning('maintenance_dashboard_action missing — cannot restore app home.')
            return False

        binding = f'{teams_action._name},{teams_action.id}'
        Users = self.env['res.users'].sudo().with_context(active_test=False)
        bad_action_ids = self.env['ir.actions.act_url'].sudo().search([
            ('url', 'ilike', 'rul_tobm'),
        ]).ids
        redirect = self.env.ref(
            'maintenance.maintenance_rul_tobm_path_redirect',
            raise_if_not_found=False,
        )
        if redirect:
            bad_action_ids.append(redirect.id)
        for user in Users.search([('action_id', 'in', bad_action_ids)]):
            user.write({'action_id': teams_action.id})

        root = self.env.ref('maintenance.menu_maintenance_title', raise_if_not_found=False)
        if not root:
            _logger.warning('menu_maintenance_title missing — upgrade Maintenance module first.')
            return False

        Menu = self.env['ir.ui.menu'].sudo()
        maintenance_menus = Menu.search([('id', 'child_of', root.id)])
        maintenance_menus.write({'active': True})

        plant_menu_xmlids = (
            'menu_m_dashboard',
            'menu_m_dashboard_teams',
            'menu_m_operations',
            'menu_m_workflow_timeline',
            'menu_m_request_form',
            'menu_m_request_calendar',
            'menu_m_work_orders',
            'menu_m_planning_root',
            'menu_m_planning',
            'menu_m_inventory_spares',
            'menu_m_manpower_assignment',
            'menu_m_analysis_root',
            'menu_m_rca_mom',
            'menu_m_plant_rca',
            'menu_m_agile_rca',
            'menu_m_why_rca',
            'menu_m_capa_rca',
            'maintenance_no_go_reporting',
            'menu_m_reports',
            'menu_m_reports_analytics',
            'menu_m_reports_rul_tobm',
            'maintenance_request_reporting',
            'menu_equipment_form',
            'menu_maintenance_configuration',
            'menu_maintenance_teams',
            'menu_maintenance_cat',
            'menu_maintenance_stage_configuration',
        )
        missing = []
        for menu_xmlid in plant_menu_xmlids:
            menu = self.env.ref(f'maintenance.{menu_xmlid}', raise_if_not_found=False)
            if menu:
                menu.sudo().write({'active': True})
            else:
                missing.append(menu_xmlid)
        if missing:
            _logger.warning(
                'Maintenance menus missing (module upgrade incomplete): %s',
                ', '.join(missing),
            )

        dash_menu = self.env.ref('maintenance.menu_m_dashboard', raise_if_not_found=False)
        plant_app = self.env.ref('maintenance.maintenance_plant_app_action', raise_if_not_found=False)
        if dash_menu:
            if plant_app:
                dash_menu.sudo().write({
                    'action': f'{plant_app._name},{plant_app.id}',
                    'name': 'Dashboard',
                })
            else:
                dash_menu.sudo().write({'action': binding})

        extra_dash = self.env.ref('maintenance.menu_m_dashboard_plant_app', raise_if_not_found=False)
        if extra_dash:
            extra_dash.sudo().write({'active': False})

        from odoo.addons.maintenance.hooks import apply_plant_navbar_menu_order
        apply_plant_navbar_menu_order(self.env)

        # Only repair broken actions on Maintenance menus (never all Odoo menus).
        for menu in maintenance_menus.filtered('action'):
            action_ref = menu.action
            model_name = action_ref._name
            if model_name not in self.env:
                continue
            if not self.env[model_name].sudo().browse(action_ref.id).exists():
                _logger.warning(
                    'Maintenance menu %s (%s) has a missing action %s,%s',
                    menu.display_name, menu.id, model_name, action_ref.id,
                )

        self.env.registry.clear_cache()
        _logger.info('Maintenance app home and menus restored (%s menus).', len(maintenance_menus))
        return True

    @api.model
    def ensure_rul_tobm_redirect_action(self):
        """Legacy hook — client action path rul-tobm replaces URL redirect."""
        return self.setup_rul_tobm_dashboard_ui()

    @api.model
    def ensure_rul_tobm_path_action(self):
        return self.ensure_rul_tobm_redirect_action()

    @api.model
    def ensure_rul_tobm_legacy_redirect(self):
        return self.ensure_rul_tobm_redirect_action()

    @api.model
    def fix_rul_tobm_menu_actions(self):
        """Keep hook name for upgrades — ensure reporting menu points to dashboard."""
        return self.setup_rul_tobm_dashboard_ui()

    @api.model
    def apply_plant_navbar_menu_order(self):
        """Force Dashboard → Equipment → Operations → Planning → Analysis → Reporting → Configuration."""
        from odoo.addons.maintenance.hooks import apply_plant_navbar_menu_order
        apply_plant_navbar_menu_order(self.env)
        return True

    @api.onchange('category_id', 'fleet_vehicle_scope')
    def _onchange_rul_scope(self):
        for dash in self:
            if not dash.equipment_id:
                continue
            if dash.category_id and dash.equipment_id.category_id != dash.category_id:
                dash.equipment_id = False
            elif dash.fleet_vehicle_scope and dash.equipment_id.category_id:
                cat_name = (dash.equipment_id.category_id.name or '').lower()
                eq_name = (dash.equipment_id.name or '').lower()
                fleet_tokens = ('vehicle', 'fleet', 'forklift')
                if not any(t in cat_name or t in eq_name for t in fleet_tokens):
                    dash.equipment_id = False

    @api.model
    def _notify_rul_refresh(self, companies):
        if 'bus.bus' not in self.env:
            return
        companies = companies.filtered(lambda c: c) if companies else self.env['res.company'].browse()
        for company in companies:
            channel = f'maintenance_rul_tobm_{company.id}'
            self.env['bus.bus']._sendone(
                channel,
                'maintenance/rul_tobm_refresh',
                {'company_id': company.id},
            )

    @api.model
    def _invalidate_rul_for_companies(self, companies):
        companies = companies.filtered(lambda c: c) if companies else self.env['res.company'].browse()
        if not companies:
            return
        dashboards = self.sudo().search([('company_id', 'in', companies.ids)])
        if dashboards:
            dashboards.invalidate_recordset()
        self._notify_rul_refresh(companies)

    @api.model
    def _equipment_cycle_start(self, equipment):
        """Last completed PM resets the lifecycle; otherwise in-service date."""
        today = fields.Date.context_today(equipment)
        from .maintenance_types import is_preventive_type

        done_pm = equipment.maintenance_ids.filtered(
            lambda r: not r.archive
            and is_preventive_type(r.maintenance_type)
            and r.stage_id
            and r.stage_id.done
        ).sorted(key=lambda r: (r.close_date or r.request_date or today), reverse=True)
        if done_pm:
            last = done_pm[0]
            return last.close_date or last.request_date or equipment.effective_date
        return equipment.effective_date

    @api.model
    def _equipment_cycle_days(self, equipment):
        return int(equipment.expected_mtbf or equipment.mtbf or 0) or 90

    @api.model
    def _life_consumed_for_equipment(self, equipment, period_from_date=None):
        """Plant maintenance: PM resets cycle, time + correctives + risk drive life used."""
        if (equipment.life_consumed_percent or 0.0) > 0:
            return min(100.0, float(equipment.life_consumed_percent))
        today = fields.Date.context_today(equipment)
        cycle_start = self._equipment_cycle_start(equipment)
        cycle_days = self._equipment_cycle_days(equipment)
        if cycle_start:
            elapsed = max((today - cycle_start).days, 0)
            life = min(99.0, (elapsed / max(cycle_days, 1)) * 100.0)
        else:
            life = 0.0
        if period_from_date:
            from .maintenance_types import is_corrective_type, is_predictive_type

            correctives = equipment.maintenance_ids.filtered(
                lambda r: not r.archive
                and is_corrective_type(r.maintenance_type)
                and r.request_date
                and r.request_date >= period_from_date
                and r.stage_id
                and r.stage_id.done
            )
            predictives = equipment.maintenance_ids.filtered(
                lambda r: not r.archive
                and is_predictive_type(r.maintenance_type)
                and r.request_date
                and r.request_date >= period_from_date
            )
            life = min(99.0, life + len(correctives) * 6.0 + len(predictives) * 3.0)
        reqs = equipment.maintenance_ids.filtered(
            lambda r: not r.archive
            and r.request_date
            and (not period_from_date or r.request_date >= period_from_date)
        )
        max_risk = max([float(r.failure_risk_percent or 0.0) for r in reqs] or [0.0])
        return min(99.0, max(life, max_risk))

    def _rul_for_life(self, life_used):
        return max(0.0, 100.0 - min(100.0, life_used))

    def _days_to_threshold(self, equipment, life_used):
        today = fields.Date.context_today(self)
        if life_used >= self.FAILURE_LIFE_PCT:
            if equipment.estimated_next_failure:
                return max((equipment.estimated_next_failure - today).days, 0)
            return 0
        if equipment.expected_mtbf:
            return max(1, int((self.FAILURE_LIFE_PCT - life_used) / 100.0 * equipment.expected_mtbf))
        return 0

    def _dashboard_request_domain(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        days = max(min(self.analysis_period_days or 30, 365), 1)
        from_date = today - timedelta(days=days)
        domain = [
            ('archive', '=', False),
            ('company_id', '=', self.company_id.id),
            ('request_date', '>=', from_date),
        ]
        if self.category_id:
            domain.append(('equipment_id.category_id', '=', self.category_id.id))
        if self.fleet_vehicle_scope:
            fleet_or = [
                '|', '|', '|',
                ('equipment_id.category_id.name', 'ilike', 'vehicle'),
                ('equipment_id.category_id.name', 'ilike', 'fleet'),
                ('equipment_id.name', 'ilike', 'vehicle'),
                ('equipment_id.name', 'ilike', 'forklift'),
            ]
            domain = expression.AND([domain, fleet_or])
        return domain

    def _detail_subtitle_text(self):
        return _('RUL trend with TOBM maintenance window at %s lifecycle consumption') % (
            f'{int(self.FAILURE_LIFE_PCT)}%',
        )

    def _get_dashboard_requests(self):
        self.ensure_one()
        domain = self._dashboard_request_domain()
        return self.env['maintenance.request'].search(domain, order='request_date desc')

    def _get_scope_equipments(self, reqs):
        self.ensure_one()
        if self.category_id:
            equipments = self.env['maintenance.equipment'].search([
                ('company_id', '=', self.company_id.id),
                ('category_id', '=', self.category_id.id),
            ])
        elif self.fleet_vehicle_scope:
            fleet_cat = self.env.ref(
                'maintenance.equipment_category_fleet_vehicles',
                raise_if_not_found=False,
            )
            domain = [('company_id', '=', self.company_id.id)]
            if fleet_cat:
                domain.append(('category_id', '=', fleet_cat.id))
            else:
                domain.extend([
                    '|', '|', '|',
                    ('category_id.name', 'ilike', 'vehicle'),
                    ('category_id.name', 'ilike', 'fleet'),
                    ('name', 'ilike', 'vehicle'),
                    ('name', 'ilike', 'forklift'),
                ])
            equipments = self.env['maintenance.equipment'].search(domain)
        else:
            equipments = self.env['maintenance.equipment'].search([
                ('company_id', '=', self.company_id.id),
            ])
            equipments |= reqs.mapped('equipment_id').filtered(lambda e: e)
        if self.equipment_id:
            equipments = self.equipment_id | equipments
        return equipments

    def _rul_stats(self):
        self.ensure_one()
        reqs = self._get_dashboard_requests()
        days = max(min(self.analysis_period_days or 30, 365), 1)
        from_date = fields.Date.context_today(self) - timedelta(days=days)
        equipments = self._get_scope_equipments(reqs)
        rows = []
        for eq in equipments:
            life = self._life_consumed_for_equipment(eq, period_from_date=from_date)
            rul = self._rul_for_life(life)
            short = self._equipment_short_label(eq)
            rows.append({
                'equipment': eq,
                'name': eq.display_name,
                'short': short,
                'life_used': round(life, 1),
                'rul': round(rul, 1),
                'in_tobm': self.TOBM_WINDOW_START <= life < self.FAILURE_LIFE_PCT,
                'past_threshold': life >= self.FAILURE_LIFE_PCT,
                'days_to_threshold': self._days_to_threshold(eq, life),
            })
        rows.sort(key=lambda r: r['life_used'], reverse=True)

        rul_vals = [r['rul'] for r in rows]
        avg_rul = round(sum(rul_vals) / len(rul_vals), 0) if rul_vals else 0.0
        tobm_count = len([r for r in rows if r['in_tobm']])

        next_critical = None
        below = [r for r in rows if r['life_used'] < self.FAILURE_LIFE_PCT]
        if below:
            next_critical = min(
                below,
                key=lambda r: (r['days_to_threshold'] if r['days_to_threshold'] is not None else 9999, -r['life_used']),
            )
        elif rows:
            next_critical = max(rows, key=lambda r: r['life_used'])

        row_ids = {r['equipment'].id for r in rows}
        detail_eq = self.equipment_id
        if detail_eq and detail_eq.id not in row_ids:
            detail_eq = False
        if not detail_eq and rows:
            detail_eq = rows[0]['equipment']
        detail_row = next((r for r in rows if r['equipment'] == detail_eq), rows[0] if rows else None)

        from .maintenance_types import classify_maintenance_type

        scoped_reqs = reqs.filtered(lambda r: r.equipment_id and r.equipment_id.id in row_ids)

        type_counts = {'corrective': 0, 'preventive': 0, 'predictive': 0, 'other': 0}
        for req in scoped_reqs:
            kind = classify_maintenance_type(req.maintenance_type)
            type_counts[kind] = type_counts.get(kind, 0) + 1

        stats = {
            'from_date': from_date,
            'period_days': days,
            'req_count': len(scoped_reqs),
            'type_counts': type_counts,
            'equipment_count': len(rows),
            'rows': rows,
            'avg_rul': int(avg_rul),
            'tobm_count': tobm_count,
            'next_critical': next_critical,
            'detail_row': detail_row,
            'detail_equipment': detail_eq,
        }
        return stats

    @api.model
    def action_open_maintenance_teams(self):
        """Open Maintenance Teams kanban from the dashboard header."""
        action = self.env.ref('maintenance.maintenance_dashboard_action', raise_if_not_found=False)
        if not action:
            return {'type': 'ir.actions.act_window_close'}
        return action.read()[0]

    def _phase_bar_payload(self):
        """Lifecycle segment widths matching the reference mockup (75/10/15)."""
        rul_w = int(self.FAILURE_LIFE_PCT)
        tobm_w = int(self.MAINTENANCE_START - self.FAILURE_LIFE_PCT)
        maint_w = max(0, 100 - int(self.MAINTENANCE_START))
        return {
            'rul_width': rul_w,
            'tobm_width': tobm_w,
            'maint_width': maint_w,
            'rul_label': _('RUL (%(pct)s%%)') % {'pct': rul_w},
            'tobm_label': _('TOBM Window (%(pct)s%%)') % {'pct': tobm_w},
            'maint_label': _('Maintenance (%(pct)s%%)') % {'pct': maint_w},
            'failure_rul_label': _('Failure Threshold (%(pct)s%%)') % {'pct': int(self.FAILURE_RUL_PCT)},
        }

    def _lifecycle_curve_points(self, detail_row, stats):
        """Build equipment-specific curve from filtered history, fallback to template."""
        equipment = detail_row.get('equipment') if detail_row else None
        period_from_date = stats.get('from_date') if isinstance(stats, dict) else None
        history_samples = self._lifecycle_curve_from_history(equipment, period_from_date)
        if history_samples:
            points = self._densify_lifecycle_points(history_samples)
            life_used = float((detail_row or {}).get('life_used') or 0.0)
            current_rul = max(0.0, min(100.0, 100.0 - life_used))
            # Anchor the right edge to current life consumption for visible per-equipment differences.
            points[-1] = (100, round(current_rul, 1))
            return points
        return self._lifecycle_curve_template(had_pm_reset=True)

    def _build_chart_payload(self, detail_row, stats):
        """Chart.js dataset + annotation metadata (reference mockup)."""
        points = self._lifecycle_curve_points(detail_row, stats)
        tobm_point_y = round(self._curve_rul_at_progress(
            [(p, r) for p, r in points], self.FAILURE_LIFE_PCT,
        ), 1)
        return {
            'points': [{'x': p, 'y': r} for p, r in points],
            'failure_life_pct': self.FAILURE_LIFE_PCT,
            'failure_rul_pct': self.FAILURE_RUL_PCT,
            'maintenance_start': self.MAINTENANCE_START,
            'tobm_line_x': self.FAILURE_LIFE_PCT,
            'tobm_point_y': tobm_point_y,
            'labels': {
                'tobm': _('75% TOBM Point'),
                'maintenance': _('85% Maintenance Start'),
                'failure': _('Failure Threshold (25%)'),
                'x_axis': _('Lifecycle Progress (%)'),
                'y_axis': _('RUL Remaining (%)'),
            },
        }

    def _lifecycle_curve_template(self, had_pm_reset=False):
        # Reference mockup: near-linear decline to 25% at ~70% progress, then PM recovery.
        anchors = [
            (0, 100), (10, 90), (20, 80), (30, 70), (40, 60),
            (50, 50), (60, 40), (70, 25),
            (75, 29), (80, 34), (85, 40), (90, 58), (94, 78), (100, 100),
        ]
        points = []
        for progress in range(0, 101, 2):
            rul = self._curve_rul_at_progress(anchors, progress)
            if had_pm_reset and progress >= 85:
                rul = min(100.0, rul)
            points.append((progress, round(rul, 1)))
        return points

    def _densify_lifecycle_points(self, samples):
        """Interpolate sparse PM/history samples to a full 0–100% lifecycle curve."""
        if not samples:
            return self._lifecycle_curve_template()
        anchors = sorted(samples, key=lambda s: s[0])
        return [
            (progress, round(self._curve_rul_at_progress(anchors, progress), 1))
            for progress in range(0, 101, 2)
        ]

    def _curve_rul_at_progress(self, points, progress):
        if not points:
            return 100.0
        progress = max(0.0, min(100.0, float(progress)))
        if progress <= points[0][0]:
            return points[0][1]
        if progress >= points[-1][0]:
            return points[-1][1]
        for i in range(1, len(points)):
            p0, r0 = points[i - 1]
            p1, r1 = points[i]
            if progress <= p1:
                span = max(p1 - p0, 1e-6)
                ratio = (progress - p0) / span
                return r0 + ratio * (r1 - r0)
        return points[-1][1]

    def _lifecycle_curve_from_history(self, equipment, period_from_date):
        """Build request-driven lifecycle curve in the active filter window."""
        if not equipment:
            return None
        today = fields.Date.context_today(self)
        period_start = period_from_date or (today - timedelta(days=max(self.analysis_period_days or 30, 1)))
        window_days = max((today - period_start).days, 1)
        cycle_days = max(self._equipment_cycle_days(equipment), 30)

        # Limit history to current filter window so graph reacts to filter/date changes.
        history = equipment.maintenance_ids.filtered(
            lambda r: not r.archive and r.request_date and r.request_date >= period_start and r.request_date <= today
        ).sorted(key=lambda r: r.request_date)

        current_life = min(99.0, max(0.0, self._life_consumed_for_equipment(equipment, period_start)))
        start_life_guess = max(0.0, min(99.0, current_life - (window_days / cycle_days) * 55.0))
        life = start_life_guess

        def progress_for(date_value):
            elapsed = max((date_value - period_start).days, 0)
            return min(100.0, (elapsed / window_days) * 100.0)

        samples = [(0.0, max(0.0, 100.0 - life))]
        from .maintenance_types import is_corrective_type, is_preventive_type, is_predictive_type

        prev_date = period_start
        for req in history:
            elapsed_days = max((req.request_date - prev_date).days, 0)
            life = min(99.0, max(0.0, life + (elapsed_days / cycle_days) * 100.0 * 0.8))

            risk = float(req.failure_risk_percent or 0.0)
            if is_preventive_type(req.maintenance_type) and req.stage_id and req.stage_id.done:
                life = max(0.0, life - 18.0)
            elif is_predictive_type(req.maintenance_type):
                if req.stage_id and req.stage_id.done:
                    life = max(0.0, life - max(7.0, min(12.0, risk * 0.2)))
                else:
                    bump = max(4.0, risk * 0.25)
                    life = min(99.0, life + bump)
            elif is_corrective_type(req.maintenance_type):
                bump = max(6.0, risk * 0.4)
                life = min(99.0, life + bump)
            progress = progress_for(req.request_date)
            samples.append((progress, max(0.0, 100.0 - life)))
            prev_date = req.request_date

        elapsed_days = max((today - prev_date).days, 0)
        life = min(99.0, max(0.0, life + (elapsed_days / cycle_days) * 100.0 * 0.8))
        samples.append((100.0, max(0.0, 100.0 - life)))

        # Align simulated end-point with computed current life so KPI + graph stay consistent.
        simulated_end_life = max(0.0, 100.0 - samples[-1][1])
        offset = current_life - simulated_end_life
        aligned = []
        for progress, rul in samples:
            life_at_point = min(99.0, max(0.0, (100.0 - rul) + offset))
            aligned.append((progress, max(0.0, 100.0 - life_at_point)))

        if len(aligned) < 2:
            return None
        aligned.sort(key=lambda s: s[0])
        return aligned

    def _svg_curve_path(self, points, x_px, y_px):
        if not points:
            return ''
        parts = [f'M {x_px(points[0][0]):.1f},{y_px(points[0][1]):.1f}']
        for idx in range(1, len(points)):
            p0, r0 = points[idx - 1]
            p1, r1 = points[idx]
            cx = (x_px(p0) + x_px(p1)) / 2.0
            parts.append(
                f'Q {cx:.1f},{y_px(r0):.1f} {x_px(p1):.1f},{y_px(r1):.1f}'
            )
        return ' '.join(parts)

    def _render_lifecycle_svg(self, detail_row, stats):
        """Reference mockup lifecycle chart (decline → TOBM → maintenance → recovery)."""
        points = self._lifecycle_curve_points(detail_row, stats)
        w, h, ml, mr, mt, mb = 920, 380, 72, 24, 20, 56
        cw, ch = w - ml - mr, h - mt - mb

        def x_px(pct):
            return ml + (pct / 100.0) * cw

        def y_px(rul):
            return mt + (1.0 - rul / 100.0) * ch

        curve_path = self._svg_curve_path(points, x_px, y_px)
        thresh_y = y_px(self.FAILURE_RUL_PCT)
        # Orange marker at curve nadir (~70%); shaded bands from 75% and 85%
        nadir_progress = min(points, key=lambda p: p[1])[0]
        nadir_rul = self._curve_rul_at_progress(points, nadir_progress)
        tobm_line_x = x_px(nadir_progress)
        tobm_shade_x = x_px(int(self.FAILURE_LIFE_PCT))
        maint_x = x_px(int(self.MAINTENANCE_START))
        mark_x, mark_y = x_px(nadir_progress), y_px(nadir_rul)

        y_ticks = [0, 25, 50, 75, 100]
        x_ticks = list(range(0, 101, 10))

        y_grid = ''.join(
            f'<line x1="{ml}" y1="{y_px(t):.1f}" x2="{w - mr}" y2="{y_px(t):.1f}" '
            f'stroke="#e8edf3" stroke-width="1"/>'
            for t in y_ticks
        )
        x_grid = ''.join(
            f'<line x1="{x_px(t):.1f}" y1="{mt}" x2="{x_px(t):.1f}" y2="{h - mb}" '
            f'stroke="#e8edf3" stroke-width="1"/>'
            for t in x_ticks
        )
        grid = y_grid + x_grid
        y_labels = ''.join(
            f'<text x="{ml - 6}" y="{y_px(t) + 4:.1f}" text-anchor="end" '
            f'font-size="10" fill="#64748b">{t}%</text>'
            for t in y_ticks
        )
        x_labels = ''.join(
            f'<text x="{x_px(t):.1f}" y="{h - mb + 14}" text-anchor="middle" '
            f'font-size="10" fill="#64748b">{t}%</text>'
            for t in x_ticks
        )
        curve_dots = ''.join(
            f'<circle cx="{x_px(p):.1f}" cy="{y_px(r):.1f}" r="4" '
            f'fill="#2563eb" stroke="#fff" stroke-width="1.5"/>'
            for p, r in points
            if p % 10 == 0
        )

        return (
            f'<svg class="o_maint_rul_chart_svg" viewBox="0 0 {w} {h}" '
            f'preserveAspectRatio="xMidYMid meet" role="img" '
            f'aria-label="{escape(_("RUL lifecycle chart"))}">'
            f'<rect x="{ml}" y="{mt}" width="{cw}" height="{ch}" fill="#fafbfd" rx="4"/>'
            f'{grid}{y_labels}'
            f'<rect x="{tobm_shade_x:.1f}" y="{mt}" width="{maint_x - tobm_shade_x:.1f}" '
            f'height="{ch}" fill="#fff7ed" opacity="0.92"/>'
            f'<rect x="{maint_x:.1f}" y="{mt}" width="{w - mr - maint_x:.1f}" height="{ch}" '
            f'fill="#eff6ff" opacity="0.95"/>'
            f'<line x1="{ml}" y1="{thresh_y:.1f}" x2="{w - mr}" y2="{thresh_y:.1f}" '
            f'stroke="#ef4444" stroke-width="1.5" stroke-dasharray="6 4"/>'
            f'<text x="{ml + 6}" y="{thresh_y - 8:.1f}" text-anchor="start" font-size="10" '
            f'fill="#dc2626" font-weight="700">{escape(_("Failure Threshold (25%)"))}</text>'
            f'<line x1="{tobm_line_x:.1f}" y1="{mt}" x2="{tobm_line_x:.1f}" y2="{h - mb}" '
            f'stroke="#f97316" stroke-width="1.5" stroke-dasharray="5 4"/>'
            f'<text x="{mark_x:.1f}" y="{mark_y - 14:.1f}" text-anchor="middle" font-size="10" '
            f'fill="#c2410c" font-weight="700">{escape(_("75% TOBM Point"))}</text>'
            f'<line x1="{maint_x:.1f}" y1="{mt}" x2="{maint_x:.1f}" y2="{h - mb}" '
            f'stroke="#2563eb" stroke-width="1.5" stroke-dasharray="5 4"/>'
            f'<text x="{maint_x + 6:.1f}" y="{mt + 16}" font-size="10" fill="#1d4ed8" '
            f'font-weight="700">{escape(_("85% Maintenance Start"))}</text>'
            f'<path d="{curve_path}" fill="none" stroke="#2563eb" stroke-width="2.5" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f'{curve_dots}'
            f'<circle cx="{mark_x:.1f}" cy="{mark_y:.1f}" r="7" fill="#f97316" '
            f'stroke="#fff" stroke-width="2"/>'
            f'{x_labels}'
            f'<text x="{ml + cw / 2:.1f}" y="{h - 8}" text-anchor="middle" font-size="11" '
            f'fill="#475569" font-weight="600">{escape(_("Lifecycle Progress (%)"))}</text>'
            f'<text x="{ml / 2:.1f}" y="{mt + ch / 2:.1f}" transform="rotate(-90 {ml / 2:.1f} {mt + ch / 2:.1f})" '
            f'text-anchor="middle" font-size="11" fill="#475569" font-weight="600">'
            f'{escape(_("RUL Remaining (%)"))}</text>'
            '</svg>'
        )

    def _render_equipment_selector(self, stats, detail_row):
        rows = stats.get('rows') or []
        if not rows:
            return ''
        current_id = detail_row['equipment'].id if detail_row else False
        current_label = detail_row['short'] if detail_row else _('Select equipment')
        options = []
        for row in rows:
            eq_id = row['equipment'].id
            active = ' is-active' if eq_id == current_id else ''
            options.append(
                f'<a href="#" role="button" class="o_maint_rul_eq_option{active}" '
                f'data-rul-equipment-id="{eq_id}">'
                f'<i class="fa fa-truck"></i> {escape(row["short"])}</a>'
            )
        return (
            '<<D>>class="o_maint_rul_eq_select"<<DG>>'
            f'<a href="#" role="button" class="o_maint_rul_eq_select_btn">'
            f'<i class="fa fa-truck"></i> {escape(current_label)}'
            f'<i class="fa fa-caret-down"></i></a>'
            f'<<D>>class="o_maint_rul_eq_menu"<<DG>>{"".join(options)}<</DG>>'
            '<</DG>>'
        )

    def _render_rul_tobm_full_page(self, body_html):
        """Standalone reference mockup — full HTML page, no Odoo web client."""
        page_script = """
(function () {
    function closeMenus() {
        document.querySelectorAll('.o_maint_rul_eq_select.is-open').forEach(function (el) {
            el.classList.remove('is-open');
        });
    }
    document.addEventListener('click', function (ev) {
        var opt = ev.target.closest('[data-rul-equipment-id]');
        if (opt) {
            ev.preventDefault();
            var eqId = parseInt(opt.getAttribute('data-rul-equipment-id'), 10);
            if (eqId) {
                var url = new URL(window.location.href);
                url.searchParams.set('equipment_id', String(eqId));
                window.location.assign(url.toString());
            }
            closeMenus();
            return;
        }
        var btn = ev.target.closest('.o_maint_rul_eq_select_btn');
        if (btn) {
            ev.preventDefault();
            var sel = btn.closest('.o_maint_rul_eq_select');
            if (!sel) return;
            var wasOpen = sel.classList.contains('is-open');
            closeMenus();
            if (!wasOpen) sel.classList.add('is-open');
            return;
        }
        if (!ev.target.closest('.o_maint_rul_eq_select')) closeMenus();
    });
})();
"""
        css_href = f'/maintenance/rul_tobm/styles?v={RUL_TOBM_EMBED_VERSION}'
        return (
            '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{escape(_("Maintenance RUL & TOBM Report"))}</title>'
            '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/4.7.0/css/font-awesome.min.css" '
            'integrity="sha512-SfTiTlX6kk+qitfevl/7LibUOeJWlt9rbyDn74zVDhR/zakH63oFCZ0TnIcTlW6VICzoPbSSeZ" '
            'crossorigin="anonymous" referrerpolicy="no-referrer"/>'
            f'<link rel="stylesheet" href="{css_href}"/>'
            f'<style>{RUL_TOBM_EMBED_CSS}</style></head>'
            '<body class="o_maint_rul_standalone_body">'
            f'{body_html}'
            f'<script>{page_script}</script></body></html>'
        )

    def _render_kpi_card(self, css_mod, label, value, desc, icon):
        return (
            f'<<D>>class="o_maint_rul_kpi o_maint_rul_kpi--{css_mod}"<<DG>>'
            '<<D>>class="o_maint_rul_kpi_inner"<<DG>>'
            '<<D>>class="o_maint_rul_kpi_text"<<DG>>'
            f'<<D>>class="o_maint_rul_kpi_label"<<DG>>{escape(label)}<</DG>>'
            f'<<D>>class="o_maint_rul_kpi_value"<<DG>>{escape(value)}<</DG>>'
            f'<<D>>class="o_maint_rul_kpi_desc"<<DG>>{escape(desc)}<</DG>>'
            '<</DG>>'
            f'<<D>>class="o_maint_rul_kpi_icon"<<DG>><i class="fa {icon}"></i><</DG>>'
            '<</DG>>'
            '<</DG>>'
        )

    def _render_rul_tobm_dashboard_body(self, stats):
        self.ensure_one()
        filters = self._filters_payload()
        period_label = filters['period_label']
        scope_label = filters['category_label']
        meta = _(
            '%(req)s request(s) • %(eq)s equipment • updates when you save maintenance data'
        ) % {'req': stats['req_count'], 'eq': stats['equipment_count']}

        nc = stats.get('next_critical')
        if nc:
            nc_name = self._next_critical_display_name(nc)
            nc_days = nc['days_to_threshold']
            if nc.get('past_threshold'):
                nc_desc = _('Past failure threshold')
            elif nc_days:
                nc_desc = _('Closest to threshold - %(days)s days') % {'days': nc_days}
            else:
                nc_desc = _('Threshold date unavailable')
        else:
            nc_name = '—'
            nc_desc = _('No equipment in scope')

        detail = stats.get('detail_row')
        detail_title = detail['short'] if detail else _('No equipment selected')
        detail_sub = self._detail_subtitle_text()
        eq_selector = self._render_equipment_selector(stats, detail)

        phases = self._phase_bar_payload()
        phase_stack = (
            '<<D>>class="o_maint_rul_phase_stack"<<DG>>'
            f'<<D>>class="o_maint_rul_phase_seg o_maint_rul_phase_seg--rul" '
            f'style="width:{phases["rul_width"]}%;"<<DG>>'
            f'{escape(phases["rul_label"])}<</DG>>'
            f'<<D>>class="o_maint_rul_phase_seg o_maint_rul_phase_seg--tobm" '
            f'style="width:{phases["tobm_width"]}%;"<<DG>>'
            f'{escape(phases["tobm_label"])}<</DG>>'
            f'<<D>>class="o_maint_rul_phase_seg o_maint_rul_phase_seg--maint" '
            f'style="width:{phases["maint_width"]}%;"<<DG>>'
            f'{escape(phases["maint_label"])}<</DG>>'
            '<</DG>>'
        )

        chart_svg = self._render_lifecycle_svg(detail, stats)
        legend = (
            '<<D>>class="o_maint_rul_legend"<<DG>>'
            '<span><i class="o_maint_rul_legend_line o_maint_rul_legend_line--curve"></i>'
            f'{escape(_("RUL Remaining (%)"))}</span>'
            '<span><i class="o_maint_rul_legend_dot o_maint_rul_legend_dot--rul"></i>'
            f'{escape(phases["rul_label"])}</span>'
            '<span><i class="o_maint_rul_legend_dot o_maint_rul_legend_dot--tobm"></i>'
            f'{escape(phases["tobm_label"])}</span>'
            '<span><i class="o_maint_rul_legend_dot o_maint_rul_legend_dot--maint"></i>'
            f'{escape(phases["maint_label"])}</span>'
            '<span><i class="o_maint_rul_legend_line o_maint_rul_legend_line--fail"></i>'
            f'{escape(phases["failure_rul_label"])}</span>'
            '<</DG>>'
        )

        kpis = (
            '<<D>>class="o_maint_rul_kpis"<<DG>>'
            + self._render_kpi_card(
                'rul', _('Average RUL'), f'{stats["avg_rul"]}%',
                _('Remaining useful life in scope'), 'fa-line-chart',
            )
            + self._render_kpi_card(
                'thresh', _('Failure threshold'), f'{int(self.FAILURE_LIFE_PCT)}%',
                _('Life consumed before high risk'), 'fa-exclamation-triangle',
            )
            + self._render_kpi_card(
                'tobm', _('TOBM opportunities'), str(stats['tobm_count']),
                _('Machines in opportunity window'), 'fa-crosshairs',
            )
            + self._render_kpi_card(
                'critical', _('Next critical'), nc_name, nc_desc, 'fa-bullhorn',
            )
            + '<</DG>>'
        )

        html = (
            '<<D>>class="o_maint_rul_dashboard o_maint_rul_viewport"<<DG>>'
            '<<D>>class="o_maint_rul_header"<<DG>>'
            '<span class="o_maint_rul_pill o_maint_rul_pill--badge o_maint_rul_live_corner">'
            '<span class="o_maint_rul_live_dot"></span> LIVE</span>'
            '<<D>>class="o_maint_rul_header_text"<<DG>>'
            f'<h1>{escape(_("Maintenance RUL & TOBM Report"))}</h1>'
            f'<p>{escape(_("Remaining useful life and opportunity-based maintenance by equipment"))}</p>'
            f'<p class="o_maint_rul_meta">{escape(meta)}</p>'
            '<</DG>>'
            '<<D>>class="o_maint_rul_pills"<<DG>>'
            f'<span class="o_maint_rul_pill"><i class="fa fa-filter"></i> '
            f'{escape(scope_label)} <i class="fa fa-caret-down"></i></span>'
            f'<span class="o_maint_rul_pill"><i class="fa fa-calendar"></i> '
            f'{escape(period_label)} <i class="fa fa-caret-down"></i></span>'
            '<span class="o_maint_rul_pill o_maint_rul_pill--scope">'
            '<span class="o_maint_rul_scope_dot"></span> '
            f'{escape(_("Live: all matching requests"))}</span>'
            '<</DG>>'
            '<</DG>>'
            f'{kpis}'
            '<<D>>class="o_maint_rul_card o_maint_rul_card--detail"<<DG>>'
            '<<D>>class="o_maint_rul_detail_head"<<DG>>'
            '<<D>>class="o_maint_rul_detail_titles"<<DG>>'
            f'<h2>{escape(detail_title)} — {escape(_("RUL, TOBM & Maintenance Timeline"))}</h2>'
            f'<p>{escape(detail_sub)}</p>'
            '<</DG>>'
            f'{eq_selector}'
            '<</DG>>'
            f'{phase_stack}'
            f'<<D>>class="o_maint_rul_chart_wrap"<<DG>>{chart_svg}<</DG>>'
            f'{legend}'
            '<</DG>>'
            '<</DG>>'
        )
        html = html.replace('<<D>>', '<div ').replace('<<DG>>', '>').replace('<</DG>>', '</div>')
        return Markup(
            f'<div class="o_maint_rul_root" data-rul-build="{RUL_TOBM_EMBED_VERSION}">'
            f'{html}</div>'
        )

    def _render_rul_tobm_html(self, stats):
        """Legacy name — dashboard body markup only."""
        return self._render_rul_tobm_dashboard_body(stats)

    @api.depends(
        'company_id',
        'analysis_period_days',
        'category_id',
        'fleet_vehicle_scope',
        'equipment_id',
    )
    def _compute_rul_tobm_dashboard(self):
        for dash in self:
            # Rendered via HTTP iframe (see controllers/rul_tobm_dashboard.py).
            dash.dashboard_html = Markup('')
