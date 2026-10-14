# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.translate import _

from .constants import ALERT_STATES, ALERT_TYPES, PRIORITY_LEVELS


class ComplianceAlert(models.Model):
    _name = "compliance.alert"
    _description = "Compliance Alert"
    _inherit = ["mail.thread", "mail.activity.mixin", "compliance.state.mixin"]
    _order = "due_date, id desc"
    _check_company_auto = True
    _ca_state_transitions = {
        "open": {"acknowledged", "escalated", "closed"},
        "acknowledged": {"escalated", "closed"},
        "escalated": {"acknowledged", "closed"},
        "closed": set(),
    }

    def _ca_require_manager(self, message=None):
        if self.env.su:
            return True
        if not self.env.user._ca_is_compliance_manager():
            raise AccessError(
                message or _("Only a Compliance Manager can perform this action.")
            )
        return True

    def _ca_require_groups(self, xmlids, message=None):
        if self.env.su:
            return True
        if not any(self.env.user.has_group(xmlid) for xmlid in xmlids):
            raise AccessError(message or _("You are not allowed to perform this action."))
        return True

    name = fields.Char(required=True, tracking=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    alert_type = fields.Selection(ALERT_TYPES, required=True, default="compliance_check", index=True)
    priority = fields.Selection(PRIORITY_LEVELS, default="medium", required=True, tracking=True)
    due_date = fields.Date(index=True)
    state = fields.Selection(
        ALERT_STATES,
        default="open",
        required=True,
        tracking=True,
        index=True,
    )
    res_model = fields.Char(index=True)
    res_id = fields.Integer(index=True)
    assigned_user_id = fields.Many2one("res.users", index=True)
    acknowledged_by_id = fields.Many2one("res.users", readonly=True)
    acknowledged_datetime = fields.Datetime(readonly=True)
    note = fields.Text()

    def action_acknowledge(self):
        self._ca_require_groups(
            [
                "compliance_audit_management.group_compliance_manager",
            ]
        )
        self.write(
            {
                "acknowledged_by_id": self.env.user.id,
                "acknowledged_datetime": fields.Datetime.now(),
            }
        )
        self._ca_set_state("acknowledged")
        return True

    def action_escalate(self):
        self._ca_require_manager()
        for record in self:
            if record.priority != "critical":
                record.priority = "critical"
        self._ca_set_state("escalated")
        return True

    def action_close(self):
        self._ca_require_manager()
        self._ca_set_state("closed")
        return True

    def _ca_find_open_alert(self, res_model, res_id, alert_type):
        return self.search(
            [
                ("res_model", "=", res_model),
                ("res_id", "=", res_id),
                ("alert_type", "=", alert_type),
                ("state", "in", ["open", "acknowledged", "escalated"]),
            ],
            limit=1,
        )

    def _ca_ensure_activity(self, record, user_id, summary, deadline):
        if not record or not user_id or not summary:
            return False
        if not hasattr(record, "activity_schedule"):
            return False
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not activity_type:
            return False
        existing = self.env["mail.activity"].search(
            [
                ("res_model", "=", record._name),
                ("res_id", "=", record.id),
                ("activity_type_id", "=", activity_type.id),
                ("summary", "=", summary),
                ("user_id", "=", user_id),
            ],
            limit=1,
        )
        if existing:
            return existing
        return record.activity_schedule(
            "mail.mail_activity_data_todo",
            user_id=user_id,
            summary=summary,
            date_deadline=deadline or fields.Date.context_today(self),
        )

    def _ca_ensure_alert(
        self,
        *,
        name,
        alert_type,
        priority,
        due_date,
        res_model,
        res_id,
        assigned_user_id=False,
        company_id=False,
        note=False,
        activity_record=None,
        activity_summary=None,
    ):
        alert = self._ca_find_open_alert(res_model, res_id, alert_type)
        vals = {
            "name": name,
            "alert_type": alert_type,
            "priority": priority,
            "due_date": due_date or False,
            "assigned_user_id": assigned_user_id or False,
            "note": note or False,
        }
        if company_id:
            vals["company_id"] = company_id
        if alert:
            write_vals = {}
            for key in ("name", "due_date", "assigned_user_id", "note"):
                if vals.get(key) and alert[key] != vals[key]:
                    write_vals[key] = vals[key]
            if (
                vals.get("priority")
                and alert.priority != vals["priority"]
                and alert.state != "escalated"
            ):
                write_vals["priority"] = vals["priority"]
            if write_vals:
                alert.write(write_vals)
        else:
            vals.update(
                {
                    "res_model": res_model,
                    "res_id": res_id,
                    "state": "open",
                }
            )
            alert = self.create(vals)
        if activity_record is not None:
            self._ca_ensure_activity(
                activity_record,
                assigned_user_id,
                activity_summary or name,
                due_date,
            )
        return alert

    @api.model
    def _cron_generate_alerts(self):
        """Daily: refresh document expiry, upsert open alerts, schedule To-Dos, close stale."""
        Alert = self.sudo()
        Alert.env["compliance.document"]._cron_refresh_document_states()
        today = fields.Date.context_today(Alert)
        week = today + timedelta(days=7)
        month = today + timedelta(days=30)
        Alert._ca_generate_check_alerts(today, week)
        Alert._ca_generate_audit_alerts(today, week)
        Alert._ca_generate_document_alerts(today)
        Alert._ca_generate_action_alerts(today, week)
        Alert._ca_generate_regulatory_alerts(today, month)
        Alert._ca_close_stale_alerts()
        return True

    @api.model
    def _ca_generate_check_alerts(self, today, week):
        checks = self.env["compliance.check"].search(
            [
                ("state", "in", ["scheduled", "in_progress", "pending"]),
                ("due_date", "!=", False),
                ("due_date", "<=", week),
            ]
        )
        for check in checks:
            overdue = check.due_date < today
            priority = "high" if overdue else "medium"
            name = (
                _("Overdue compliance check: %s") % check.name
                if overdue
                else _("Upcoming compliance check: %s") % check.name
            )
            self._ca_ensure_alert(
                name=name,
                alert_type="compliance_check",
                priority=priority,
                due_date=check.due_date,
                res_model=check._name,
                res_id=check.id,
                assigned_user_id=check.assigned_user_id.id,
                company_id=check.company_id.id,
                note=_("Due %s") % check.due_date,
                activity_record=check,
                activity_summary=name,
            )

    @api.model
    def _ca_generate_audit_alerts(self, today, week):
        audits = self.env["compliance.audit"].search(
            [
                ("state", "in", ["scheduled", "in_progress", "pending_review"]),
                ("date_planned", "!=", False),
                ("date_planned", "<=", week),
            ]
        )
        for audit in audits:
            overdue = audit.date_planned < today
            alert_type = "inspection" if audit.kind == "inspection" else "audit"
            label = _("Inspection") if audit.kind == "inspection" else _("Audit")
            priority = "high" if overdue else "medium"
            name = (
                _("Overdue %(label)s: %(name)s") % {"label": label, "name": audit.name}
                if overdue
                else _("Upcoming %(label)s: %(name)s") % {"label": label, "name": audit.name}
            )
            self._ca_ensure_alert(
                name=name,
                alert_type=alert_type,
                priority=priority,
                due_date=audit.date_planned,
                res_model=audit._name,
                res_id=audit.id,
                assigned_user_id=audit.assigned_user_id.id,
                company_id=audit.company_id.id,
                note=_("Planned %s") % audit.date_planned,
                activity_record=audit,
                activity_summary=name,
            )

    @api.model
    def _ca_generate_document_alerts(self, today):
        docs = self.env["compliance.document"].search(
            [("state", "in", ["expiring_soon", "renewal_due", "expired"])]
        )
        for doc in docs:
            alert_type = (
                "license_renewal" if doc.document_type == "license" else "document_renewal"
            )
            if doc.state == "expired":
                priority = "critical"
                name = _("Expired document: %s") % doc.name
            elif doc.state == "renewal_due":
                priority = "high"
                name = _("Document renewal due: %s") % doc.name
            else:
                priority = "medium"
                name = _("Document expiring soon: %s") % doc.name
            self._ca_ensure_alert(
                name=name,
                alert_type=alert_type,
                priority=priority,
                due_date=doc.expiry_date,
                res_model=doc._name,
                res_id=doc.id,
                assigned_user_id=doc.assigned_user_id.id,
                company_id=doc.company_id.id,
                note=_("Expiry %s (%s)") % (doc.expiry_date, doc.state),
                activity_record=doc,
                activity_summary=name,
            )

    @api.model
    def _ca_generate_action_alerts(self, today, week):
        actions = self.env["compliance.action"].search(
            [
                ("state", "in", ["open", "in_progress", "pending_verification"]),
                ("deadline", "!=", False),
                ("deadline", "<=", week),
            ]
        )
        for action in actions:
            overdue = action.deadline < today
            priority = "high" if overdue else "medium"
            name = (
                _("Overdue corrective action: %s") % action.name
                if overdue
                else _("Upcoming corrective action: %s") % action.name
            )
            self._ca_ensure_alert(
                name=name,
                alert_type="corrective_action",
                priority=priority,
                due_date=action.deadline,
                res_model=action._name,
                res_id=action.id,
                assigned_user_id=action.assigned_user_id.id,
                company_id=action.company_id.id,
                note=_("Deadline %s") % action.deadline,
                activity_record=action,
                activity_summary=name,
            )

    @api.model
    def _ca_generate_regulatory_alerts(self, today, month):
        reports = self.env["compliance.regulatory.report"].search(
            [
                ("state", "!=", "submitted"),
                ("deadline", "!=", False),
                ("deadline", "<=", month),
            ]
        )
        for report in reports:
            overdue = report.deadline < today
            priority = "critical" if overdue else "high"
            name = (
                _("Overdue regulatory submission: %s") % report.name
                if overdue
                else _("Regulatory submission due: %s") % report.name
            )
            assignee = report.assigned_user_id or report.owner_id
            self._ca_ensure_alert(
                name=name,
                alert_type="regulatory_submission",
                priority=priority,
                due_date=report.deadline,
                res_model=report._name,
                res_id=report.id,
                assigned_user_id=assignee.id if assignee else False,
                company_id=report.company_id.id,
                note=_("Deadline %s") % report.deadline,
                activity_record=report,
                activity_summary=name,
            )

    @api.model
    def _ca_alert_still_needed(self, alert, record):
        today = fields.Date.context_today(self)
        week = today + timedelta(days=7)
        month = today + timedelta(days=30)
        if alert.alert_type == "compliance_check":
            return (
                record.state in ("scheduled", "in_progress", "pending")
                and record.due_date
                and record.due_date <= week
            )
        if alert.alert_type in ("audit", "inspection"):
            return (
                record.state in ("scheduled", "in_progress", "pending_review")
                and record.date_planned
                and record.date_planned <= week
            )
        if alert.alert_type in ("document_renewal", "license_renewal"):
            return record.state in ("expiring_soon", "renewal_due", "expired")
        if alert.alert_type == "corrective_action":
            return (
                record.state in ("open", "in_progress", "pending_verification")
                and record.deadline
                and record.deadline <= week
            )
        if alert.alert_type == "regulatory_submission":
            return (
                record.state != "submitted"
                and record.deadline
                and record.deadline <= month
            )
        return True

    @api.model
    def _ca_close_stale_alerts(self):
        alerts = self.search([("state", "in", ["open", "acknowledged", "escalated"])])
        for alert in alerts:
            if not alert.res_model or not alert.res_id or alert.res_model not in self.env:
                continue
            record = self.env[alert.res_model].browse(alert.res_id).exists()
            if not record or not self._ca_alert_still_needed(alert, record):
                alert.with_context(ca_allow_state_write=True).write({"state": "closed"})
