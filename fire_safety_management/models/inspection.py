# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from .constants import (
    CHECKLIST_RESULTS,
    INSPECTION_STATES,
    INSPECTION_TYPES,
    XMLID_SAFETY_MANAGER,
    XMLID_SECURITY,
)


class FireSafetyInspection(models.Model):
    _name = "fire.safety.inspection"
    _description = "Fire & Safety Inspection"
    _inherit = [
        "mail.thread",
        "mail.activity.mixin",
        "fire.safety.scoped.mixin",
        "fire.safety.state.mixin",
    ]
    _order = "scheduled_date desc, id desc"
    _rec_name = "name"
    _check_company_auto = True
    _fs_state_transitions = {
        "scheduled": {"in_progress"},
        "in_progress": {"pending", "completed"},
        "pending": {"completed", "in_progress"},
        "completed": {"closed"},
        "closed": set(),
    }

    name = fields.Char(required=True, copy=False, default="New", tracking=True)
    inspection_type = fields.Selection(
        INSPECTION_TYPES,
        required=True,
        default="fire_inspection",
        tracking=True,
        index=True,
    )
    state = fields.Selection(
        INSPECTION_STATES,
        default="scheduled",
        required=True,
        tracking=True,
        index=True,
        copy=False,
    )
    scheduled_date = fields.Date(required=True, index=True, tracking=True)
    start_datetime = fields.Datetime(readonly=True)
    complete_datetime = fields.Datetime(readonly=True)
    close_datetime = fields.Datetime(readonly=True)
    is_overdue = fields.Boolean(
        compute="_compute_is_overdue",
        search="_search_is_overdue",
        help="Computed: scheduled or in progress with a date before today.",
    )
    checklist_template_id = fields.Many2one(
        "fire.safety.checklist.template",
        ondelete="restrict",
        tracking=True,
    )
    line_ids = fields.One2many("fire.safety.inspection.line", "inspection_id")
    finding_ids = fields.One2many("fire.safety.finding", "inspection_id")
    finding_count = fields.Integer(compute="_compute_counts")
    action_count = fields.Integer(compute="_compute_counts")
    line_count = fields.Integer(compute="_compute_counts")
    failed_line_count = fields.Integer(compute="_compute_counts")
    inspector_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        tracking=True,
    )
    location_detail = fields.Char()
    notes = fields.Html()
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "fire_safety_inspection_attachment_rel",
        "inspection_id",
        "attachment_id",
        string="Evidence",
    )

    @api.depends("scheduled_date", "state")
    def _compute_is_overdue(self):
        today = fields.Date.context_today(self)
        for record in self:
            record.is_overdue = (
                record.state in ("scheduled", "in_progress")
                and bool(record.scheduled_date)
                and record.scheduled_date < today
            )

    def _search_is_overdue(self, operator, value):
        today = fields.Date.context_today(self)
        overdue_domain = [
            ("state", "in", ("scheduled", "in_progress")),
            ("scheduled_date", "<", today),
        ]
        if (operator in ("=", "==") and value) or (operator in ("!=", "<>") and not value):
            return overdue_domain
        return ["!"] + overdue_domain

    @api.depends("line_ids", "line_ids.result", "finding_ids", "finding_ids.action_ids")
    def _compute_counts(self):
        for record in self:
            record.line_count = len(record.line_ids)
            record.failed_line_count = len(record.line_ids.filtered(lambda line: line.result == "fail"))
            record.finding_count = len(record.finding_ids)
            record.action_count = len(record.finding_ids.action_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].sudo().next_by_code("fire.safety.inspection") or "New"
        records = super().create(vals_list)
        for record in records:
            if record.checklist_template_id and not record.line_ids:
                record.checklist_template_id.action_copy_items_to_inspection(record)
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get("checklist_template_id"):
            for record in self:
                if not record.line_ids:
                    record.checklist_template_id.action_copy_items_to_inspection(record)
        return res

    def action_apply_checklist_template(self):
        self.ensure_one()
        self._fs_require_safety_manager()
        if self.state not in ("scheduled", "in_progress"):
            raise UserError(_("Checklist can only be applied to scheduled or in-progress inspections."))
        if not self.checklist_template_id:
            raise UserError(_("Select a checklist template first."))
        self.line_ids.unlink()
        self.checklist_template_id.action_copy_items_to_inspection(self)
        return True

    @api.model
    def get_assigned_inspections(self, user=None, states=None):
        """Mobile-ready: assigned inspections for the Operations / Staff app."""
        user = user or self.env.user
        domain = [
            "|",
            ("assigned_user_id", "=", user.id),
            ("inspector_id", "=", user.id),
        ]
        if states:
            domain.append(("state", "in", list(states)))
        return self.search(domain)

    def action_start_inspection(self):
        self._fs_require_groups(
            [XMLID_SAFETY_MANAGER, XMLID_SECURITY],
            _("Only Safety Manager or Security can start an inspection."),
        )
        self._fs_set_state("in_progress")
        self.filtered(lambda rec: not rec.start_datetime).write(
            {"start_datetime": fields.Datetime.now()}
        )
        return True

    def action_complete_inspection(self):
        self._fs_require_safety_manager(_("Only a Safety Manager can complete an inspection."))
        for record in self:
            unfinished = record.line_ids.filtered(lambda line: line.required and not line.result)
            if unfinished:
                raise UserError(
                    _("Complete all required checklist items before finishing %(name)s.")
                    % {"name": record.name}
                )
            if not record.line_ids:
                raise UserError(
                    _("Checklist execution is required before completing %(name)s.")
                    % {"name": record.name}
                )
            failed = record.line_ids.filtered(lambda line: line.result == "fail")
            if failed and not record.finding_ids:
                raise UserError(
                    _("Failed checklist items require at least one finding on %(name)s.")
                    % {"name": record.name}
                )
            open_actions = record.finding_ids.action_ids.filtered(lambda act: act.state != "closed")
            if open_actions:
                record._fs_set_state("pending")
            else:
                record._fs_set_state("completed")
                if not record.complete_datetime:
                    record.complete_datetime = fields.Datetime.now()
        return True

    def action_mark_completed(self):
        self._fs_require_safety_manager()
        for record in self:
            open_actions = record.finding_ids.action_ids.filtered(lambda act: act.state != "closed")
            if open_actions:
                raise UserError(
                    _("Close all corrective actions before completing %(name)s.")
                    % {"name": record.name}
                )
        self._fs_set_state("completed")
        self.filtered(lambda rec: not rec.complete_datetime).write(
            {"complete_datetime": fields.Datetime.now()}
        )
        return True

    def action_close_inspection(self):
        self._fs_require_safety_manager(_("Only a Safety Manager can close an inspection."))
        self._fs_set_state("closed")
        self.write({"close_datetime": fields.Datetime.now()})
        return True

    def action_update_checklist_line(self, line_id, result, notes=None):
        """Mobile-ready checklist result update."""
        self.ensure_one()
        line = self.line_ids.filtered(lambda rec: rec.id == line_id)
        if not line:
            raise UserError(_("Checklist line does not belong to this inspection."))
        vals = {"result": result}
        if notes is not None:
            vals["notes"] = notes
        line.write(vals)
        return True


class FireSafetyInspectionLine(models.Model):
    _name = "fire.safety.inspection.line"
    _description = "Fire & Safety Inspection Checklist Line"
    _order = "sequence, id"

    inspection_id = fields.Many2one(
        "fire.safety.inspection",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="inspection_id.company_id", store=True, index=True)
    item_id = fields.Many2one("fire.safety.checklist.item", ondelete="set null")
    name = fields.Char(required=True)
    category = fields.Selection(
        [
            ("fire_extinguishers", "Fire Extinguishers"),
            ("fire_alarms", "Fire Alarms"),
            ("fire_exits", "Fire Exits"),
            ("emergency_lighting", "Emergency Lighting"),
            ("evacuation_routes", "Evacuation Routes"),
            ("emergency_signage", "Emergency Signage"),
            ("fire_safety_equipment", "Fire Safety Equipment"),
        ]
    )
    sequence = fields.Integer(default=10)
    required = fields.Boolean(default=True)
    result = fields.Selection(CHECKLIST_RESULTS, index=True)
    notes = fields.Text()
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "fire_safety_inspection_line_attachment_rel",
        "line_id",
        "attachment_id",
        string="Evidence",
    )
