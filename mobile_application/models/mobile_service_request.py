# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.translate import _

from .constants import SERVICE_REQUEST_STATES, XMLID_GROUP_RESIDENT, XMLID_GROUP_STAFF


class MobileServiceRequest(models.Model):
    _name = "mobile.service.request"
    _description = "Mobile Service Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(readonly=True, copy=False, default="/")
    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, index=True)
    company_id = fields.Many2one(
        "res.company",
        related="user_id.company_id",
        store=True,
        index=True,
    )
    category = fields.Char(required=True)
    description = fields.Text(required=True)
    state = fields.Selection(SERVICE_REQUEST_STATES, default="submitted", required=True, tracking=True, index=True)
    assigned_user_id = fields.Many2one("res.users", string="Assigned To", index=True)
    idempotency_key = fields.Char(index=True)
    external_model = fields.Char(index=True)
    external_id = fields.Integer(index=True)
    attachment_ids = fields.Many2many("ir.attachment", string="Attachments")

    _sql_constraints = [
        (
            "idempotency_uniq",
            "unique(idempotency_key)",
            "This service request was already submitted.",
        ),
    ]
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "/") == "/":
                vals["name"] = self.env["ir.sequence"].next_by_code("mobile.service.request") or "/"
        records = super().create(vals_list)
        for record in records:
            record._notify_user(_("Service request submitted"), _("Your request %s has been submitted.") % record.name)
        return records

    def _notify_user(self, title, message):
        self.env["mobile.application.notification"].sudo().create({
            "user_id": self.user_id.id,
            "title": title,
            "message": message,
            "notification_type": "service",
            "res_model": self._name,
            "res_id": self.id,
            "action_route": "service_requests",
        })

    def _check_resident_access(self):
        if self.env.user.has_group(XMLID_GROUP_STAFF):
            return
        if self.user_id != self.env.user:
            raise AccessError(_("You can only access your own service requests."))

    def action_add_update(self, body):
        self.ensure_one()
        self._check_resident_access()
        if not body:
            raise UserError(_("Update text is required."))
        self.message_post(body=body, message_type="comment", subtype_xmlid="mail.mt_note")
