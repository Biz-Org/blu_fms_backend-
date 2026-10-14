from odoo import fields, models


class GateDevice(models.Model):
    _name = "gate.device"
    _description = "Gate Hardware Device"

    name = fields.Char(required=True)
    device_type = fields.Selection(
        [
            ("anpr", "ANPR Camera"),
            ("face", "Face Recognition Camera"),
            ("rfid", "RFID Reader"),
            ("barrier", "Boom Barrier"),
            ("sensor", "Sensor"),
            ("gateway", "IoT Gateway"),
        ],
        default="anpr",
    )
    device_code = fields.Char()
    gate_id = fields.Many2one("gate.gate", ondelete="set null")
    ip_address = fields.Char()
    status = fields.Selection([("online", "Online"), ("offline", "Offline"), ("degraded", "Degraded")], default="online")
    last_seen = fields.Datetime(default=fields.Datetime.now)
    health_percentage = fields.Integer(default=98)
    firmware_version = fields.Char(default="1.4.2")


class GateDeviceEvent(models.Model):
    _name = "gate.device.event"
    _description = "Device Event"
    _order = "timestamp desc"

    device_id = fields.Many2one("gate.device", required=True, ondelete="cascade")
    name = fields.Char(required=True)
    timestamp = fields.Datetime(default=fields.Datetime.now)
    status = fields.Char()


class GateNetworkNode(models.Model):
    _name = "gate.network.node"
    _description = "Network Node"

    name = fields.Char(required=True)
    node_type = fields.Selection(
        [
            ("odoo", "Odoo Server"),
            ("gateway", "IoT Gateway"),
            ("controller", "Gate Controller"),
            ("camera", "Camera"),
            ("rfid", "RFID Reader"),
            ("barrier", "Barrier"),
        ],
        default="camera",
    )
    device_id = fields.Many2one("gate.device", ondelete="set null")
    ip_address = fields.Char()
    status = fields.Selection([("online", "Online"), ("offline", "Offline")], default="online")


class GateNetworkConnection(models.Model):
    _name = "gate.network.connection"
    _description = "Network Connection"

    name = fields.Char()
    source_node_id = fields.Many2one("gate.network.node", required=True, ondelete="cascade")
    target_node_id = fields.Many2one("gate.network.node", required=True, ondelete="cascade")
    connection_type = fields.Selection([("lan", "LAN"), ("wifi", "Wi-Fi"), ("api", "API")], default="lan")
