from datetime import date

from odoo import api, fields, models


RESIDENT_STATUS = [
    ("pending", "Pending"),
    ("verification", "Under Verification"),
    ("active", "Active"),
    ("notice", "Notice Period"),
    ("inactive", "Inactive"),
    ("moved_out", "Moved Out"),
    ("suspended", "Suspended"),
]

ONBOARDING = [
    ("submitted", "Submitted"),
    ("docs", "Docs Uploaded"),
    ("kyc", "KYC"),
    ("review", "Review"),
    ("approved", "Approved"),
    ("rejected", "Rejected"),
]


class ResidentResident(models.Model):
    _name = "resident.resident"
    _description = "Resident"
    _order = "id desc"

    name = fields.Char(compute="_compute_name", store=True)
    code = fields.Char(copy=False)
    partner_id = fields.Many2one("res.partner", ondelete="restrict")
    first_name = fields.Char(required=True)
    last_name = fields.Char(required=True)
    preferred_name = fields.Char()
    dob = fields.Date()
    gender = fields.Selection([("male", "Male"), ("female", "Female"), ("other", "Other")])
    marital_status = fields.Char()
    nationality = fields.Char()
    resident_type = fields.Char(default="Primary Tenant")
    mobile = fields.Char()
    email = fields.Char()
    alt_phone = fields.Char()
    street = fields.Char()
    city = fields.Char()
    state_name = fields.Char()
    zip = fields.Char()
    country = fields.Char()
    unit_id = fields.Many2one("property.unit", ondelete="set null")
    building_id = fields.Many2one("property.building", ondelete="set null")
    floor_id = fields.Many2one("property.floor", ondelete="set null")
    property_id = fields.Many2one(related="unit_id.property_id", store=True)
    move_in_date = fields.Date()
    move_out_date = fields.Date()
    lease_term = fields.Char(default="12 Months")
    id_type = fields.Char()
    id_number = fields.Char()
    status = fields.Selection(RESIDENT_STATUS, default="pending", required=True, index=True)
    onboarding_stage = fields.Selection(ONBOARDING, default="submitted")
    onboarding_progress = fields.Integer(default=15)
    kyc_state = fields.Selection(
        [("pending", "Pending"), ("review", "Under Review"), ("verified", "Verified"), ("rejected", "Rejected"), ("none", "—")],
        default="pending",
    )
    status_reason = fields.Char()
    status_since = fields.Date(default=fields.Date.today)
    household_ids = fields.One2many("resident.household.member", "resident_id")
    emergency_ids = fields.One2many("resident.emergency.contact", "resident_id")
    kyc_ids = fields.One2many("resident.kyc.document", "resident_id")
    move_ids = fields.One2many("resident.move.request", "resident_id")
    history_ids = fields.One2many("resident.status.history", "resident_id")

    @api.depends("first_name", "last_name")
    def _compute_name(self):
        for rec in self:
            rec.name = " ".join(part for part in [rec.first_name, rec.last_name] if part) or "Resident"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.code:
                rec.code = f"RES-{rec.id:04d}"
            if not rec.partner_id:
                rec.partner_id = self.env["res.partner"].create({
                    "name": rec.name,
                    "email": rec.email,
                    "phone": rec.mobile,
                    "street": rec.street,
                    "city": rec.city,
                    "zip": rec.zip,
                })
            self.env["resident.status.history"].create({
                "resident_id": rec.id,
                "activity_type": "created",
                "title": "Resident Created",
                "body": "Initial profile created in the system.",
                "new_status": rec.status,
                "performed_by": "System",
            })
        return records


