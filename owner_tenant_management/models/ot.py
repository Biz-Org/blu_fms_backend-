from odoo import api, fields, models


class OtLease(models.Model):
    _name = "ot.lease"
    _description = "Owner Tenant Lease"
    _order = "date_start desc"

    name = fields.Char(required=True)
    unit_id = fields.Many2one("property.unit", ondelete="set null")
    tenant_id = fields.Many2one("res.partner", ondelete="set null")
    owner_id = fields.Many2one("res.partner", ondelete="set null")
    date_start = fields.Date()
    date_end = fields.Date()
    rent = fields.Float()
    deposit = fields.Float()
    term_months = fields.Integer(default=12)
    status = fields.Selection(
        [("active", "Active"), ("expired", "Expired"), ("renewed", "Renewed"), ("terminated", "Terminated")],
        default="active",
    )
    notice_days = fields.Integer(default=60)
    auto_renew = fields.Boolean()
    payment_day = fields.Char(default="1st of Month")
    late_fee = fields.Char(default="$50 after 5th")
    document_name = fields.Char()
    file_data = fields.Binary()
    proposed_rent = fields.Float()
    proposed_start = fields.Date()
    renewal_state = fields.Selection(
        [("none", "None"), ("awaiting", "Awaiting Response"), ("accepted", "Accepted"), ("declined", "Declined")],
        default="none",
    )
    renewal_note = fields.Text()


class OtPayment(models.Model):
    _name = "ot.payment"
    _description = "Owner Tenant Payment"
    _order = "date desc, id desc"

    name = fields.Char(required=True)
    unit_id = fields.Many2one("property.unit", ondelete="set null")
    tenant_id = fields.Many2one("res.partner", ondelete="set null")
    date = fields.Date(default=fields.Date.today)
    amount = fields.Float()
    method = fields.Char(default="Bank ACH")
    status = fields.Selection(
        [("paid", "Paid"), ("pending", "Pending"), ("failed", "Failed"), ("due", "Due")],
        default="paid",
    )
    description = fields.Char()
    reference = fields.Char()
    receipt_name = fields.Char()
    file_data = fields.Binary()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.reference:
                rec.reference = f"TXN-{rec.id:04d}"
        return records


class OtLedger(models.Model):
    _name = "ot.ledger"
    _description = "Owner Tenant Ledger"
    _order = "date desc, id desc"

    date = fields.Date(default=fields.Date.today)
    line_type = fields.Selection(
        [("rent", "Rent"), ("payment", "Payment"), ("maintenance", "Maintenance"), ("utility", "Utility"), ("opening", "Opening")],
        default="rent",
    )
    description = fields.Char()
    debit = fields.Float()
    credit = fields.Float()
    unit_id = fields.Many2one("property.unit", ondelete="set null")


class OtMaintenance(models.Model):
    _name = "ot.maintenance"
    _description = "Owner Tenant Maintenance"
    _order = "id desc"

    name = fields.Char(required=True)
    code = fields.Char()
    unit_id = fields.Many2one("property.unit", ondelete="set null")
    category = fields.Char()
    priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("emergency", "Emergency")],
        default="medium",
    )
    state = fields.Selection(
        [("open", "Open"), ("progress", "In Progress"), ("scheduled", "Scheduled"), ("done", "Completed")],
        default="open",
    )
    description = fields.Text()
    access_date = fields.Date()
    access_slot = fields.Char()
    scheduled_date = fields.Date()
    vendor_name = fields.Char()
    vendor_phone = fields.Char()
    notes = fields.Text()
    attachment_name = fields.Char()
    file_data = fields.Binary()
    message_ids = fields.One2many("ot.maint.message", "request_id")

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.code:
                rec.code = f"REQ-{rec.id:04d}"
        return records


class OtMaintMessage(models.Model):
    _name = "ot.maint.message"
    _description = "Maintenance Message"
    _order = "id"

    request_id = fields.Many2one("ot.maintenance", required=True, ondelete="cascade")
    author = fields.Char()
    body = fields.Text()
    mine = fields.Boolean()
    date = fields.Datetime(default=fields.Datetime.now)


class OtDocument(models.Model):
    _name = "ot.document"
    _description = "Owner Tenant Document"
    _order = "id desc"

    name = fields.Char(required=True)
    category = fields.Selection(
        [("lease", "Lease"), ("invoice", "Invoices"), ("maintenance", "Maintenance"), ("property", "Property"), ("notice", "Notices")],
        default="property",
    )
    property_label = fields.Char()
    status = fields.Char(default="Verified")
    date = fields.Date(default=fields.Date.today)
    uploaded_by = fields.Char()
    size_label = fields.Char()
    tags = fields.Char()
    version = fields.Char(default="v1.0")
    file_data = fields.Binary()
    mimetype = fields.Char()
    body_html = fields.Html()


class OtMessage(models.Model):
    _name = "ot.message"
    _description = "Owner Tenant Message"
    _order = "id desc"

    thread = fields.Char(required=True, index=True)
    subject = fields.Char()
    author = fields.Char()
    email = fields.Char()
    body = fields.Text()
    tag = fields.Char()
    date = fields.Datetime(default=fields.Datetime.now)
    mine = fields.Boolean()
    unread = fields.Boolean()
    attachment = fields.Char()
    unit_label = fields.Char()


class OtNotification(models.Model):
    _name = "ot.notification"
    _description = "Owner Tenant Notification"
    _order = "id desc"

    name = fields.Char(required=True)
    body = fields.Text()
    category = fields.Selection(
        [("payments", "Payments"), ("lease", "Lease"), ("maintenance", "Maintenance"), ("documents", "Documents"), ("messages", "Messages")],
        default="lease",
    )
    date = fields.Datetime(default=fields.Datetime.now)
    is_read = fields.Boolean()


class OtPreference(models.Model):
    _name = "ot.preference"
    _description = "Portal Preferences"

    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    phone = fields.Char()
    role = fields.Char(default="Property Manager")
    office_address = fields.Char()
    email_on = fields.Boolean(default=True)
    sms_on = fields.Boolean()
    push_on = fields.Boolean(default=True)
    two_fa = fields.Boolean(default=True)
