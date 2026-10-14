# -*- coding: utf-8 -*-

from odoo.addons.web.controllers.action import Action
from odoo.exceptions import AccessError
from odoo.http import request, route
from odoo.tools.translate import _


RESIDENT_CLIENT_TAGS = {
    "community_communication.action_dashboard",
    "community_communication.action_announcements",
    "community_communication.action_discussions",
    "community_communication.action_polls",
    "community_communication.action_events",
    "community_communication.action_notices",
    "community_communication.action_feedback",
    "community_communication.action_groups",
}


class CommunityAction(Action):
    @route()
    def load(self, action_id, context=None):
        result = super().load(action_id, context=context)
        user = request.env.user
        if user._cc_is_community_webclient_resident() and not _resident_may_load_action(result):
            raise AccessError(_("This action is not available for community residents."))
        return result


def _resident_may_load_action(action):
    if not action:
        return False
    return (
        action.get("type") == "ir.actions.client"
        and action.get("tag") in RESIDENT_CLIENT_TAGS
    )
