import uuid

from odoo import api, fields, models


class GateAccessPass(models.Model):
    _name = "gate.access.pass"
    _description = "QR Access Pass"
    _order = "id desc"

    name = fields.Char(required=True, default="Access Pass")
    visitor_id = fields.Many2one("gate.visitor", ondelete="cascade")
    vehicle_id = fields.Many2one("fleet.vehicle", ondelete="set null")
    gate_id = fields.Many2one("gate.gate", ondelete="set null")
    host_id = fields.Many2one(related="visitor_id.host_id", store=True)
    qr_token = fields.Char(copy=False)
    valid_from = fields.Datetime(default=fields.Datetime.now)
    valid_until = fields.Datetime()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("active", "Active"),
            ("used", "Used"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.qr_token:
                rec.qr_token = uuid.uuid4().hex[:12].upper()
            if not rec.name or rec.name == "Access Pass":
                rec.name = f"PASS-{rec.id:04d}"
        return records


class GateVisitorRequest(models.Model):
    _name = "gate.visitor.request"
    _description = "Visitor Access Request"
    _order = "id desc"

    name = fields.Char(default="Request")
    visitor_id = fields.Many2one("gate.visitor", required=True, ondelete="cascade")
    host_employee_id = fields.Many2one("hr.employee", ondelete="set null")
    requested_gate_id = fields.Many2one("gate.gate", ondelete="set null")
    requested_date = fields.Datetime(default=fields.Datetime.now)
    purpose = fields.Char()
    priority = fields.Selection([("normal", "Normal"), ("urgent", "Urgent")], default="normal")
    security_level = fields.Selection([("standard", "Standard"), ("high", "High")], default="standard")
    state = fields.Selection(
        [
            ("requested", "Requested"),
            ("host", "Host Approval"),
            ("security", "Security Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="requested",
    )
    approved_by = fields.Many2one("res.users")
    approved_date = fields.Datetime()
    rejected_reason = fields.Char()


class GateAccessPolicy(models.Model):
    _name = "gate.access.policy"
    _description = "Access Policy"

    name = fields.Char(required=True)
    time_from = fields.Char(default="08:00")
    time_to = fields.Char(default="20:00")
    days = fields.Char(default="Mon-Fri")
    zone_id = fields.Many2one("gate.zone")
    gate_ids = fields.Many2many("gate.gate")


class GateEmployeeAccess(models.Model):
    _name = "gate.employee.access"
    _description = "Employee Gate Access"

    employee_id = fields.Many2one("hr.employee", required=True, ondelete="cascade")
    policy_id = fields.Many2one("gate.access.policy", ondelete="set null")
    gate_id = fields.Many2one("gate.gate", ondelete="cascade")
    time_from = fields.Char(default="08:00")
    time_to = fields.Char(default="20:00")
    days = fields.Char(default="Mon-Fri")
    state = fields.Selection([("active", "Active"), ("pending", "Pending"), ("blocked", "Blocked")], default="active")
