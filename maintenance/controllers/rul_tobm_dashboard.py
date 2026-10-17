# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request

from odoo.addons.maintenance.models.rul_tobm_embed_css import (
    RUL_TOBM_EMBED_CSS,
    RUL_TOBM_EMBED_VERSION,
)


class MaintenanceRulTobmDashboardController(http.Controller):
    """HTTP routes for RUL & TOBM dashboard styles and legacy deep links."""

    @http.route('/maintenance/rul_tobm/styles', type='http', auth='user', website=False)
    def rul_tobm_styles(self, **kwargs):
        return request.make_response(
            RUL_TOBM_EMBED_CSS,
            headers=[
                ('Content-Type', 'text/css; charset=utf-8'),
                ('Cache-Control', 'public, max-age=3600'),
            ],
        )

    @http.route(
        '/maintenance/rul_tobm/data/<int:dashboard_id>',
        type='json',
        auth='user',
        website=False,
    )
    def rul_tobm_data(self, dashboard_id, **kwargs):
        dash = request.env['maintenance.rul.tobm.dashboard'].browse(dashboard_id).exists()
        if not dash:
            return {'error': 'not_found'}
        return dash._build_dashboard_payload()

    def _redirect_to_rul_client_action(self, dashboard_id=None):
        """Single redirect to action-{id} (never back to /odoo/rul-tobm — prevents redirect loops)."""
        env = request.env
        dash = env['maintenance.rul.tobm.dashboard']._get_company_dashboard(res_id=dashboard_id)
        action = env.ref(
            'maintenance.maintenance_rul_tobm_dashboard_action',
            raise_if_not_found=False,
        )
        if not action:
            env['maintenance.rul.tobm.dashboard'].setup_rul_tobm_dashboard_ui()
            action = env.ref(
                'maintenance.maintenance_rul_tobm_dashboard_action',
                raise_if_not_found=False,
            )
        if action and action._name in ('ir.actions.act_window', 'ir.actions.client'):
            return request.redirect(f'/odoo/action-{action.id}?res_id={dash.id}')
        return request.redirect('/web')

    @http.route(
        [
            '/odoo/rul-tobm',
            '/odoo/rul-tobm/<int:dashboard_id>',
            '/maintenance/rul_tobm/dashboard/<int:dashboard_id>',
            '/rul-tobm',
            '/rul-tobm/<int:dashboard_id>',
        ],
        type='http',
        auth='user',
        website=False,
    )
    def rul_tobm_dashboard(self, dashboard_id=None, **kwargs):
        """Legacy bookmarks → action-{id} once (fixes ERR_TOO_MANY_REDIRECTS)."""
        return self._redirect_to_rul_client_action(dashboard_id=dashboard_id)