class ResidentHouseholdMember(models.Model):
    _name = "resident.household.member"
    _description = "Household Member"

    resident_id = fields.Many2one("resident.resident", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    relation = fields.Char()
    dob = fields.Date()
    email = fields.Char()
    phone = fields.Char()
    member_status = fields.Selection(
        [("active", "Active"), ("dependent", "Dependent"), ("guest", "Guest")],
        default="active",
    )
    kyc_state = fields.Char(default="Pending")


class ResidentEmergencyContact(models.Model):
    _name = "resident.emergency.contact"
    _description = "Emergency Contact"

    resident_id = fields.Many2one("resident.resident", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    relation = fields.Char()
    phone = fields.Char()
    email = fields.Char()
    priority = fields.Selection([("primary", "Primary"), ("secondary", "Secondary")], default="primary")


class ResidentKycDocument(models.Model):
    _name = "resident.kyc.document"
    _description = "KYC Document"
    _order = "id desc"

    name = fields.Char(required=True)
    resident_id = fields.Many2one("resident.resident", required=True, ondelete="cascade")
    document_type = fields.Char()
    document_number = fields.Char()
    file_name = fields.Char()
    file_size = fields.Char()
    file_data = fields.Binary()
    mimetype = fields.Char()
    status = fields.Selection(
        [("pending", "Pending"), ("review", "Under Review"), ("verified", "Verified"), ("rejected", "Rejected"), ("expiring", "Expiring Soon")],
        default="pending",
    )
    expiry_date = fields.Date()
    reviewer = fields.Char()
    reject_reason = fields.Char()
    identity_match = fields.Boolean()
    document_readable = fields.Boolean()
    document_valid = fields.Boolean()
    not_expired = fields.Boolean()
    information_match = fields.Boolean()
    submitted = fields.Date(default=fields.Date.today)


class ResidentMoveRequest(models.Model):
    _name = "resident.move.request"
    _description = "Move Request"
    _order = "planned_date"

    name = fields.Char(default="Move")
    move_type = fields.Selection([("in", "Move-In"), ("out", "Move-Out")], required=True, default="in")
    resident_id = fields.Many2one("resident.resident", required=True, ondelete="cascade")
    unit_id = fields.Many2one("property.unit")
    planned_date = fields.Date(default=fields.Date.today)
    request_date = fields.Date(default=fields.Date.today)
    notice_date = fields.Date()
    final_date = fields.Date()
    state = fields.Selection(
        [("pending", "Pending"), ("scheduled", "Scheduled"), ("ready", "Ready"), ("progress", "In Progress"), ("done", "Completed")],
        default="pending",
    )
    approved = fields.Boolean()
    agent = fields.Char()
    checklist_ids = fields.One2many("resident.checklist.item", "request_id")
    readiness_score = fields.Integer(compute="_compute_readiness")
    clearance_name = fields.Char()
    clearance_file = fields.Binary()
    clearance_mimetype = fields.Char()

    @api.depends("checklist_ids.done")
    def _compute_readiness(self):
        for rec in self:
            total = len(rec.checklist_ids) or 1
            rec.readiness_score = int(100 * len(rec.checklist_ids.filtered("done")) / total)


class ResidentChecklistItem(models.Model):
    _name = "resident.checklist.item"
    _description = "Checklist Item"
    _order = "sequence, id"

    request_id = fields.Many2one("resident.move.request", required=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    name = fields.Char(required=True)
    note = fields.Char()
    done = fields.Boolean()


class ResidentStatusHistory(models.Model):
    _name = "resident.status.history"
    _description = "Resident History"
    _order = "date desc, id desc"

    resident_id = fields.Many2one("resident.resident", required=True, ondelete="cascade")
    activity_type = fields.Char()
    title = fields.Char(required=True)
    body = fields.Text()
    date = fields.Datetime(default=fields.Datetime.now)
    old_status = fields.Selection(RESIDENT_STATUS)
    new_status = fields.Selection(RESIDENT_STATUS)
    performed_by = fields.Char()
    reason = fields.Char()
    notes = fields.Text()
    category = fields.Char(default="Lifecycle Management")
    code = fields.Char()


class ResidentCommunication(models.Model):
    _name = "resident.communication"
    _description = "Resident Communication"
    _order = "id desc"

    name = fields.Char(required=True)
    body = fields.Text()
    audience = fields.Char(default="All Residents")
    channel_push = fields.Boolean(default=True)
    channel_email = fields.Boolean(default=True)
    channel_sms = fields.Boolean()
    sent_by = fields.Char()
    date = fields.Datetime(default=fields.Datetime.now)
    state = fields.Selection(
        [("draft", "Draft"), ("scheduled", "Scheduled"), ("delivered", "Delivered"), ("partial", "Partial Fail"), ("failed", "Failed")],
        default="draft",
    )
    attachment_name = fields.Char()
    attachment_file = fields.Binary()
    attachment_mimetype = fields.Char()
    recipient_ids = fields.One2many("resident.comm.recipient", "comm_id")


class ResidentCommRecipient(models.Model):
    _name = "resident.comm.recipient"
    _description = "Communication Recipient"

    comm_id = fields.Many2one("resident.communication", required=True, ondelete="cascade")
    resident_id = fields.Many2one("resident.resident", required=True, ondelete="cascade")
    delivery = fields.Selection([("delivered", "Delivered"), ("failed", "Failed"), ("unread", "Unread")], default="delivered")
    read = fields.Boolean()
    timestamp = fields.Datetime(default=fields.Datetime.now)
