# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

from .constants import VISITOR_STATES, XMLID_GROUP_RESIDENT, XMLID_GROUP_SECURITY


class MobileVisitor(models.Model):
    _name = "mobile.visitor"
    _description = "Mobile Visitor Pass Request"
    _inherit = ["mail.thread"]
    _order = "expected_start desc, id desc"

    name = fields.Char(string="Visitor Name", required=True)
    phone = fields.Char()
    purpose = fields.Char(required=True)
    resident_user_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        related="resident_user_id.company_id",
        store=True,
        index=True,
    )
    unit_label = fields.Char()
    building_label = fields.Char()
    notes = fields.Text()
    expected_start = fields.Datetime(required=True, index=True)
    expected_end = fields.Datetime()
    duration_hours = fields.Float()
    state = fields.Selection(VISITOR_STATES, default="submitted", required=True, tracking=True, index=True)
    pass_code = fields.Char(readonly=True, copy=False)
    idempotency_key = fields.Char(index=True)
    external_model = fields.Char(index=True)
    external_id = fields.Integer(index=True)

    _idempotency_uniq = models.Constraint(
        "unique(idempotency_key)",
        "This visitor request was already submitted.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if not record.pass_code:
                record.pass_code = self.env["ir.sequence"].next_by_code("mobile.visitor.pass") or str(record.id)
            record._notify_resident(_("Visitor request submitted"), _("Visitor %s is pending approval.") % record.name)
        return records

    def _notify_resident(self, title, message):
        self.env["mobile.application.notification"].sudo().create({
            "user_id": self.resident_user_id.id,
            "title": title,
            "message": message,
            "notification_type": "visitor",
            "res_model": self._name,
            "res_id": self.id,
            "action_route": "visitors",
        })

    def _notify_security(self, title, message):
        security_users = self.env.ref(XMLID_GROUP_SECURITY).users
        for user in security_users:
            self.env["mobile.application.notification"].sudo().create({
                "user_id": user.id,
                "title": title,
                "message": message,
                "notification_type": "security",
                "res_model": self._name,
                "res_id": self.id,
                "action_route": "visitor_approval",
            })

    def _check_resident_owner(self):
        if self.env.user.has_group(XMLID_GROUP_SECURITY):
            return
        if self.resident_user_id != self.env.user and not self.env.user.has_group(
            "mobile_application.group_mobile_staff"
        ):
            raise AccessError(_("You cannot access this visitor record."))

    def action_approve(self):
        self.ensure_one()
        if self.resident_user_id != self.env.user:
            raise AccessError(_("Only the resident can approve this visitor."))
        if self.state not in ("submitted", "draft"):
            raise UserError(_("This visitor request cannot be approved."))
        self.write({"state": "approved"})
        self._notify_security(_("Visitor approved"), _("Visitor %s approved by resident.") % self.name)

    def action_deny(self):
        self.ensure_one()
        if self.resident_user_id != self.env.user:
            raise AccessError(_("Only the resident can deny this visitor."))
        self.write({"state": "denied"})

    def action_verify(self):
        self.ensure_one()
        if not self.env.user.has_group(XMLID_GROUP_SECURITY):
            raise AccessError(_("Only security can verify visitors."))
        if self.state != "approved":
            raise UserError(_("Visitor must be approved before verification."))
        self.write({"state": "verified"})
        self._notify_resident(_("Visitor verified"), _("Visitor %s has been verified by security.") % self.name)

    def action_check_in(self):
        self.ensure_one()
        if not self.env.user.has_group(XMLID_GROUP_SECURITY):
            raise AccessError(_("Only security can check visitors in."))
        if self.state not in ("approved", "verified"):
            raise UserError(_("Visitor is not ready for check-in."))
        self.write({"state": "checked_in"})
        self._notify_resident(_("Visitor arrived"), _("Visitor %s has checked in.") % self.name)

    def action_check_out(self):
        self.ensure_one()
        if not self.env.user.has_group(XMLID_GROUP_SECURITY):
            raise AccessError(_("Only security can check visitors out."))
        if self.state != "checked_in":
            raise UserError(_("Visitor is not checked in."))
        self.write({"state": "checked_out"})
