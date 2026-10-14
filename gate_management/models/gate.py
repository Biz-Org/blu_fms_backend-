from odoo import fields, models


class GateZone(models.Model):
    _name = "gate.zone"
    _description = "Perimeter Zone"

    name = fields.Char(required=True)
    zone_type = fields.Selection(
        [
            ("gate", "Gate"),
            ("parking", "Parking"),
            ("loading", "Loading Dock"),
            ("office", "Office"),
            ("blocked", "Blocked"),
        ],
        default="gate",
    )
    coordinates = fields.Char()
    status = fields.Selection([("open", "Open"), ("restricted", "Restricted"), ("closed", "Closed")], default="open")
    gate_ids = fields.One2many("gate.gate", "zone_id")


class GateGate(models.Model):
    _name = "gate.gate"
    _description = "Gate"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char()
    location = fields.Char()
    direction = fields.Selection([("in", "Entry"), ("out", "Exit"), ("both", "Both")], default="both")
    status = fields.Selection([("open", "Open"), ("closed", "Closed"), ("hold", "Hold")], default="open")
    zone_id = fields.Many2one("gate.zone", ondelete="set null")
    latitude = fields.Float()
    longitude = fields.Float()
    camera_label = fields.Char()
    barrier_device_id = fields.Many2one("gate.device", ondelete="set null")


class GateEntry(models.Model):
    _name = "gate.entry"
    _description = "Gate Entry Event"
    _order = "timestamp desc"

    name = fields.Char(default="Entry")
    gate_id = fields.Many2one("gate.gate", required=True, ondelete="cascade")
    visitor_id = fields.Many2one("gate.visitor", ondelete="set null")
    employee_id = fields.Many2one("hr.employee", ondelete="set null")
    vehicle_id = fields.Many2one("fleet.vehicle", ondelete="set null")
    timestamp = fields.Datetime(default=fields.Datetime.now)
    direction = fields.Selection([("in", "Entry"), ("out", "Exit")], default="in")
    result = fields.Selection([("granted", "Granted"), ("rejected", "Rejected"), ("hold", "Hold")], default="granted")
    note = fields.Char()


class GateVehicleMovement(models.Model):
    _name = "gate.vehicle.movement"
    _description = "Vehicle Gate Movement"
    _order = "timestamp desc"

    vehicle_id = fields.Many2one("fleet.vehicle", ondelete="set null")
    gate_id = fields.Many2one("gate.gate", ondelete="set null")
    movement_type = fields.Selection([("entry", "Entry"), ("exit", "Exit")], required=True, default="entry")
    timestamp = fields.Datetime(default=fields.Datetime.now)
    plate_number = fields.Char()
    driver_id = fields.Many2one("res.partner", ondelete="set null")
    verification_status = fields.Selection(
        [("verified", "Verified"), ("pending", "Pending"), ("failed", "Failed"), ("hold", "Hold")],
        default="pending",
    )
    ai_confidence = fields.Float()


class GateVisitEvent(models.Model):
    _name = "gate.visit.event"
    _description = "Visit Timeline Event"
    _order = "timestamp, id"

    visitor_id = fields.Many2one("gate.visitor", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    event_type = fields.Char()
    timestamp = fields.Datetime(default=fields.Datetime.now)
    note = fields.Char()
