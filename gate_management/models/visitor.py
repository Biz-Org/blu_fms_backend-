from odoo import api, fields, models


class GateVisitor(models.Model):
    """Community visitor register with Frontdesk-compatible fields."""

    _name = "gate.visitor"
    _description = "Visitor"
    _order = "id desc"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, tracking=True)
    company = fields.Char()
    phone = fields.Char()
    email = fields.Char()
    partner_id = fields.Many2one("res.partner", ondelete="set null")
    host_id = fields.Many2one("hr.employee", string="Host", tracking=True)
    department_id = fields.Many2one(related="host_id.department_id", store=True)
    visit_purpose = fields.Selection(
        [
            ("meeting", "Meeting"),
            ("delivery", "Delivery"),
            ("interview", "Interview"),
            ("maintenance", "Maintenance"),
            ("other", "Other"),
        ],
        default="meeting",
    )
    vehicle_id = fields.Many2one("fleet.vehicle", ondelete="set null")
    plate_number = fields.Char()
    vehicle_type = fields.Char()
    gate_id = fields.Many2one("gate.gate", ondelete="set null")
    planned_date = fields.Datetime(default=fields.Datetime.now)
    check_in = fields.Datetime()
    check_out = fields.Datetime()
    visitor_count = fields.Integer(default=1)
    floor_wing = fields.Char()
    meeting_room = fields.Char()
    security_status = fields.Selection(
        [("clear", "Clear"), ("review", "Under Review"), ("blocked", "Blocked")],
        default="clear",
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("requested", "Requested"),
            ("approved", "Approved"),
            ("checked_in", "Checked In"),
            ("checked_out", "Checked Out"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        tracking=True,
    )
    photo = fields.Binary()
    notes = fields.Text()
    request_ids = fields.One2many("gate.visitor.request", "visitor_id")
    pass_ids = fields.One2many("gate.access.pass", "visitor_id")
    event_ids = fields.One2many("gate.visit.event", "visitor_id")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.partner_id:
                rec.partner_id = self.env["res.partner"].create({
                    "name": rec.name,
                    "email": rec.email,
                    "phone": rec.phone,
                    "company_name": rec.company,
                })
            self.env["gate.visit.event"].create({
                "visitor_id": rec.id,
                "name": "Visitor Created",
                "event_type": "created",
            })
        return records
