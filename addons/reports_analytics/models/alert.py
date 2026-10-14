# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from .constants import ALERT_CONDITIONS, ALERT_FREQUENCIES, ALERT_SEVERITIES, ALERT_TYPES


class AnalyticsAlert(models.Model):
    _name = "analytics.alert"
    _description = "Analytics Alert"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "severity, name"
    _check_company_auto = True

    name = fields.Char(required=True, tracking=True)
    alert_type = fields.Selection(ALERT_TYPES, required=True, default="threshold", tracking=True)
    severity = fields.Selection(ALERT_SEVERITIES, required=True, default="warning", tracking=True, index=True)
    module = fields.Char(index=True)
    property_ref = fields.Char()
    kpi_id = fields.Many2one("analytics.kpi", ondelete="set null", index=True)
    metric_label = fields.Char()
    condition = fields.Selection(ALERT_CONDITIONS, required=True, default="gt")
    threshold = fields.Float(required=True)
    recipient_ids = fields.Many2many(
        "res.users",
        "analytics_alert_user_rel",
        "alert_id",
        "user_id",
        string="Recipients",
    )
    notify_in_app = fields.Boolean(default=True)
    notify_email = fields.Boolean(default=True)
    notify_sms = fields.Boolean(default=False)
    frequency = fields.Selection(ALERT_FREQUENCIES, default="once", required=True)
    active = fields.Boolean(default=True, tracking=True)
    last_value = fields.Float()
    last_evaluated = fields.Datetime()
    last_triggered = fields.Datetime()
    is_triggered = fields.Boolean(default=False)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            self.env["analytics.audit.log"].log_event(
                "alert",
                _("Alert created: %s") % record.name,
                alert_id=record.id,
                kpi_id=record.kpi_id.id,
                related_module=record.module,
            )
        return records

    def write(self, vals):
        for record in self:
            if any(key in vals for key in ("threshold", "condition", "kpi_id", "severity", "active")):
                self.env["analytics.audit.log"].log_event(
                    "alert",
                    _("Alert updated: %s") % record.name,
                    alert_id=record.id,
                    kpi_id=record.kpi_id.id,
                )
        return super().write(vals)

    def ui_row(self):
        self.ensure_one()
        snapshot = self.kpi_id.compute_snapshot() if self.kpi_id else {}
        current = snapshot.get("value") if snapshot else self.last_value
        return {
            "id": self.id,
            "name": self.name,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "module": self.module or (self.kpi_id.category if self.kpi_id else ""),
            "metric": self.metric_label or (self.kpi_id.name if self.kpi_id else ""),
            "current_value": current,
            "available": snapshot.get("available", False) if snapshot else False,
            "reason": snapshot.get("reason") if snapshot else _("No KPI linked"),
            "threshold": self.threshold,
            "condition": self.condition,
            "property_ref": self.property_ref or "",
            "status": "triggered" if self.is_triggered else "ok",
            "active": self.active,
        }

    @api.model
    def action_create_from_ui(self, vals):
        if not vals.get("name"):
            raise UserError(_("Alert name is required."))
        record = self.create({
            "name": vals["name"],
            "alert_type": vals.get("alert_type") or "threshold",
            "severity": vals.get("severity") or "warning",
            "module": vals.get("module"),
            "property_ref": vals.get("property_ref"),
            "kpi_id": vals.get("kpi_id") or False,
            "metric_label": vals.get("metric_label"),
            "condition": vals.get("condition") or "gt",
            "threshold": vals.get("threshold") or 0.0,
            "recipient_ids": [(6, 0, vals.get("recipient_ids") or [])],
            "notify_in_app": bool(vals.get("notify_in_app", True)),
            "notify_email": bool(vals.get("notify_email", True)),
            "notify_sms": bool(vals.get("notify_sms", False)),
            "frequency": vals.get("frequency") or "once",
            "active": True,
        })
        record.action_evaluate()
        return record.ui_row()

    def _condition_holds(self, value):
        if value is None:
            return False
        threshold = self.threshold
        if self.condition == "gt":
            return value > threshold
        if self.condition == "gte":
            return value >= threshold
        if self.condition == "lt":
            return value < threshold
        if self.condition == "lte":
            return value <= threshold
        return value == threshold

    def action_evaluate(self):
        for record in self:
            record._evaluate()
        return True

    def _evaluate(self):
        self.ensure_one()
        if not self.active:
            return False
        if not self.kpi_id:
            return False
        snapshot = self.kpi_id.compute_snapshot()
        value = snapshot.get("value")
        self.last_value = value or 0.0
        self.last_evaluated = fields.Datetime.now()
        if not snapshot.get("available"):
            return False
        triggered = self._condition_holds(value)
        was_triggered = self.is_triggered
        self.is_triggered = triggered
        if not triggered:
            return False
        if self.frequency == "once" and was_triggered and self.last_triggered:
            return False
        self.last_triggered = fields.Datetime.now()
        self._notify(value)
        return True

    def _notify(self, value):
        body = _(
            "Analytics alert '%(name)s' is %(severity)s: %(metric)s is %(value)s (condition %(condition)s %(threshold)s)."
        ) % {
            "name": self.name,
            "severity": self.severity,
            "metric": self.metric_label or (self.kpi_id.name if self.kpi_id else ""),
            "value": value,
            "condition": self.condition,
            "threshold": self.threshold,
        }
        partners = self.recipient_ids.mapped("partner_id")
        if self.notify_in_app:
            self.message_post(body=body, partner_ids=partners.ids, subtype_xmlid="mail.mt_comment")
            for user in self.recipient_ids:
                self.activity_schedule(
                    "mail.mail_activity_data_warning",
                    user_id=user.id,
                    summary=self.name,
                    note=body,
                ) if hasattr(self, "activity_schedule") else None
        if self.notify_email and partners:
            template = self.env.ref("reports_analytics.mail_template_analytics_alert", raise_if_not_found=False)
            if template:
                template.send_mail(self.id, force_send=False)
            else:
                self.message_notify(
                    partner_ids=partners.ids,
                    subject=_("Analytics alert: %s") % self.name,
                    body=body,
                )
        if self.notify_sms and "sms.sms" in self.env and self.env["sms.sms"].has_access("create"):
            Sms = self.env["sms.sms"]
            for partner in partners:
                number = partner.mobile or partner.phone
                if number:
                    Sms.create({"number": number, "body": body})

    def action_acknowledge(self):
        self.write({"is_triggered": False})
        return True

    @api.model
    def _cron_evaluate_alerts(self):
        for record in self.search([("active", "=", True)]):
            try:
                record._evaluate()
            except Exception:
                continue
        return True
