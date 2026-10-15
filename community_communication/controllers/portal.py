# -*- coding: utf-8 -*-

from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.web import Home as PortalHome
from odoo.addons.web.controllers.utils import ensure_db
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.service import security
from odoo.tools.misc import hmac


def _cc_user_is_webclient_resident(uid):
    if not uid:
        return False
    user = request.env["res.users"].sudo().browse(uid)
    return bool(user.exists() and user._cc_is_community_webclient_resident())


class CommunityWebHome(PortalHome):
    """Residents enter the same OWL webclient without Internal User rights."""

    def _login_redirect(self, uid, redirect=None):
        if _cc_user_is_webclient_resident(uid) and (
            not redirect or redirect == "/my" or redirect.startswith("/my?")
        ):
            redirect = "/odoo"
        return super()._login_redirect(uid, redirect=redirect)

    @http.route()
    def index(self, *args, **kw):
        if request.session.uid and _cc_user_is_webclient_resident(request.session.uid):
            return request.redirect_query("/odoo", query=request.params)
        return super().index(*args, **kw)

    @http.route()
    def web_client(self, s_action=None, **kw):
        if request.session.uid and _cc_user_is_webclient_resident(request.session.uid):
            return self._cc_render_webclient(**kw)
        return super().web_client(s_action, **kw)

    @http.route()
    def login_successful_external_user(self, **kwargs):
        if request.session.uid and _cc_user_is_webclient_resident(request.session.uid):
            return request.redirect("/odoo")
        return super().login_successful_external_user(**kwargs)

    def _cc_render_webclient(self, **kw):
        ensure_db()
        if not request.session.uid:
            return request.redirect_query(
                "/web/login",
                query={"redirect": request.httprequest.full_path},
                code=303,
            )
        if kw.get("redirect"):
            return request.redirect(kw.get("redirect"), 303)
        if not security.check_session(request.session, request.env, request):
            raise http.SessionExpiredException("Session expired")

        request.session.touch()
        request.update_env(user=request.session.uid)
        try:
            if request.env.user:
                request.env.user._on_webclient_bootstrap()
            context = request.env["ir.http"].webclient_rendering_context()
            hmac_payload = request.env.user._session_token_get_values()
            session_info = context.get("session_info")
            session_info["browser_cache_secret"] = hmac(
                request.env(su=True), "browser_cache_key", hmac_payload
            )
            response = request.render("web.webclient_bootstrap", qcontext=context)
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Cache-Control"] = "no-store"
            return response
        except AccessError:
            return request.redirect("/web/login?error=access")


class CommunityResidentRedirect(http.Controller):
    """Bookmarks and portal home open the shared Community OWL app."""

    @http.route(
        ["/my/community", "/my/community/<path:rest>"],
        type="http",
        auth="user",
    )
    def community_app(self, rest=None, **kwargs):
        return request.redirect("/odoo")

    @http.route("/community", type="http", auth="user")
    def community_entry(self, **kwargs):
        return request.redirect("/odoo")


class CommunityPortalHome(CustomerPortal):
    @http.route(["/my", "/my/home"], type="http", auth="user", website=True)
    def home(self, **kw):
        if request.env.user._cc_is_community_webclient_resident():
            return request.redirect("/odoo")
        return super().home(**kw)
