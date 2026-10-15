# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.translate import _

from .constants import DEVICE_TYPES, FIRE_ALARM_CONDITIONS


def _m2o(record):
    if not record:
        return False
    return [record.id, record.display_name]


class IntegrationIotDashboard(models.AbstractModel):
    _name = "integration.iot.dashboard"
    _description = "IoT Dashboard Aggregator"

    @api.model
    def get_lookups(self):
        return {
            "properties": [
                {"id": rec.id, "name": rec.name} for rec in self.env["integration.iot.property"].search([])
            ],
            "buildings": [
                {"id": rec.id, "name": rec.name, "property_id": rec.property_id.id}
                for rec in self.env["integration.iot.building"].search([])
            ],
            "areas": [
                {
                    "id": rec.id,
                    "name": rec.name,
                    "building_id": rec.building_id.id,
                    "kind": rec.area_kind,
                }
                for rec in self.env["integration.iot.area"].search([])
            ],
            "integrations": [
                {
                    "id": rec.id,
                    "name": rec.name,
                    "kind": rec.system_kind,
                    "mode": rec.connection_mode,
                    "state": rec.state,
                }
                for rec in self.env["integration.iot.integration"].search([])
            ],
            "devices": [
                {
                    "id": rec.id,
                    "name": rec.name,
                    "type": rec.device_type,
                    "building_id": rec.building_id.id,
                }
                for rec in self.env["integration.iot.device"].search([("archived", "=", False)])
            ],
        }

    @api.model
    def get_dashboard_data(self):
        Device = self.env["integration.iot.device"]
        Alert = self.env["integration.iot.alert"]
        Rule = self.env["integration.iot.automation.rule"]
        Energy = self.env["integration.iot.energy.reading"]
        Log = self.env["integration.iot.log"]
        Sensor = self.env["integration.iot.sensor"]
        active_devices = Device.search([("archived", "=", False)])
        online = active_devices.filtered(lambda d: d.status == "online")
        offline = active_devices.filtered(lambda d: d.status == "offline")
        alerts = Alert.search([("state", "in", ["open", "acknowledged"])], order="priority_rank desc, id desc", limit=8)
        energy_rows = Energy.search([], order="captured_at desc", limit=48)
        current = energy_rows[:1].kwh if energy_rows else 0.0
        trend = [
            {"t": fields.Datetime.to_string(row.captured_at), "kwh": row.kwh}
            for row in reversed(energy_rows[:12])
        ]
        env = {}
        for parameter in ("temperature", "humidity", "air_quality"):
            sensor = Sensor.search([("parameter", "=", parameter), ("active", "=", True)], limit=1)
            env[parameter] = {
                "value": sensor.last_value if sensor else False,
                "unit": sensor.unit if sensor else "",
                "quality": "ok" if sensor and sensor.last_value is not False else "empty",
            }

        def system_status(device_type, extra=None):
            devices = active_devices.filtered(lambda d: d.device_type == device_type)
            if extra:
                devices = devices or extra
            if not devices:
                return {"state": "empty", "label": _("No devices")}
            if any(d.status == "faulty" for d in devices):
                return {"state": "fault", "label": _("Fault")}
            if any(d.status == "offline" for d in devices):
                return {"state": "offline", "label": _("Offline")}
            if any(d.status == "warning" for d in devices):
                return {"state": "warning", "label": _("Warning")}
            return {"state": "ok", "label": _("Normal")}

        bms = self.env["integration.iot.integration"].search([("system_kind", "in", ["bms", "mock"])], limit=1)
        bms_status = {"state": "empty", "label": _("Not configured")}
        if bms:
            if bms.connection_mode == "simulated":
                bms_status = {"state": "ok", "label": _("Simulated")}
            elif bms.state == "connected":
                bms_status = {"state": "ok", "label": _("Ready")}
            elif bms.state == "error":
                bms_status = {"state": "fault", "label": _("Error")}
            else:
                bms_status = {"state": "offline", "label": _("Not connected")}

        fire_devices = active_devices.filtered(lambda d: d.device_type == "fire_alarm")
        fire = system_status("fire_alarm")
        if fire_devices and any(d.fire_alarm_condition == "alarm" for d in fire_devices):
            fire = {"state": "fault", "label": _("Alarm")}

        savings = sum(self.env["integration.iot.energy.opportunity"].search([("state", "=", "applied")]).mapped("applied_kwh"))
        return {
            "kpis": {
                "connected_devices": len(active_devices),
                "offline_devices": len(offline),
                "online_devices": len(online),
                "active_alerts": Alert.search_count([("state", "in", ["open", "acknowledged"])]),
                "automation_rules": Rule.search_count([("active", "=", True)]),
                "energy_usage": current,
                "energy_savings": savings,
            },
            "systems": {
                "lighting": system_status("lighting"),
                "hvac": system_status("hvac"),
                "fire_alarm": fire,
                "environment": system_status("environmental") if active_devices.filtered(lambda d: d.device_type in ("environmental", "temperature")) else {"state": "empty", "label": _("No sensors")},
                "bms": bms_status,
            },
            "environment": env,
            "energy": {
                "current": current,
                "trend": trend,
            },
            "attention": [
                {
                    "id": alert.id,
                    "title": alert.name,
                    "priority": alert.priority,
                    "time": fields.Datetime.to_string(alert.create_date),
                    "location": alert._iot_location_label(),
                }
                for alert in alerts
            ],
            "activity": [
                {
                    "id": log.id,
                    "title": log.name,
                    "kind": log.kind,
                    "time": fields.Datetime.to_string(log.event_time),
                    "simulated": log.simulated,
                }
                for log in Log.search([], limit=8)
            ],
        }

    def _iot_device_payload(self, device):
        return {
            "id": device.id,
            "name": device.name,
            "code": device.code,
            "type": device.device_type,
            "status": device.status,
            "location": device._iot_location_label(),
            "property_id": _m2o(device.property_id),
            "building_id": _m2o(device.building_id),
            "area_id": _m2o(device.area_id),
            "power_state": device.power_state,
            "brightness": device.brightness,
            "hvac_mode": device.hvac_mode,
            "hvac_setpoint": device.hvac_setpoint,
            "fire_alarm_condition": device.fire_alarm_condition,
            "health_score": device.health_score,
            "last_seen": fields.Datetime.to_string(device.last_seen) if device.last_seen else False,
            "control_supported": device.control_supported,
            "integration": _m2o(device.integration_id),
            "active": device.active,
        }

    @api.model
    def get_systems_data(self, tab="lighting", building_id=False):
        domain = [("archived", "=", False)]
        if building_id:
            domain.append(("building_id", "=", int(building_id)))
        Device = self.env["integration.iot.device"]
        if tab == "lighting":
            devices = Device.search(domain + [("device_type", "=", "lighting")])
            schedules = self.env["integration.iot.schedule"].search(
                [("system_kind", "=", "lighting")] + ([("building_id", "=", int(building_id))] if building_id else [])
            )
            return {
                "devices": [self._iot_device_payload(d) for d in devices],
                "schedules": [
                    {
                        "id": rec.id,
                        "name": rec.name,
                        "action": rec.lighting_action,
                        "location": rec._iot_location_label(),
                        "start_time": rec.start_time,
                        "end_time": rec.end_time,
                        "active": rec.active,
                    }
                    for rec in schedules
                ],
                "history": self._iot_history(["lighting_changed"], 10),
            }
        if tab == "hvac":
            devices = Device.search(domain + [("device_type", "=", "hvac")])
            sensors = self.env["integration.iot.sensor"].search(
                [("parameter", "in", ["temperature", "humidity"])]
                + ([("building_id", "=", int(building_id))] if building_id else [])
            )
            return {
                "devices": [self._iot_device_payload(d) for d in devices],
                "environment": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "parameter": s.parameter,
                        "value": s.last_value,
                        "unit": s.unit,
                        "location": s._iot_location_label(),
                    }
                    for s in sensors
                ],
                "history": self._iot_history(["hvac_adjusted"], 10),
            }
        if tab == "fire":
            devices = Device.search(domain + [("device_type", "=", "fire_alarm")])
            events = self.env["integration.iot.alarm.event"].search(
                ([("building_id", "=", int(building_id))] if building_id else []),
                limit=30,
            )
            return {
                "devices": [self._iot_device_payload(d) for d in devices],
                "conditions": FIRE_ALARM_CONDITIONS,
                "events": [
                    {
                        "id": ev.id,
                        "name": ev.name,
                        "condition": ev.condition,
                        "location": ev._iot_location_label(),
                        "time": fields.Datetime.to_string(ev.event_time),
                        "device": _m2o(ev.device_id),
                    }
                    for ev in events
                ],
            }
        sensors = self.env["integration.iot.sensor"].search(
            [("parameter", "in", ["temperature", "humidity", "air_quality", "co2"])]
            + ([("building_id", "=", int(building_id))] if building_id else [])
        )
        return {
            "sensors": [
                {
                    "id": s.id,
                    "name": s.name,
                    "parameter": s.parameter,
                    "value": s.last_value,
                    "unit": s.unit,
                    "min": s.min_threshold,
                    "max": s.max_threshold,
                    "location": s._iot_location_label(),
                    "updated": fields.Datetime.to_string(s.last_reading_at) if s.last_reading_at else False,
                }
                for s in sensors
            ],
            "history": [
                {
                    "id": r.id,
                    "sensor": r.sensor_id.display_name,
                    "parameter": r.parameter,
                    "value": r.value,
                    "quality": r.quality,
                    "time": fields.Datetime.to_string(r.captured_at),
                    "location": r._iot_location_label(),
                }
                for r in self.env["integration.iot.reading"].search(
                    [("parameter", "in", ["temperature", "humidity", "air_quality", "co2"])],
                    limit=20,
                )
            ],
        }

    def _iot_history(self, kinds, limit=10):
        return [
            {
                "id": log.id,
                "title": log.name,
                "time": fields.Datetime.to_string(log.event_time),
                "simulated": log.simulated,
            }
            for log in self.env["integration.iot.log"].search([("kind", "in", kinds)], limit=limit)
        ]

    @api.model
    def get_devices_data(self, tab="devices", search="", status=""):
        domain = [("archived", "=", False)]
        if search:
            domain += ["|", ("name", "ilike", search), ("code", "ilike", search)]
        if status:
            domain.append(("status", "=", status))
        if tab == "sensors":
            sensors = self.env["integration.iot.sensor"].search([])
            return {
                "sensors": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "parameter": s.parameter,
                        "device": _m2o(s.device_id),
                        "value": s.last_value,
                        "unit": s.unit,
                        "min": s.min_threshold,
                        "max": s.max_threshold,
                        "location": s._iot_location_label(),
                        "updated": fields.Datetime.to_string(s.last_reading_at) if s.last_reading_at else False,
                    }
                    for s in sensors
                ],
                "readings": [
                    {
                        "id": r.id,
                        "sensor": r.sensor_id.display_name,
                        "value": r.value,
                        "quality": r.quality,
                        "source": r.source,
                        "time": fields.Datetime.to_string(r.captured_at),
                    }
                    for r in self.env["integration.iot.reading"].search([], limit=25)
                ],
                "lookups": self.get_lookups(),
            }
        devices = self.env["integration.iot.device"].search(domain)
        return {
            "devices": [self._iot_device_payload(d) for d in devices],
            "types": DEVICE_TYPES,
            "lookups": self.get_lookups(),
        }

    @api.model
    def get_automation_data(self):
        rules = self.env["integration.iot.automation.rule"].search([])
        executions = self.env["integration.iot.automation.execution"].search([], limit=20)
        return {
            "rules": [
                {
                    "id": rule.id,
                    "name": rule.name,
                    "active": rule.active,
                    "parameter": rule.trigger_parameter,
                    "operator": rule.operator,
                    "threshold": rule.threshold,
                    "action": rule.action,
                    "action_value": rule.action_value,
                    "location": rule._iot_location_label(),
                    "schedule_mode": rule.schedule_mode,
                    "last_executed": fields.Datetime.to_string(rule.last_executed) if rule.last_executed else False,
                    "target_device": _m2o(rule.target_device_id),
                }
                for rule in rules
            ],
            "executions": [
                {
                    "id": rec.id,
                    "name": rec.name,
                    "rule": rec.rule_id.display_name,
                    "state": rec.state,
                    "simulated": rec.simulated,
                    "message": rec.message,
                    "time": fields.Datetime.to_string(rec.executed_at),
                }
                for rec in executions
            ],
            "lookups": self.get_lookups(),
        }

    @api.model
    def get_energy_data(self):
        readings = self.env["integration.iot.energy.reading"].search([], order="captured_at desc", limit=60)
        current = readings[:1].kwh if readings else 0.0
        peak = max(readings.mapped("kwh") or [0.0])
        savings = sum(
            self.env["integration.iot.energy.opportunity"].search([("state", "=", "applied")]).mapped("applied_kwh")
        )
        by_location = {}
        for row in readings:
            key = row.building_id.display_name or row.property_id.display_name or _("Unassigned")
            by_location.setdefault(key, 0.0)
            by_location[key] += row.kwh
        opportunities = self.env["integration.iot.energy.opportunity"].search([])
        attention = self.env["integration.iot.alert"].search(
            [("alert_type", "=", "energy_abnormal"), ("state", "in", ["open", "acknowledged"])],
            limit=6,
        )
        return {
            "kpis": {
                "current": current,
                "peak": peak,
                "savings": savings,
            },
            "trend": [
                {"t": fields.Datetime.to_string(row.captured_at), "kwh": row.kwh}
                for row in reversed(readings[:12])
            ],
            "by_location": [{"name": name, "kwh": value} for name, value in by_location.items()],
            "opportunities": [
                {
                    "id": rec.id,
                    "name": rec.name,
                    "estimated_kwh": rec.estimated_kwh,
                    "applied_kwh": rec.applied_kwh,
                    "state": rec.state,
                    "location": rec._iot_location_label(),
                }
                for rec in opportunities
            ],
            "attention": [
                {
                    "id": rec.id,
                    "title": rec.name,
                    "priority": rec.priority,
                    "location": rec._iot_location_label(),
                }
                for rec in attention
            ],
        }
