from odoo import fields, models


class GateAIValidation(models.Model):
    _name = "gate.ai.validation"
    _description = "AI Validation"
    _order = "timestamp desc"

    name = fields.Char(default="AI Validation")
    entry_id = fields.Many2one("gate.entry", ondelete="set null")
    visitor_id = fields.Many2one("gate.visitor", ondelete="set null")
    employee_id = fields.Many2one("hr.employee", ondelete="set null")
    vehicle_id = fields.Many2one("fleet.vehicle", ondelete="set null")
    face_confidence = fields.Float()
    vehicle_confidence = fields.Float()
    qr_verified = fields.Boolean()
    blacklist_match = fields.Boolean()
    permit_status = fields.Char()
    decision = fields.Selection([("granted", "Access Granted"), ("denied", "Denied"), ("review", "Review")], default="review")
    confidence = fields.Float()
    timestamp = fields.Datetime(default=fields.Datetime.now)
    evidence_note = fields.Char()


class GateSecurityAlert(models.Model):
    _name = "gate.security.alert"
    _description = "Security Alert"
    _inherit = ["mail.thread"]
    _order = "event_time desc"

    name = fields.Char(required=True)
    alert_type = fields.Selection(
        [
            ("unauthorized", "Unauthorized Entry"),
            ("wrong_vehicle", "Wrong Vehicle"),
            ("tailgating", "Tailgating"),
            ("blacklist", "Blacklisted Vehicle"),
            ("expired", "Expired Visitor"),
            ("emergency", "Emergency"),
        ],
        default="unauthorized",
    )
    severity = fields.Selection([("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")], default="high")
    gate_id = fields.Many2one("gate.gate")
    zone_id = fields.Many2one("gate.zone")
    vehicle_id = fields.Many2one("fleet.vehicle")
    visitor_id = fields.Many2one("gate.visitor")
    employee_id = fields.Many2one("hr.employee")
    confidence = fields.Float()
    camera_id = fields.Many2one("gate.device")
    event_time = fields.Datetime(default=fields.Datetime.now)
    description = fields.Text()
    state = fields.Selection(
        [("new", "New"), ("investigating", "Investigating"), ("resolved", "Resolved"), ("dismissed", "Dismissed")],
        default="new",
        tracking=True,
    )
    assigned_user_id = fields.Many2one("res.users")
    resolved_by = fields.Many2one("res.users")
    resolved_at = fields.Datetime()
    resolution_note = fields.Text()


class GateNotification(models.Model):
    _name = "gate.notification"
    _description = "Security Notification"
    _order = "id desc"

    title = fields.Char(required=True)
    notification_type = fields.Selection(
        [
            ("security", "Security Alerts"),
            ("visitor", "Visitor Updates"),
            ("gate", "Gate Events"),
            ("system", "System Messages"),
        ],
        default="security",
    )
    severity = fields.Selection([("info", "Info"), ("warning", "Warning"), ("critical", "Critical")], default="info")
    message = fields.Text()
    gate_id = fields.Many2one("gate.gate")
    device_id = fields.Many2one("gate.device")
    visitor_id = fields.Many2one("gate.visitor")
    vehicle_id = fields.Many2one("fleet.vehicle")
    is_read = fields.Boolean()
    resolved = fields.Boolean()


class GateAuditLog(models.Model):
    _name = "gate.audit.log"
    _description = "Gate Audit Log"
    _order = "id desc"

    name = fields.Char(required=True)
    user_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    timestamp = fields.Datetime(default=fields.Datetime.now)
    category = fields.Char()
    details = fields.Text()


class GateSecurityConfig(models.Model):
    _name = "gate.security.config"
    _description = "Gate Security Configuration"

    name = fields.Char(default="GateFlow Settings")
    org_name = fields.Char(default="GateFlow Facility")
    face_recognition_threshold = fields.Float(default=0.86)
    license_plate_threshold = fields.Float(default=0.90)
    tailgating_detection = fields.Boolean(default=True)
    unauthorized_access_alert = fields.Boolean(default=True)
    ai_auto_optimization = fields.Boolean()
    notify_email = fields.Boolean(default=True)
    notify_push = fields.Boolean(default=True)
