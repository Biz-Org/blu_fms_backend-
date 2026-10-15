# -*- coding: utf-8 -*-

from odoo import models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class CommunityCommunicationStateMixin(models.AbstractModel):
    """Enforce lifecycle changes through controlled methods."""

    _name = "community.communication.state.mixin"
    _description = "Controlled state transitions"

    _cc_state_transitions = {}

    def _cc_set_state(self, new_state):
        allowed = self._cc_state_transitions
        for record in self:
            if new_state == record.state:
                continue
            destinations = allowed.get(record.state, set())
            if new_state not in destinations:
                raise UserError(
                    _("Cannot change %(name)s from %(current)s to %(target)s.")
                    % {
                        "name": record.display_name,
                        "current": record.state,
                        "target": new_state,
                    }
                )
        self.write({"state": new_state})
