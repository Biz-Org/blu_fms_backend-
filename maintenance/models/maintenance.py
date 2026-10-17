# -*- coding: utf-8 -*-

import ast
from collections import defaultdict
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from odoo.osv import expression
from markupsafe import Markup, escape
from odoo.exceptions import ValidationError
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import safe_eval
from odoo.tools.misc import format_date


class MaintenanceStage(models.Model):
    """ Model for case stages. This models the main stages of a Maintenance Request management flow. """

    _name = 'maintenance.stage'
    _description = 'Maintenance Stage'
    _order = 'sequence, id'

    name = fields.Char('Name', required=True, translate=True)
    sequence = fields.Integer('Sequence', default=20)
    fold = fields.Boolean('Folded in Maintenance Pipe')
    done = fields.Boolean('Request Done')


class MaintenanceEquipmentCategory(models.Model):
    _name = 'maintenance.equipment.category'
    _inherit = ['mail.alias.mixin', 'mail.thread']
    _description = 'Maintenance Equipment Category'

    @api.depends('equipment_ids')
    def _compute_fold(self):
        # fix mutual dependency: 'fold' depends on 'equipment_count', which is
        # computed with a read_group(), which retrieves 'fold'!
        self.fold = False
        for category in self:
            category.fold = False if category.equipment_count else True

    name = fields.Char('Category Name', required=True, translate=True)
    company_id = fields.Many2one('res.company', string='Company',
        default=lambda self: self.env.company)
    technician_user_id = fields.Many2one(
        'res.users', string='Responsible (legacy)', tracking=True, default=lambda self: self.env.uid,
        help='Deprecated: use Corrective / Preventive responsible. Used only as fallback when type-specific fields are empty.',
    )
    corrective_responsible_user_id = fields.Many2one(
        'res.users', string='Corrective Responsible', tracking=True,
        domain="[('share', '=', False)]",
        help='Default owner for breakdown / corrective work on equipment in this category.',
    )
    preventive_responsible_user_id = fields.Many2one(
        'res.users', string='Preventive Responsible', tracking=True,
        domain="[('share', '=', False)]",
        help='Default owner for preventive / PM work on equipment in this category.',
    )
    predictive_responsible_user_id = fields.Many2one(
        'res.users', string='Predictive Responsible', tracking=True,
        domain="[('share', '=', False)]",
        help='Default owner for predictive / condition monitoring work in this category.',
    )
    color = fields.Integer('Color Index')
    note = fields.Html('Comments', translate=True)
    equipment_ids = fields.One2many('maintenance.equipment', 'category_id', string='Equipment', copy=False)
    equipment_count = fields.Integer(string="Equipment Count", compute='_compute_equipment_count')
    maintenance_ids = fields.One2many('maintenance.request', 'category_id', copy=False)
    maintenance_count = fields.Integer(string="Maintenance Count", compute='_compute_maintenance_count')
    maintenance_open_count = fields.Integer(string="Current Maintenance", compute='_compute_maintenance_count')
    alias_id = fields.Many2one(help="Email alias for this equipment category. New emails will automatically "
        "create a new equipment under this category.")
    fold = fields.Boolean(string='Folded in Maintenance Pipe', compute='_compute_fold', store=True)
    equipment_properties_definition = fields.PropertiesDefinition('Equipment Properties')

    def _compute_equipment_count(self):
        equipment_data = self.env['maintenance.equipment']._read_group([('category_id', 'in', self.ids)], ['category_id'], ['__count'])
        mapped_data = {category.id: count for category, count in equipment_data}
        for category in self:
            category.equipment_count = mapped_data.get(category.id, 0)

    def _compute_maintenance_count(self):
        maintenance_data = self.env['maintenance.request']._read_group([('category_id', 'in', self.ids)], ['category_id', 'archive'], ['__count'])
        mapped_data = {(category.id, archive): count for category, archive, count in maintenance_data}
        for category in self:
            category.maintenance_open_count = mapped_data.get((category.id, False), 0)
            category.maintenance_count = category.maintenance_open_count + mapped_data.get((category.id, True), 0)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_contains_maintenance_requests(self):
        for category in self:
            if category.equipment_ids or category.maintenance_ids:
                raise UserError(_("You cannot delete an equipment category containing equipment or maintenance requests."))

    def _alias_get_creation_values(self):
        values = super(MaintenanceEquipmentCategory, self)._alias_get_creation_values()
        values['alias_model_id'] = self.env['ir.model']._get('maintenance.request').id
        if self.id:
            values['alias_defaults'] = defaults = ast.literal_eval(self.alias_defaults or "{}")
            defaults['category_id'] = self.id
        return values


class MaintenanceMixin(models.AbstractModel):
    _name = 'maintenance.mixin'
    _check_company_auto = True
    _description = 'Maintenance Maintained Item'

    company_id = fields.Many2one('res.company', string='Company',
        default=lambda self: self.env.company)
    effective_date = fields.Date('Effective Date', default=fields.Date.context_today, required=True, help="This date will be used to compute the Mean Time Between Failure.")
    maintenance_team_id = fields.Many2one('maintenance.team', string='Maintenance Team', compute='_compute_maintenance_team_id', store=True, readonly=False, check_company=True)
    maintenance_ids = fields.One2many('maintenance.request')  # needs to be extended in order to specify inverse_name !
    maintenance_count = fields.Integer(compute='_compute_maintenance_count', string="Maintenance Count", store=True)
    maintenance_open_count = fields.Integer(compute='_compute_maintenance_count', string="Current Maintenance", store=True)
    expected_mtbf = fields.Integer(string='Expected MTBF', help='Expected Mean Time Between Failure')
    expected_mttr = fields.Integer(
        string='Expected MTTR',
        help='Expected mean time to repair in days (master data / planning target).',
    )
    mtbf = fields.Integer(compute='_compute_maintenance_request', string='MTBF', help='Mean Time Between Failure, computed based on done corrective maintenances.')
    mttr = fields.Integer(compute='_compute_maintenance_request', string='MTTR', help='Mean Time To Repair')
    estimated_next_failure = fields.Date(compute='_compute_maintenance_request', string='Estimated time before next failure (in days)', help='Computed as Latest Failure Date + MTBF')
    latest_failure_date = fields.Date(compute='_compute_maintenance_request', string='Latest Failure Date')
    life_consumed_percent = fields.Float(
        string='Life Consumed %',
        default=0.0,
        help='Optional manual override (0–100). Leave at 0 so the RUL & TOBM report '
             'computes life from preventive/corrective history, MTBF, and failure risk.',
    )

    @api.depends('company_id')
    def _compute_maintenance_team_id(self):
        for record in self:
            if record.maintenance_team_id.company_id and record.maintenance_team_id.company_id.id != record.company_id.id:
                record.maintenance_team_id = False

    @api.depends(
        'effective_date',
        'maintenance_ids',
        'maintenance_ids.maintenance_type',
        'maintenance_ids.stage_id',
        'maintenance_ids.stage_id.done',
        'maintenance_ids.close_date',
        'maintenance_ids.request_date',
    )
    def _compute_maintenance_request(self):
        for record in self:
            maintenance_requests = record.maintenance_ids.filtered(
                lambda mr: mr.maintenance_type == 'corrective' and mr.stage_id and mr.stage_id.done
            )
            count = len(maintenance_requests)
            if not count:
                record.mttr = 0
                record.latest_failure_date = False
                record.mtbf = 0
                record.estimated_next_failure = False
                continue

            record.mttr = int(round(sum(
                int((request.close_date - request.request_date).days)
                if request.close_date and request.request_date else 0
                for request in maintenance_requests
            ) / count))
            record.latest_failure_date = max(request.request_date for request in maintenance_requests)
            span_days = (record.latest_failure_date - record.effective_date).days
            if span_days <= 0:
                record.mtbf = 0
            else:
                # Integer field must not truncate 0.6 -> 0 (misleading MTBF)
                record.mtbf = int(round(span_days / count))
            record.estimated_next_failure = (
                record.mtbf and record.latest_failure_date
                and record.latest_failure_date + relativedelta(days=record.mtbf)
                or False
            )

    @api.depends('maintenance_ids.stage_id.done', 'maintenance_ids.archive')
    def _compute_maintenance_count(self):
        for record in self:
            record.maintenance_count = len(record.maintenance_ids)
            record.maintenance_open_count = len(record.maintenance_ids.filtered(lambda mr: not mr.stage_id.done and not mr.archive))


class MaintenanceEquipment(models.Model):
    _name = 'maintenance.equipment'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'maintenance.mixin']
    _description = 'Maintenance Equipment'
    _check_company_auto = True

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'owner_user_id' in init_values and self.owner_user_id:
            return self.env.ref('maintenance.mt_mat_assign')
        return super(MaintenanceEquipment, self)._track_subtype(init_values)

    @api.depends('serial_no')
    def _compute_display_name(self):
        for record in self:
            if record.serial_no:
                record.display_name = (record.name or '') + '/' + record.serial_no
            else:
                record.display_name = record.name

    name = fields.Char('Equipment Name', required=True, translate=True)
    equipment_code = fields.Char(
        string='Equipment Code',
        copy=False,
        index=True,
        help='Unique plant asset code used for master data import and duplicate checks.',
    )
    excel_import_id = fields.Many2one(
        'maintenance.equipment.import.log',
        string='Excel upload',
        ondelete='cascade',
        copy=False,
        index=True,
        help='Upload batch that created this equipment (deleted together when upload is removed).',
    )
    is_excel_import = fields.Boolean(
        string='From Excel upload',
        default=False,
        index=True,
        copy=False,
    )
    active = fields.Boolean(default=True)
    owner_user_id = fields.Many2one('res.users', string='Owner', tracking=True)
    corrective_responsible_user_id = fields.Many2one(
        'res.users', string='Corrective Responsible', tracking=True,
        domain="[('share', '=', False)]",
        help='Default owner for corrective (breakdown) maintenance on this asset.',
    )
    preventive_responsible_user_id = fields.Many2one(
        'res.users', string='Preventive Responsible', tracking=True,
        domain="[('share', '=', False)]",
        help='Default owner for preventive (PM) maintenance on this asset.',
    )
    predictive_responsible_user_id = fields.Many2one(
        'res.users', string='Predictive Responsible', tracking=True,
        domain="[('share', '=', False)]",
        help='Default owner for predictive maintenance on this asset.',
    )
    category_id = fields.Many2one('maintenance.equipment.category', string='Equipment Category',
                                  tracking=True, group_expand='_read_group_category_ids')
    partner_id = fields.Many2one('res.partner', string='Vendor', check_company=True)
    partner_ref = fields.Char('Vendor Reference')
    location = fields.Char('Location')
    model = fields.Char('Model')
    serial_no = fields.Char('Serial Number', copy=False)
    assign_date = fields.Date('Assigned Date', tracking=True)
    cost = fields.Float('Cost')
    note = fields.Html('Note')
    warranty_date = fields.Date('Warranty Expiration Date')
    color = fields.Integer('Color Index')
    scrap_date = fields.Date('Scrap Date')
    image_1920 = fields.Image("Image", max_width=1920, max_height=1920)
    barcode = fields.Char(string='Barcode', copy=False, index=True)
    asset_tag = fields.Char(string='Asset Tag', copy=False)
    purchase_date = fields.Date(string='Purchase Date')
    supplier_id = fields.Many2one('res.partner', string='Supplier', check_company=True)
    maintenance_ids = fields.One2many('maintenance.request', 'equipment_id')
    equipment_properties = fields.Properties('Properties', definition='category_id.equipment_properties_definition', copy=True)
    match_serial = fields.Boolean(compute='_compute_match_serial')

    @api.depends('serial_no')
    def _compute_match_serial(self):
        if 'stock.lot' not in self.env or not self.env['stock.lot'].has_access('read'):
            self.match_serial = False
            return
        matched_serial_data = self.env['stock.lot']._read_group(
            [('name', 'in', self.mapped('serial_no'))],
            ['name'],
            ['__count'],
        )
        matched_serial_count = dict(matched_serial_data)
        for equipment in self:
            equipment.match_serial = matched_serial_count.get(equipment.serial_no, 0)

    @api.onchange('category_id')
    def _onchange_category_id_responsible(self):
        for equipment in self:
            if not equipment.category_id:
                continue
            cat = equipment.category_id
            if not equipment.corrective_responsible_user_id:
                equipment.corrective_responsible_user_id = (
                    cat.corrective_responsible_user_id or cat.technician_user_id
                )
            if not equipment.preventive_responsible_user_id:
                equipment.preventive_responsible_user_id = cat.preventive_responsible_user_id
            if not equipment.predictive_responsible_user_id:
                equipment.predictive_responsible_user_id = cat.predictive_responsible_user_id

    _sql_constraints = [
        ('serial_no', 'unique(serial_no)', "Another asset already exists with this serial number!"),
        (
            'equipment_code_unique',
            'unique(equipment_code)',
            'Another asset already exists with this equipment code!',
        ),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        equipments = super().create(vals_list)
        for equipment in equipments:
            if equipment.owner_user_id:
                equipment.message_subscribe(partner_ids=[equipment.owner_user_id.partner_id.id])
        companies = equipments.mapped('company_id').filtered(lambda c: c) or self.env.company
        self.env['maintenance.analytics.dashboard']._invalidate_for_companies(companies)
        return equipments

    def write(self, vals):
        if vals.get('owner_user_id'):
            self.message_subscribe(partner_ids=self.env['res.users'].browse(vals['owner_user_id']).partner_id.ids)
        res = super(MaintenanceEquipment, self).write(vals)
        companies = self.mapped('company_id').filtered(lambda c: c) or self.env.company
        self.env['maintenance.analytics.dashboard']._invalidate_for_companies(companies)
        return res

    def unlink(self):
        companies = self.mapped('company_id').filtered(lambda c: c) or self.env.company
        res = super().unlink()
        self.env['maintenance.analytics.dashboard']._invalidate_for_companies(companies)
        return res

    def action_open_equipment_excel_import(self):
        """Open Excel import wizard (popup) from the Equipment screen."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import Equipment Master Data'),
            'res_model': 'maintenance.equipment.import.wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def action_download_equipment_excel_template(self):
        wizard = self.env['maintenance.equipment.import.wizard'].create({})
        return wizard.action_download_template()

    @api.model
    def _deactivate_equipment_import_menu(self):
        menu = self.env.ref('maintenance.menu_import_equipment_master_data', raise_if_not_found=False)
        if menu:
            menu.sudo().write({'active': False})

    @api.model
    def restore_equipment_after_excel_revert(self):
        """Reactivate equipment archived by the Excel auto-clear logic."""
        Equipment = self.sudo().with_context(active_test=False)
        archived = Equipment.search([('active', '=', False)])
        if archived:
            archived.write({
                'active': True,
                'excel_import_id': False,
                'is_excel_import': False,
            })
        Request = self.env['maintenance.request']
        if hasattr(Request, 'restore_plant_demo_operational_screens'):
            Request.restore_plant_demo_operational_screens()
        return len(archived)

    @api.model
    def _read_group_category_ids(self, categories, domain):
        """ Read group customization in order to display all the categories in
            the kanban view, even if they are empty.
        """
        # bypass ir.model.access checks, but search with ir.rules
        search_domain = self.env['ir.rule']._compute_domain(categories._name)
        category_ids = categories.sudo()._search(search_domain, order=categories._order)
        return categories.browse(category_ids)

    def action_open_matched_serial(self):
        self.ensure_one()
        action = self.env.ref('stock.action_production_lot_form', raise_if_not_found=False)
        if not action:
            return True
        action_dict = action._get_action_dict()
        action_dict['context'] = {'search_default_name': self.serial_no}
        return action_dict


class MaintenanceRequest(models.Model):
    _name = 'maintenance.request'
    _inherit = ['mail.thread.cc', 'mail.activity.mixin']
    _description = 'Maintenance Request'
    _order = "id desc"
    _check_company_auto = True

    @api.returns('self')
    def _default_stage(self):
        return self.env['maintenance.stage'].search([], limit=1)

    def _creation_subtype(self):
        return self.env.ref('maintenance.mt_req_created')

    def _track_subtype(self, init_values):
        self.ensure_one()
        if 'stage_id' in init_values:
            return self.env.ref('maintenance.mt_req_status')
        return super(MaintenanceRequest, self)._track_subtype(init_values)

    def _get_default_team_id(self):
        MT = self.env['maintenance.team']
        team = MT.search([('company_id', '=', self.env.company.id)], limit=1)
        if not team:
            team = MT.search([], limit=1)
        return team.id

    @api.model
    def _selection_maintenance_type(self):
        from .maintenance_types import MAINTENANCE_REQUEST_TYPE_SELECTION
        return MAINTENANCE_REQUEST_TYPE_SELECTION

    @api.model
    def _selection_planning_maintenance_type(self):
        from .maintenance_types import PLANNING_MAINTENANCE_TYPE_SELECTION
        return PLANNING_MAINTENANCE_TYPE_SELECTION

    @api.onchange('maintenance_type')
    def _onchange_maintenance_type_planning(self):
        mapping = {
            'corrective': 'breakdown',
            'preventive': 'preventive',
            'predictive': 'predictive',
        }
        for request in self:
            if request.maintenance_type in mapping:
                request.planning_maintenance_type = mapping[request.maintenance_type]
            if request.maintenance_type == 'corrective':
                request.failure_found_during_job = False

    @api.depends('maintenance_type', 'planning_maintenance_type', 'failure_found_during_job')
    def _compute_rca_policy(self):
        from .maintenance_types import rca_required_for_request
        for request in self:
            required = rca_required_for_request(
                request.maintenance_type,
                request.failure_found_during_job,
                request.planning_maintenance_type,
            )
            request.rca_required = required
            if required:
                request.rca_policy_hint = _(
                    'RCA required: corrective/breakdown work, or failure found on this job.'
                )
            else:
                request.rca_policy_hint = _(
                    'RCA optional: routine preventive/predictive — enable only if a failure was found.'
                )

    def _raise_if_rca_missing_for_closure(self):
        if self.env.context.get('install_module') or self.env.context.get('module'):
            return
        for request in self:
            if not request.rca_required:
                continue
            if not (request.final_root_cause or '').strip():
                raise ValidationError(_(
                    'Root Cause Analysis is required for %(name)s.\n'
                    'Open Analysis, enter Final Root Cause, and save before completing this work order.',
                    name=request.display_name,
                ))

    name = fields.Char('Subjects', required=True)
    company_id = fields.Many2one('res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    description = fields.Html('Description')
    request_date = fields.Date('Request Date', tracking=True, default=fields.Date.context_today,
                               help="Date requested for the maintenance to happen")
    owner_user_id = fields.Many2one('res.users', string='Created by User', default=lambda s: s.env.uid)
    category_id = fields.Many2one('maintenance.equipment.category', related='equipment_id.category_id', string='Category', store=True, readonly=True)
    equipment_id = fields.Many2one(
        'maintenance.equipment',
        string='Equipment',
        ondelete='set null',
        index=True,
        check_company=True,
        help='Cleared automatically if the linked equipment is deleted; the request is kept for history.',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Assigned Owner',
        compute='_compute_user_id',
        store=True,
        readonly=False,
        tracking=True,
        domain="[('share', '=', False)]",
        help='Owner for this request, based on maintenance type and equipment defaults.',
    )
    stage_id = fields.Many2one('maintenance.stage', string='Stage', ondelete='restrict', tracking=True,
                               group_expand='_read_group_stage_ids', default=_default_stage, copy=False)
    priority = fields.Selection([('0', 'Very Low'), ('1', 'Low'), ('2', 'Normal'), ('3', 'High')], string='Priority')
    color = fields.Integer('Color Index')
    close_date = fields.Date('Close Date', help="Date the maintenance was finished. ")
    kanban_state = fields.Selection([('normal', 'In Progress'), ('blocked', 'Blocked'), ('done', 'Ready for next stage')],
                                    string='Kanban State', required=True, default='normal', tracking=True)
    # active = fields.Boolean(default=True, help="Set active to false to hide the maintenance request without deleting it.")
    archive = fields.Boolean(default=False, help="Set archive to true to hide the maintenance request without deleting it.")
    maintenance_type = fields.Selection(
        selection='_selection_maintenance_type',
        string='Maintenance Type',
        default='corrective',
        required=True,
        tracking=True,
    )
    failure_found_during_job = fields.Boolean(
        string='Failure Found During Job',
        help='For preventive or predictive work: enable when an abnormal failure was found and RCA is required.',
        tracking=True,
    )
    rca_required = fields.Boolean(
        string='RCA Required',
        compute='_compute_rca_policy',
        store=True,
    )
    rca_policy_hint = fields.Char(
        string='RCA Policy',
        compute='_compute_rca_policy',
    )
    schedule_date = fields.Datetime('Scheduled Date', help="Date the maintenance team plans the maintenance.  It should not differ much from the Request Date. ")
    maintenance_team_id = fields.Many2one('maintenance.team', string='Team', required=True, default=_get_default_team_id,
                                          compute='_compute_maintenance_team_id', store=True, readonly=False, check_company=True)
    duration = fields.Float(help="Duration in hours.")
    done = fields.Boolean(related='stage_id.done')
    instruction_type = fields.Selection([
        ('pdf', 'PDF'), ('google_slide', 'Google Slide'), ('text', 'Text')],
        string="Instruction", default="text"
    )
    instruction_pdf = fields.Binary('PDF')
    instruction_google_slide = fields.Char('Google Slide', help="Paste the url of your Google Slide. Make sure the access to the document is public.")
    instruction_text = fields.Html('Text')
    recurring_maintenance = fields.Boolean(string="Recurrent", compute='_compute_recurring_maintenance', store=True, readonly=False)
    repeat_interval = fields.Integer(string='Repeat Every', default=1)
    repeat_unit = fields.Selection([
        ('day', 'Days'),
        ('week', 'Weeks'),
        ('month', 'Months'),
        ('year', 'Years'),
    ], default='week')
    repeat_type = fields.Selection([
        ('forever', 'Forever'),
        ('until', 'Until'),
    ], default="forever", string="Until")
    repeat_until = fields.Date(string="End Date")
    work_area = fields.Char(string='Work Area')
    planning_maintenance_type = fields.Selection(
        selection='_selection_planning_maintenance_type',
        string='Planning Maintenance Type',
        default='breakdown',
        tracking=True,
    )
    planned_date = fields.Date(string='Planned Date')
    planned_duration = fields.Float(string='Planned Duration (Hours)', default=2.0)
    electrician_required = fields.Boolean(string='Electrician')
    mechanic_required = fields.Boolean(string='Mechanic')
    third_party_vendor = fields.Boolean(string='Third-party Vendor')
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_maintenance_cost_currency_id',
        store=True,
        readonly=True,
        help='Maintenance cost fields use US dollars (USD). Enter amounts in USD.',
    )
    electrical_cost = fields.Monetary(string='Electrical Cost', currency_field='currency_id')
    mechanical_cost = fields.Monetary(string='Mechanical Cost', currency_field='currency_id')
    total_cost = fields.Monetary(
        string='Total Cost', currency_field='currency_id', compute='_compute_total_cost', store=True
    )
    spare_line_ids = fields.One2many(
        'maintenance.request.spare.line', 'request_id', string='Spare Planning', copy=True
    )
    spare_unavailable_warning = fields.Boolean(
        string='Spare Unavailable Warning', compute='_compute_spare_unavailable_warning'
    )
    spare_unavailable_message = fields.Char(
        string='Spare Unavailable Message', compute='_compute_spare_unavailable_warning'
    )
    spare_available_warning = fields.Boolean(
        string='Spare Available Warning', compute='_compute_spare_unavailable_warning'
    )
    spare_pr_pending = fields.Boolean(
        string='Purchase Request Pending',
        compute='_compute_spare_unavailable_warning',
        help='True while at least one out-of-stock spare line has no purchase request yet.',
    )
    spare_total_cost = fields.Monetary(
        string='Total Spares Cost',
        currency_field='currency_id',
        compute='_compute_spares_summary',
        store=True,
    )
    spare_critical_count = fields.Integer(
        string='Critical Items',
        compute='_compute_spares_summary',
        store=True,
    )
    spare_item_count = fields.Integer(
        string='Total Items',
        compute='_compute_spares_summary',
        store=True,
    )
    spare_available_count = fields.Integer(
        string='Available Items',
        compute='_compute_spares_summary',
        store=True,
    )
    spare_shortage_count = fields.Integer(
        string='Shortage Items',
        compute='_compute_spares_summary',
        store=True,
    )
    document_line_ids = fields.One2many(
        'maintenance.request.document',
        'request_id',
        string='Related Documents',
        copy=True,
    )
    manpower_line_ids = fields.One2many(
        'maintenance.request.manpower.line',
        'request_id',
        string='Manpower Assignment',
        copy=True,
    )
    planned_hours = fields.Float(
        string='Planned Hours',
        compute='_compute_planned_hours',
        store=True,
        readonly=False,
        help='Follows Planned Duration from Maintenance Planning; drives delay and the Timeline.',
    )
    actual_hours = fields.Float(string='Actual Hours', default=0.0)
    delay_hours = fields.Float(
        string='Delay Hours',
        compute='_compute_delay_hours',
        store=True,
    )
    responsible_person_id = fields.Many2one(
        'res.users',
        string='Responsible Person',
        compute='_compute_manpower_summary',
        store=True,
    )
    affected_department = fields.Char(string='Affected Department')
    impact_level = fields.Selection(
        [('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        string='Impact Level',
        default='medium',
    )
    execution_status = fields.Selection(
        [('in_progress', 'In Progress'), ('paused', 'Paused'), ('completed', 'Completed')],
        string='Execution Status',
        default='in_progress',
        tracking=True,
    )
    go_no_go_decision = fields.Selection(
        [('go', 'GO'), ('no_go', 'NO GO')],
        string='Operational Status',
        default='no_go',
        tracking=True,
    )
    vibration_level = fields.Selection(
        [('normal', 'Normal'), ('critical_high', 'Critical High')],
        string='Vibration Levels',
        default='normal',
    )
    bearing_temp_state = fields.Selection(
        [('normal', 'Normal'), ('high', 'High')],
        string='Bearing Temp',
        default='normal',
    )
    failure_risk_percent = fields.Float(string='Failure Risk %', default=0.0)
    condition_readings_manual = fields.Boolean(
        string='Manual Condition Readings',
        default=False,
        help='When enabled, vibration/temperature/risk are not auto-updated from request conditions.',
    )
    rca_method = fields.Selection(
        [('five_why', '5 Why'), ('fishbone', 'Fishbone'), ('fault_tree', 'Fault Tree')],
        string='RCA Method',
        default='five_why',
    )
    rca_dashboard_type = fields.Selection(
        selection=[
            ('mom', 'RCA & MOM — Meeting record'),
            ('fishbone', 'Fishbone analysis (6M)'),
            ('why_why', '5 Why analysis'),
            ('agile', 'Agile investigation'),
            ('capa', 'CAPA management'),
            ('dependency', 'Dependency mapping'),
            ('failure_tree', 'Failure tree analysis'),
        ],
        string='Analysis View',
        default='mom',
        help='Choose which root cause analysis screen to open for this work order.',
    )
    rca_line_ids = fields.One2many(
        'maintenance.request.rca.line',
        'request_id',
        string='5 Why Lines',
        copy=True,
    )
    fishbone_summary = fields.Text(string='Fishbone Analysis')
    fault_tree_summary = fields.Text(string='Fault Tree Analysis')
    final_root_cause = fields.Char(string='Final Root Cause')
    mom_discussion = fields.Text(string='MOM Discussion')
    mom_decision = fields.Text(string='MOM Decision')
    mom_action_owner = fields.Char(string='Action Owner')
    corrective_action_ids = fields.One2many(
        'maintenance.request.corrective.action',
        'request_id',
        string='Corrective Actions',
        copy=True,
    )
    actual_vs_plan_percent = fields.Float(
        string='Actual vs Planned %',
        compute='_compute_execution_metrics',
        store=True,
    )
    planned_bar_percent = fields.Float(
        string='Planned Bar %',
        compute='_compute_execution_metrics',
    )
    actual_bar_percent = fields.Float(
        string='Actual Bar %',
        compute='_compute_execution_metrics',
    )
    execution_notes = fields.Text(string='Execution Notes')
    decision_resolution_notes = fields.Text(
        string='Operational Decision Notes',
        help='Notes shown on the workflow timeline after GO / NO-GO resolution.',
    )
    work_order_sequence = fields.Char(
        string='Work Order Reference',
        copy=False,
        help='Optional display code (e.g. WO-2045). If empty, the timeline shows WO- plus the record id.',
    )
    work_order_display = fields.Char(
        string='Work Order',
        compute='_compute_work_order_display',
    )
    maintenance_timeline_total = fields.Monetary(
        string='Timeline Total Cost',
        currency_field='currency_id',
        compute='_compute_maintenance_timeline_total',
        store=True,
    )
    wf_step_issue_done = fields.Boolean(compute='_compute_workflow_timeline_flags')
    wf_step_plan_done = fields.Boolean(compute='_compute_workflow_timeline_flags')
    wf_step_spare_done = fields.Boolean(compute='_compute_workflow_timeline_flags')
    wf_step_assigned_done = fields.Boolean(compute='_compute_workflow_timeline_flags')
    wf_step_execution_done = fields.Boolean(compute='_compute_workflow_timeline_flags')
    wf_step_gonogo_done = fields.Boolean(compute='_compute_workflow_timeline_flags')
    wf_step_rca_done = fields.Boolean(compute='_compute_workflow_timeline_flags')
    wf_step_completed_done = fields.Boolean(compute='_compute_workflow_timeline_flags')
    wf_timeline_highlight_index = fields.Integer(
        string='Timeline Highlight Step',
        compute='_compute_workflow_timeline_flags',
        help='0-based index into the 8 lifecycle steps for the highlighted node on the workflow screen.',
    )
    workflow_timeline_html = fields.Html(
        string='Workflow Timeline',
        compute='_compute_workflow_timeline_html',
        sanitize=False,
    )
    timeline_assigned_html = fields.Html(
        string='Timeline Assigned Team',
        compute='_compute_timeline_assigned_html',
        sanitize=False,
    )
    rca_why_chain_html = fields.Html(
        string='Why–Why Chain',
        compute='_compute_rca_why_chain_html',
        sanitize=False,
    )
    rca_ai_dashboard_html = fields.Html(
        string='AI RCA Dashboard',
        compute='_compute_rca_ai_dashboard_html',
        sanitize=False,
    )
    plant_rca_dashboard_html = fields.Html(
        string='Plant RCA Intelligence',
        compute='_compute_plant_rca_dashboard_html',
        sanitize=False,
    )
    agile_rca_dashboard_html = fields.Html(
        string='Agile RCA Dashboard',
        compute='_compute_agile_rca_dashboard_html',
        sanitize=False,
    )
    why_rca_dashboard_html = fields.Html(
        string='Why-Why RCA Dashboard',
        compute='_compute_why_rca_dashboard_html',
        sanitize=False,
    )
    capa_rca_dashboard_html = fields.Html(
        string='CAPA RCA Dashboard',
        compute='_compute_capa_rca_dashboard_html',
        sanitize=False,
    )
    rca_why_why_screen_html = fields.Html(
        string='Why-Why RCA Screen',
        compute='_compute_rca_why_why_screen_html',
        sanitize=False,
    )
    rca_dependency_screen_html = fields.Html(
        string='Dependency Mapping Screen',
        compute='_compute_rca_dependency_screen_html',
        sanitize=False,
    )
    rca_failure_tree_screen_html = fields.Html(
        string='Failure Tree Screen',
        compute='_compute_rca_failure_tree_screen_html',
        sanitize=False,
    )

    def _rca_equipment_label(self):
        self.ensure_one()
        equipment = self.equipment_id
        if not equipment:
            return None
        label = equipment.display_name
        if equipment.serial_no:
            label = f'{label} ({equipment.serial_no})'
        return label

    def _rca_nav_context(self, form_view_ref=None):
        """Single-screen navigation: avoid stacking rca-mom / ai-plant-rca URL segments."""
        ctx = dict(self.env.context)
        ctx['no_breadcrumbs'] = True
        ctx.pop('params', None)
        if form_view_ref:
            ctx['form_view_ref'] = form_view_ref
            ctx['pm_workflow_step'] = form_view_ref
        ctx['active_id'] = self.id
        ctx['active_ids'] = [self.id]
        return ctx

    @api.model
    def _selection_rca_dashboard_type(self):
        return [
            ('mom', _('RCA & MOM — Meeting record')),
            ('fishbone', _('Fishbone analysis (6M)')),
            ('why_why', _('5 Why analysis')),
            ('agile', _('Agile investigation')),
            ('capa', _('CAPA management')),
            ('dependency', _('Dependency mapping')),
            ('failure_tree', _('Failure tree analysis')),
        ]

    def _rca_dashboard_type_view_map(self):
        return {
            'mom': (
                'maintenance.maintenance_rca_case_form_view',
                _('Root Cause Analysis & MOM'),
            ),
            'fishbone': (
                'maintenance.maintenance_plant_rca_form_view',
                _('Fishbone Root Cause Analysis'),
            ),
            'why_why': (
                'maintenance.maintenance_why_rca_form_view',
                _('5 Why Root Cause Analysis'),
            ),
            'agile': (
                'maintenance.maintenance_agile_rca_form_view',
                _('Agile Investigation Network'),
            ),
            'capa': (
                'maintenance.maintenance_capa_rca_form_view',
                _('CAPA Management'),
            ),
            'dependency': (
                'maintenance.maintenance_rca_dependency_form_view',
                _('Dependency Mapping'),
            ),
            'failure_tree': (
                'maintenance.maintenance_rca_failure_tree_form_view',
                _('Failure Tree Analysis'),
            ),
        }

    def action_open_rca_dashboard_type(self, dashboard_type=None):
        """Open the selected RCA analysis screen for this work order."""
        self.ensure_one()
        dtype = dashboard_type or self.rca_dashboard_type or 'mom'
        view_map = self._rca_dashboard_type_view_map()
        view_xmlid, title = view_map.get(dtype, view_map['mom'])
        if self.rca_dashboard_type != dtype:
            self.rca_dashboard_type = dtype
        return self._rca_method_window_action(view_xmlid, title)

    def action_apply_rca_dashboard_type(self):
        return self.action_open_rca_dashboard_type()

    @api.model
    def action_open_rca_from_list(self, res_id, dashboard_type='mom'):
        """List → form with analysis type from search filter."""
        request = self.browse(res_id).exists()
        if not request:
            return False
        return request.action_open_rca_dashboard_type(dashboard_type)

    # Stored window action per workflow screen. Its id goes into the URL so the
    # browser Back button (and a page reload) reopens that same screen.
    _PM_STEP_ACTION_XMLIDS = {
        'maintenance.hr_equipment_request_view_form': 'maintenance.hr_equipment_request_action',
        'maintenance.maintenance_request_planning_form_view': 'maintenance.maintenance_planning_action',
        'maintenance.maintenance_request_manpower_form_view': 'maintenance.maintenance_manpower_action',
        'maintenance.maintenance_request_spares_form_view': 'maintenance.maintenance_inventory_spares_action',
        'maintenance.maintenance_request_execution_form_view': 'maintenance.maintenance_work_orders_action',
        'maintenance.maintenance_request_workflow_timeline_form_view': 'maintenance.maintenance_workflow_timeline_menu_action',
        'maintenance.maintenance_rca_case_form_view': 'maintenance.maintenance_rca_action',
        'maintenance.maintenance_plant_rca_form_view': 'maintenance.maintenance_plant_rca_action',
        'maintenance.maintenance_why_rca_form_view': 'maintenance.maintenance_why_rca_action',
        'maintenance.maintenance_agile_rca_form_view': 'maintenance.maintenance_agile_rca_action',
        'maintenance.maintenance_capa_rca_form_view': 'maintenance.maintenance_capa_rca_action',
        'maintenance.maintenance_request_nogo_form_view': 'maintenance.maintenance_no_go_dashboard_action',
    }

    def _pm_finalize_step_action(self, action, view_xmlid):
        """Reuse the open screen when the button stays on it; else tag the stored action id.

        Staying on the same screen uses Odoo's soft_reload so no duplicate history
        entry is pushed (Back then goes to the previous screen, not the same one).
        """
        ctx = self.env.context
        if (ctx.get('pm_workflow_step') or ctx.get('form_view_ref')) == view_xmlid:
            return {'type': 'ir.actions.client', 'tag': 'soft_reload'}
        action_xmlid = self._PM_STEP_ACTION_XMLIDS.get(view_xmlid)
        stored = self.env.ref(action_xmlid, raise_if_not_found=False) if action_xmlid else None
        if stored:
            action['id'] = stored.id
        return action

    def _rca_method_window_action(self, view_xmlid, title=None):
        self.ensure_one()
        view = self.env.ref(view_xmlid)
        return self._pm_finalize_step_action({
            'type': 'ir.actions.act_window',
            'name': title or _('Root Cause Analysis'),
            'res_model': 'maintenance.request',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'current',
            'context': self._rca_nav_context(form_view_ref=view_xmlid),
        }, view_xmlid)

    def action_open_rca_mom_full(self):
        """Open notebook-only form to edit RCA fields (no dashboard mix)."""
        self.ensure_one()
        return self._rca_method_window_action(
            'maintenance.maintenance_rca_data_form_view',
            _('Root Cause Analysis & MOM — Data'),
        )

    def action_open_rca_fishbone(self):
        """Fishbone RCA — default RCA dashboard screen."""
        self.ensure_one()
        return self._rca_method_window_action(
            'maintenance.maintenance_rca_case_form_view',
            _('Root Cause Analysis & MOM — Fishbone'),
        )

    def action_open_rca_why_why(self):
        """Why-Why RCA — full dashboard page."""
        self.ensure_one()
        return self.action_open_why_rca_dashboard()

    def action_open_rca_dependency_mapping(self):
        """Dependency mapping — separate full page."""
        self.ensure_one()
        return self._rca_method_window_action(
            'maintenance.maintenance_rca_dependency_form_view',
            _('Root Cause Analysis — Dependency Mapping'),
        )

    def action_open_rca_failure_tree(self):
        """Failure tree — separate full page."""
        self.ensure_one()
        return self._rca_method_window_action(
            'maintenance.maintenance_rca_failure_tree_form_view',
            _('Root Cause Analysis — Failure Tree'),
        )

    @api.depends(
        'rca_line_ids',
        'rca_line_ids.sequence',
        'rca_line_ids.problem_statement',
        'rca_line_ids.cause_statement',
    )
    def _compute_rca_why_chain_html(self):
        for request in self:
            lines = request.rca_line_ids.sorted(lambda l: (l.sequence, l.id))
            if not lines:
                request.rca_why_chain_html = Markup(
                    '<div class="o_pm_rca_why_empty text-muted small">%s</div>'
                    % escape(_('Add 5 Why lines below, or use “Load plant use-case example” in the header.'))
                )
                continue
            blocks = []
            for idx, line in enumerate(lines):
                n = idx + 1
                prob = escape((line.problem_statement or '').strip() or '—')
                cause = escape((line.cause_statement or '').strip() or '—')
                is_last = idx == len(lines) - 1
                tail = (
                    '<div class="o_pm_rca_why_tail"><span class="o_pm_rca_why_badge o_pm_rca_why_badge_root">%s</span> %s</div>'
                    % (escape(_('Root cause candidate')), cause)
                    if is_last
                    else ''
                )
                blocks.append(
                    '<div class="o_pm_rca_why_step">'
                    '<div class="o_pm_rca_why_step_num">%s</div>'
                    '<div class="o_pm_rca_why_step_body">'
                    '<div class="o_pm_rca_why_label">%s</div>'
                    '<div class="o_pm_rca_why_q">%s</div>'
                    '<div class="o_pm_rca_why_arrow">↓</div>'
                    '<div class="o_pm_rca_why_label">%s</div>'
                    '<div class="o_pm_rca_why_a">%s</div>'
                    '%s'
                    '</div></div>'
                    % (
                        n,
                        escape(_('Why?')),
                        prob,
                        escape(_('Because')),
                        cause,
                        tail,
                    )
                )
            request.rca_why_chain_html = (
                Markup('<div class="o_pm_rca_why_chain">')
                + Markup(''.join(blocks))
                + Markup('</div>')
            )

    def _rca_selection_label(self, field_name, value):
        if not value:
            return ''
        field = self._fields[field_name]
        selection = field._description_selection(self.env)
        if selection:
            return dict(selection).get(value, value)
        return value

    def _rca_dashboard_payload(self):
        """Build RCA dashboard from this request, equipment, and team records."""
        self.ensure_one()
        equipment = self.equipment_id
        owner = self.owner_user_id or self.user_id
        currency = self.company_id.currency_id.symbol or '$'

        def fmt_cost(amount):
            if not amount:
                return ''
            if amount >= 1000:
                return f'{currency}{amount / 1000:.1f}k'
            return f'{currency}{amount:,.0f}'

        health_score = ''
        if equipment and equipment.life_consumed_percent:
            health_score = f'{max(0, min(100, int(100 - equipment.life_consumed_percent)))}<small>/100</small>'

        team_domain = [
            ('maintenance_team_id', '=', self.maintenance_team_id.id),
            ('archive', '=', False),
        ] if self.maintenance_team_id else [('id', '=', self.id)]
        dash = '—'
        today = fields.Date.context_today(self)
        team_requests = self.search(team_domain, order='request_date desc, id desc', limit=12)
        if self.id not in team_requests.ids:
            team_requests = (self | team_requests)[:12]
        else:
            team_requests = (self | team_requests.filtered(lambda r: r.id != self.id))[:12]

        def _issue_age_label(req):
            if not req.request_date:
                return dash
            delta = today - req.request_date
            if delta.days <= 0:
                return _('Today')
            if delta.days == 1:
                return _('1d')
            return f'{delta.days}d'

        critical_count = len(team_requests.filtered(
            lambda r: r.impact_level in ('high', 'medium') and not r.stage_id.done
        ))

        rca_done_count = len(self.search(
            team_domain + [('final_root_cause', '!=', False)],
            limit=99,
        ))

        kpis = [
            {'icon': 'health', 'label': 'Vehicle Health', 'value': health_score or dash, 'hint': 'From equipment life consumed %'},
            {'icon': 'alert', 'label': 'Active Critical Alerts', 'value': critical_count or '0', 'hint': 'Open team requests (medium/high)'},
            {'icon': 'clock', 'label': 'MTTR', 'value': f'{self.actual_hours:.1f}<small>hrs</small>' if self.actual_hours else (f'{equipment.mttr}<small>days</small>' if equipment and equipment.mttr else dash), 'hint': 'Mean Time To Repair'},
            {'icon': 'calendar', 'label': 'MTBF', 'value': f'{equipment.mtbf}<small>days</small>' if equipment and equipment.mtbf else dash, 'hint': 'Mean Time Between Failures'},
            {'icon': 'target', 'label': 'Failure Risk', 'value': f'{int(self.failure_risk_percent or 0)}<small>%</small>' if self.failure_risk_percent else dash, 'hint': 'From request sensor data'},
            {'icon': 'gauge', 'label': 'Downtime Risk', 'value': self._rca_selection_label('impact_level', self.impact_level) or dash, 'hint': 'Impact level on request'},
            {'icon': 'dollar', 'label': 'Maintenance Cost', 'value': fmt_cost(self.total_cost) or dash, 'hint': 'Total cost on this request'},
            {'icon': 'network', 'label': 'Root Cause Found', 'value': rca_done_count or '0', 'hint': 'Team requests with RCA completed'},
        ]

        from .maintenance_types import MAINTENANCE_TYPE_EMOJI

        team_issues = []
        for req in team_requests:
            wo = req.work_order_display or req.work_order_sequence or f'WO-{req.id}'
            area = req.work_area or (req.equipment_id.location if req.equipment_id else '')
            equip_name = req.equipment_id.display_name if req.equipment_id else ''
            meta_parts = [p for p in (wo, equip_name, area) if p]
            team_issues.append({
                'id': req.id,
                'name': req.name,
                'emoji': MAINTENANCE_TYPE_EMOJI.get(req.maintenance_type, '🔧'),
                'maintenance_type': req.maintenance_type,
                'type_label': req._rca_selection_label('maintenance_type', req.maintenance_type),
                'meta_line': ' · '.join(meta_parts),
                'age': _issue_age_label(req),
                'impact_level': req.impact_level,
                'impact_label': req._rca_selection_label('impact_level', req.impact_level) or req.impact_level or '—',
            })

        trend_days = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            count = len(self.search(
                team_domain + [
                    ('request_date', '=', day),
                ],
            ))
            trend_days.append({
                'label': day.strftime('%a')[:3],
                'count': count,
            })

        equipment_select = equipment.display_name if equipment else ''
        if equipment and equipment.serial_no:
            equipment_select = f'{equipment_select} / {equipment.serial_no}'

        owner_name = owner.name if owner else ''
        initials = ''.join(w[0].upper() for w in (owner_name or '').split()[:2]) or '—'

        insight = (self.final_root_cause or '').strip()
        if not insight and self.rca_line_ids:
            last = self.rca_line_ids.sorted(lambda l: (l.sequence, l.id))[-1]
            insight = (last.cause_statement or '').strip()

        return {
            'current_request_id': self.id,
            'equipment_select': equipment_select,
            'final_root_cause': self.final_root_cause,
            'fishbone_summary': self.fishbone_summary or '',
            'failure_risk_percent': self.failure_risk_percent or 0.0,
            'impact_label': self._rca_selection_label('impact_level', self.impact_level),
            'cost_label': fmt_cost(self.total_cost),
            'owner_name': owner_name,
            'owner_initials': initials,
            'owner_role': _('Maintenance Lead'),
            'shift_label': _('Morning Shift'),
            'notification_count': critical_count,
            'ai_insight': insight,
            'kpis': kpis,
            'team_issues': team_issues,
            'trend_days': trend_days,
            'corrective_actions': [
                {'name': a.name, 'done': a.done}
                for a in self.corrective_action_ids
            ],
            'vibration_label': self._rca_selection_label('vibration_level', self.vibration_level),
            'bearing_label': self._rca_selection_label('bearing_temp_state', self.bearing_temp_state),
        }

    @api.depends(
        'name',
        'request_date',
        'equipment_id',
        'equipment_id.display_name',
        'equipment_id.serial_no',
        'equipment_id.location',
        'equipment_id.life_consumed_percent',
        'equipment_id.mtbf',
        'equipment_id.mttr',
        'maintenance_team_id',
        'work_area',
        'work_order_sequence',
        'impact_level',
        'maintenance_type',
        'failure_risk_percent',
        'vibration_level',
        'bearing_temp_state',
        'final_root_cause',
        'fishbone_summary',
        'total_cost',
        'actual_hours',
        'stage_id',
        'stage_id.done',
        'user_id',
        'owner_user_id',
        'rca_line_ids',
        'rca_line_ids.cause_statement',
        'corrective_action_ids',
        'corrective_action_ids.name',
        'corrective_action_ids.done',
        'maintenance_type',
        'fishbone_summary',
        'mom_discussion',
        'mom_decision',
        'mom_action_owner',
        'rca_line_ids.problem_statement',
        'rca_required',
    )
    def _rca_mom_completeness_percent(self):
        """RCA & MOM screen score — how much of the meeting record is filled in."""
        self.ensure_one()
        from .plant_rca_dashboard_content import _parse_fishbone_summary

        score = 0
        if (self.final_root_cause or '').strip():
            score += 25
        branches = _parse_fishbone_summary(self.fishbone_summary or '')
        filled = sum(1 for items in branches.values() if items)
        if filled >= 4:
            score += 20
        elif filled >= 2:
            score += 12
        elif filled >= 1:
            score += 6
        if (self.mom_discussion or '').strip():
            score += 15
        if (self.mom_decision or '').strip():
            score += 15
        if (self.mom_action_owner or '').strip():
            score += 10
        actions = self.corrective_action_ids
        if actions:
            score += 8
            done = len(actions.filtered('done'))
            score += min(7, int(round(7 * done / len(actions))))
        if self.rca_line_ids:
            score += min(5, len(self.rca_line_ids))
        return min(100, score)

    def _rca_ai_dashboard_render_payload(self):
        """MOM meeting dashboard — document view (fishbone diagram is on Plant RCA screen)."""
        self.ensure_one()
        from .maintenance_types import MAINTENANCE_TYPE_EMOJI

        payload = self._rca_dashboard_payload()
        completeness = self._rca_mom_completeness_percent()
        type_label = self._rca_selection_label('maintenance_type', self.maintenance_type)
        dash = '—'
        actions = self.corrective_action_ids
        capa_done = len(actions.filtered('done'))
        capa_total = len(actions)
        capa_completion = f'{int(round(100 * capa_done / capa_total))}%' if capa_total else '0%'

        has_root = bool((self.final_root_cause or '').strip())
        has_fishbone = bool((self.fishbone_summary or '').strip())
        if has_root and self.rca_required:
            rca_status_label = _('RCA complete') if completeness >= 80 else _('RCA in progress')
            rca_status_class = 'ok' if completeness >= 80 else 'warn'
        elif self.rca_required:
            rca_status_label = _('RCA required')
            rca_status_class = 'danger'
        else:
            rca_status_label = _('RCA optional')
            rca_status_class = 'info'

        summary_cards = [
            {
                'label': _('Work order'),
                'value': self.work_order_sequence or self.work_order_display or dash,
                'hint': self.stage_id.name if self.stage_id else dash,
                'tone': '',
            },
            {
                'label': _('Repair time'),
                'value': f'{self.actual_hours:.1f} hrs' if self.actual_hours else dash,
                'hint': _('Actual hours on job'),
                'tone': '',
            },
            {
                'label': _('Job cost'),
                'value': payload.get('cost_label') or dash,
                'hint': _('Labor + spares'),
                'tone': '',
            },
            {
                'label': _('CAPA'),
                'value': capa_completion,
                'hint': _('%s of %s actions done') % (capa_done, capa_total) if capa_total else _('No actions yet'),
                'tone': 'tone-ok' if capa_total and capa_done == capa_total else '',
            },
        ]

        checklist = [
            {'label': _('Final root cause documented'), 'done': has_root},
            {'label': _('Fishbone 6M summary recorded'), 'done': has_fishbone},
            {'label': _('MOM discussion recorded'), 'done': bool((self.mom_discussion or '').strip())},
            {'label': _('MOM decision recorded'), 'done': bool((self.mom_decision or '').strip())},
            {'label': _('Action owner assigned'), 'done': bool((self.mom_action_owner or '').strip())},
            {'label': _('Corrective actions listed'), 'done': bool(capa_total)},
        ]

        why_lines = [
            {
                'why': (line.problem_statement or '').strip(),
                'because': (line.cause_statement or '').strip(),
            }
            for line in self.rca_line_ids.sorted(lambda l: (l.sequence, l.id))
            if (line.problem_statement or line.cause_statement)
        ]

        for issue in payload.get('team_issues') or []:
            req = self.browse(issue.get('id'))
            if req:
                issue['maintenance_type'] = req.maintenance_type
                issue['type_label'] = req._rca_selection_label('maintenance_type', req.maintenance_type)
                issue['emoji'] = MAINTENANCE_TYPE_EMOJI.get(req.maintenance_type, '🔧')

        payload.update({
            'completeness_percent': completeness,
            'confidence': completeness,
            'fishbone_summary': self.fishbone_summary or '',
            'mom_discussion': self.mom_discussion or '',
            'mom_decision': self.mom_decision or '',
            'mom_action_owner': self.mom_action_owner or '',
            'problem_title': self.name,
            'work_order_ref': self.work_order_sequence or self.work_order_display or f'WO-{self.id}',
            'work_area': self.work_area or (self.equipment_id.location if self.equipment_id else ''),
            'stage_label': self.stage_id.name if self.stage_id else dash,
            'build_version': '1.0.197',
            'maintenance_type': self.maintenance_type,
            'maintenance_type_label': type_label,
            'scope_note': _('RCA meeting record for this work order'),
            'summary_cards': summary_cards,
            'checklist': checklist,
            'why_lines': why_lines,
            'capa_completion': capa_completion,
            'rca_status_label': rca_status_label,
            'rca_status_class': rca_status_class,
        })
        return payload

    def _compute_rca_ai_dashboard_html(self):
        from .rca_ai_dashboard_content import render_rca_ai_dashboard_from_payload

        for request in self:
            request.rca_ai_dashboard_html = render_rca_ai_dashboard_from_payload(
                request._rca_ai_dashboard_render_payload()
            )

    def _plant_rca_dashboard_payload(self):
        """Plant RCA mockup — all widgets driven from this request and team data."""
        self.ensure_one()
        equipment = self.equipment_id
        owner = self.owner_user_id or self.user_id
        today = fields.Date.context_today(self)
        dash = '—'

        age = dash
        if self.request_date:
            delta = today - self.request_date
            if delta.days < 2:
                hours = max(delta.days * 24, 1)
                age = f'{hours}h'
            else:
                age = f'{delta.days}d'

        team_domain = [
            ('maintenance_team_id', '=', self.maintenance_team_id.id),
            ('archive', '=', False),
        ] if self.maintenance_team_id else [('id', '=', self.id)]
        team_requests = self.search(team_domain, order='request_date desc, id desc', limit=12)
        if self.id not in team_requests.ids:
            team_requests = (self | team_requests)[:12]
        else:
            team_requests = (self | team_requests.filtered(lambda r: r.id != self.id))[:12]

        def _issue_age_label(req):
            if not req.request_date:
                return dash
            delta = today - req.request_date
            if delta.days <= 0:
                return _('Today')
            if delta.days == 1:
                return _('1d')
            return f'{delta.days}d'

        seen_issue_keys = set()
        issues = []
        _issue_emoji = {
            'truck': '🚛', 'battery': '🔋', 'crane': '🏗', 'forklift': '🚜',
            'press': '🏭', 'pump': '⚙', 'motor': '⚡',
        }
        for req in team_requests:
            dedupe_key = req.work_order_sequence or req.id
            if dedupe_key in seen_issue_keys:
                continue
            seen_issue_keys.add(dedupe_key)
            title = (req.name or _('Maintenance issue')).strip()
            if len(title) > 48:
                title = f'{title[:45]}…'
            req_age = _issue_age_label(req)
            name_lower = (req.name or '').lower()
            emoji = '🚛' if 'truck' in name_lower else '🔧'
            for key, icon in _issue_emoji.items():
                if key in name_lower:
                    emoji = icon
                    break
            equip_ref = req.equipment_id.name[:20] if req.equipment_id else ''
            area = (req.work_area or '')[:24]
            subline = f'{equip_ref} · {area}'.strip(' ·') if equip_ref or area else (req.work_order_sequence or '')
            issues.append({
                'id': req.id,
                'name': title,
                'meta': req.work_order_sequence or '',
                'subline': subline,
                'count': len(req.rca_line_ids) or 1,
                'impact': req.impact_level or 'low',
                'age': req_age,
                'emoji': emoji,
                'active': req.id == self.id,
            })
            if len(issues) >= 8:
                break

        alerts = []
        for req in team_requests[:5]:
            if req.stage_id.done:
                continue
            level = 'critical' if req.impact_level == 'high' else 'warn' if req.impact_level == 'medium' else 'info'
            equip_name = req.equipment_id.display_name if req.equipment_id else ''
            text = f'{req.name} - {equip_name}'.strip(' -')
            alerts.append({'level': level, 'text': text})

        mes_active = 'analyze'
        if self.final_root_cause:
            mes_active = 'corrective'
        elif self.execution_status == 'completed':
            mes_active = 'verify'
        elif self.failure_risk_percent and self.failure_risk_percent >= 70:
            mes_active = 'escalate'
        elif self.rca_line_ids:
            mes_active = 'predict'

        currency = self.company_id.currency_id.symbol or '$'
        cost = self.total_cost or 0.0
        if cost >= 1000:
            cost_label = f'~{currency}{cost / 1000:.1f}k'
        elif cost:
            cost_label = f'~{currency}{cost:,.0f}'
        else:
            cost_label = dash

        health_pct = None
        life_consumed = None
        if equipment:
            life_consumed = float(equipment.life_consumed_percent or 0)
            health_pct = max(0, min(100, int(100 - life_consumed)))
        health_score = f'{health_pct}%' if health_pct is not None else dash
        health_display = f'{health_pct}/100' if health_pct is not None else dash

        equipment_select = equipment.display_name if equipment else dash
        if equipment and equipment.serial_no:
            serial = equipment.serial_no.strip()
            if serial and serial not in equipment_select:
                equipment_select = f'{equipment_select} · {serial}'

        owner_name = owner.name if owner else dash
        initials = ''.join(w[0].upper() for w in (owner_name or '').split()[:2]) or dash

        insight = (self.final_root_cause or '').strip()
        if not insight and self.rca_line_ids:
            last = self.rca_line_ids.sorted(lambda l: (l.sequence, l.id))[-1]
            insight = (last.cause_statement or '').strip()

        critical_count = len(team_requests.filtered(
            lambda r: r.impact_level in ('high', 'medium') and not r.stage_id.done
        ))

        capa_lines = self.corrective_action_ids
        capa_done = len(capa_lines.filtered('done'))
        capa_total = len(capa_lines)
        capa_completion = f'{int(round(100 * capa_done / capa_total))}%' if capa_total else dash

        prod_efficiency = dash
        if self.planned_hours:
            pct = min(100.0, self.actual_vs_plan_percent or 0.0)
            prod_efficiency = f'{int(round(pct))}%'

        delay_min = int(round((self.delay_hours or 0.0) * 60))
        transport_delay = f'{delay_min}m' if delay_min else dash

        daily_output = dash
        if self.planned_hours:
            daily_output = f'{self.planned_hours:.0f}h planned'
        elif self.actual_hours:
            daily_output = f'{self.actual_hours:.1f}h actual'

        week_start = today - timedelta(days=6)
        week_requests = self.search(
            team_domain + [('request_date', '>=', week_start), ('request_date', '<=', today)],
        )
        high_week = len(week_requests.filtered(lambda r: r.impact_level == 'high'))
        slab_rejection = (
            f'{(100.0 * high_week / len(week_requests)):.1f}%'
            if week_requests else dash
        )

        trend_days = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            count = len(self.search(team_domain + [('request_date', '=', day)]))
            trend_days.append({'label': day.strftime('%a')[:3], 'count': count})

        failure_risk = int(max(0, min(100, round(self.failure_risk_percent or 0))))
        has_root_cause = bool((self.final_root_cause or '').strip())
        if has_root_cause:
            confidence = max(55, min(97, 100 - failure_risk)) if failure_risk else 85
        else:
            confidence = max(0, min(100, 100 - failure_risk)) if failure_risk else 0

        fishbone_text = (self.fishbone_summary or '').strip()
        if not fishbone_text and self.rca_line_ids:
            parts = []
            for line in self.rca_line_ids.sorted(lambda l: (l.sequence, l.id)):
                cause = (line.cause_statement or '').strip()
                if cause:
                    parts.append(f'Method: {cause}')
            fishbone_text = '; '.join(parts[:6])

        repair_hours = dash
        if self.actual_hours:
            repair_hours = f'{self.actual_hours:.1f} h'
        elif self.planned_hours:
            repair_hours = f'{self.planned_hours:.0f} h planned'

        stage_label = self.stage_id.name if self.stage_id else dash

        impact_label = self._rca_selection_label('impact_level', self.impact_level) or dash
        downtime_risk_label = impact_label
        if failure_risk >= 70:
            downtime_risk_label = _('High')
        elif failure_risk >= 40:
            downtime_risk_label = _('Medium')
        elif failure_risk:
            downtime_risk_label = _('Low')

        kpis = [
            {
                'label': 'Critical rate %',
                'value': slab_rejection,
                'hint': 'High-impact share (team, 7 days)',
                'class': 'kpi-alert',
                'tone': 'danger',
            },
            {
                'label': 'Prod. efficiency',
                'value': prod_efficiency,
                'hint': 'Actual vs planned hours',
                'class': 'kpi-target',
                'tone': 'ok',
            },
            {
                'label': 'Active critical',
                'value': str(critical_count),
                'hint': 'Open high/medium impact',
                'class': 'kpi-alert',
                'tone': 'danger' if critical_count else 'ok',
            },
            {
                'label': 'AI accuracy',
                'value': f'{confidence}%',
                'hint': 'Confidence from root cause + risk',
                'class': 'kpi-target',
                'tone': 'ok',
            },
            {
                'label': 'Daily output',
                'value': daily_output,
                'hint': 'Planned or actual hours',
                'class': 'kpi-calendar',
                'tone': 'ok',
            },
            {
                'label': 'Downtime risk',
                'value': downtime_risk_label,
                'hint': f'Failure risk {failure_risk}%' if failure_risk else 'Impact level',
                'class': 'kpi-gauge',
                'tone': 'danger' if failure_risk >= 70 else 'warn' if failure_risk >= 40 else 'ok',
            },
            {
                'label': 'Transport delay',
                'value': transport_delay,
                'hint': 'Delay hours on request',
                'class': 'kpi-clock',
                'tone': 'warn' if delay_min else 'ok',
            },
            {
                'label': 'CAPA completion',
                'value': capa_completion,
                'hint': 'Corrective actions done',
                'class': 'kpi-network',
                'tone': 'ok',
            },
        ]

        return {
            'current_request_id': self.id,
            'problem_title': (self.name or _('Maintenance issue'))[:60],
            'confidence': confidence,
            'stage_label': stage_label,
            'kpis': kpis,
            'failure_risk_percent': failure_risk,
            'incident_id': self.work_order_sequence or f'PL-{self.id:04d}',
            'plant_area': self.work_area or (equipment.location if equipment else dash),
            'equipment': equipment_select,
            'equipment_select': equipment_select,
            'reported_by': owner_name,
            'incident_age': age,
            'shift_label': _('Shift B Active'),
            'health_score': health_score,
            'health_display': health_display,
            'downtime_risk_label': downtime_risk_label,
            'fishbone_hub_title': (self.name or _('Maintenance failure'))[:48],
            'build_version': '1.0.74',
            'health_bar_percent': health_pct if health_pct is not None else 0,
            'owner_role': _('Maintenance Lead'),
            'slab_rejection': slab_rejection,
            'prod_efficiency': prod_efficiency,
            'critical_count': critical_count,
            'daily_output': daily_output,
            'transport_delay': transport_delay,
            'capa_completion': capa_completion,
            'impact_label': self._rca_selection_label('impact_level', self.impact_level) or dash,
            'cost_label': cost_label,
            'final_root_cause': self.final_root_cause,
            'fishbone_summary': fishbone_text,
            'ai_insight': insight,
            'owner_name': owner_name,
            'owner_initials': initials,
            'notification_count': critical_count,
            'team_issues': issues,
            'live_alerts': alerts,
            'trend_days': trend_days,
            'mes_active_step': mes_active,
            'corrective_actions': [
                {'name': a.name, 'done': a.done} for a in self.corrective_action_ids
            ],
        }

    @api.depends(
        'name',
        'request_date',
        'equipment_id',
        'equipment_id.display_name',
        'equipment_id.serial_no',
        'equipment_id.location',
        'equipment_id.life_consumed_percent',
        'work_area',
        'work_order_sequence',
        'impact_level',
        'failure_risk_percent',
        'fishbone_summary',
        'final_root_cause',
        'total_cost',
        'planned_hours',
        'actual_hours',
        'delay_hours',
        'actual_vs_plan_percent',
        'execution_status',
        'stage_id',
        'stage_id.name',
        'maintenance_team_id',
        'maintenance_type',
        'stage_id',
        'stage_id.done',
        'user_id',
        'owner_user_id',
        'rca_line_ids',
        'rca_line_ids.cause_statement',
        'corrective_action_ids',
        'corrective_action_ids.name',
        'corrective_action_ids.done',
    )
    def _compute_plant_rca_dashboard_html(self):
        from .plant_rca_dashboard_content import render_plant_rca_dashboard_html

        for request in self:
            request.plant_rca_dashboard_html = render_plant_rca_dashboard_html(
                request._plant_rca_dashboard_payload()
            )

    def _agile_board_stage(self):
        self.ensure_one()
        if self.stage_id.done:
            return 'done'
        stage_name = (self.stage_id.name or '').lower()
        if 'new' in stage_name:
            return 'backlog'
        if 'progress' in stage_name:
            return 'doing'
        if 'repair' in stage_name:
            return 'review'
        return 'doing'

    def _agile_sprint_active_step(self):
        self.ensure_one()
        if self.stage_id.done:
            return 'close'
        if self.execution_status == 'completed' and (self.final_root_cause or '').strip():
            return 'review'
        if (self.final_root_cause or '').strip() and self.corrective_action_ids:
            if not all(self.corrective_action_ids.mapped('done')):
                return 'capa'
            return 'verify'
        if (self.final_root_cause or '').strip():
            return 'review'
        if self.rca_line_ids:
            return 'analyze'
        if self.failure_risk_percent and self.failure_risk_percent >= 70:
            return 'escalate'
        return 'detect'

    def _agile_rca_dashboard_payload(self):
        """Agile RCA mockup — investigation network from fishbone + CAPA."""
        self.ensure_one()
        dash = '—'
        today = fields.Date.context_today(self)
        equipment = self.equipment_id
        owner = self.owner_user_id or self.user_id

        age = dash
        if self.request_date:
            delta = today - self.request_date
            age = f'{delta.days}d' if delta.days >= 2 else f'{max(delta.days * 24, 1)}h'

        team_domain = [
            ('maintenance_team_id', '=', self.maintenance_team_id.id),
            ('archive', '=', False),
        ] if self.maintenance_team_id else [('id', '=', self.id)]
        team_requests = self.search(team_domain, order='request_date desc, id desc', limit=30)
        open_requests = team_requests.filtered(lambda r: not r.stage_id.done)

        failure_risk = int(max(0, min(100, round(self.failure_risk_percent or 0))))
        has_root = bool((self.final_root_cause or '').strip())
        confidence = max(55, min(97, 100 - failure_risk)) if has_root and failure_risk else (
            max(0, 100 - failure_risk) if failure_risk else 0
        )

        capa_lines = self.corrective_action_ids
        capa_done = len(capa_lines.filtered('done'))
        capa_total = len(capa_lines)
        capa_pct = int(round(100 * capa_done / capa_total)) if capa_total else 72

        escalated = len(team_requests.filtered(
            lambda r: r.impact_level == 'high' and not r.stage_id.done
        ))
        prev_esc = max(0, escalated - 1)
        esc_trend = f'{escalated - prev_esc:+d}' if escalated != prev_esc else '0'

        downtime = dash
        if self.actual_hours:
            downtime = f'{self.actual_hours:.1f}h'
        elif self.planned_hours:
            downtime = f'{self.planned_hours:.0f}h'

        risk_label = self._rca_selection_label('impact_level', self.impact_level) or 'Medium'
        risk_stable = 'Stable' if self.impact_level != 'high' else 'Elevated'

        kpis = [
            {
                'label': 'Active investigations',
                'value': len(open_requests),
                'trend': '+2',
                'trend_cls': 'up',
            },
            {
                'label': 'Escalated issues',
                'value': escalated,
                'trend': esc_trend,
                'trend_cls': 'down' if escalated < prev_esc else 'up',
            },
            {
                'label': 'Sprint CAPA completion',
                'value': f'{capa_pct}%',
                'trend': '+5%',
                'trend_cls': 'up',
            },
            {
                'label': 'AI prediction accuracy',
                'value': f'{confidence}%',
                'trend': '+1.2%',
                'trend_cls': 'up',
            },
            {
                'label': 'Manufacturing downtime',
                'value': downtime,
                'trend': '-0.4h',
                'trend_cls': 'up',
            },
            {
                'label': 'Production risk index',
                'value': risk_label,
                'trend': risk_stable,
                'trend_cls': 'warn' if self.impact_level == 'high' else 'neutral',
            },
        ]

        week_start = today - timedelta(days=6)
        velocity_days = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            count = len(self.search(
                team_domain + [('request_date', '=', day)],
            ))
            velocity_days.append({'label': day.strftime('%a')[:3], 'count': count})

        fishbone_text = (self.fishbone_summary or '').strip()
        if not fishbone_text and self.rca_line_ids:
            parts = []
            for line in self.rca_line_ids.sorted(lambda l: (l.sequence, l.id)):
                cause = (line.cause_statement or '').strip()
                if cause:
                    parts.append(f'Method: {cause}')
            fishbone_text = '; '.join(parts[:6])

        severity_map = {
            'high': (_('Critical'), 'critical'),
            'medium': (_('High'), 'high'),
            'low': (_('Medium'), 'med'),
        }
        severity_label, severity_class = severity_map.get(
            self.impact_level or 'low', (_('Medium'), 'med')
        )

        owner_name = owner.name if owner else dash
        initials = ''.join(w[0].upper() for w in (owner_name or '').split()[:2]) or '—'
        sprint_num = (self.id % 24) + 1

        return {
            'current_request_id': self.id,
            'build_version': '1.0.76',
            'confidence': confidence,
            'final_root_cause': self.final_root_cause,
            'fishbone_summary': fishbone_text,
            'is_high_impact': self.impact_level == 'high',
            'incident_id': self.work_order_sequence or f'RCA-{self.id:04d}',
            'agile_ticket': f'AG-{self.id:04d}',
            'sprint_name': f'Sprint {sprint_num}',
            'sprint_label': _('Sprint %s active') % sprint_num,
            'sprint_progress': capa_pct,
            'issue_title': (self.name or _('Maintenance issue'))[:42],
            'plant_area': self.work_area or (
                equipment.location if equipment else dash
            ),
            'incident_age': age,
            'board_active': self._agile_board_stage(),
            'severity_label': severity_label,
            'severity_class': severity_class,
            'velocity_days': velocity_days,
            'kpis': kpis,
            'owner_name': owner_name,
            'owner_initials': initials,
            'owner_role': _('Scrum Master'),
            'notification_count': escalated,
            'sprint_active_step': self._agile_sprint_active_step(),
            'corrective_actions': [
                {'name': a.name, 'done': a.done} for a in self.corrective_action_ids
            ],
        }

    @api.depends(
        'name',
        'request_date',
        'equipment_id',
        'equipment_id.location',
        'work_area',
        'work_order_sequence',
        'impact_level',
        'failure_risk_percent',
        'fishbone_summary',
        'final_root_cause',
        'planned_hours',
        'actual_hours',
        'execution_status',
        'stage_id',
        'stage_id.name',
        'stage_id.done',
        'maintenance_team_id',
        'user_id',
        'owner_user_id',
        'rca_line_ids',
        'rca_line_ids.cause_statement',
        'corrective_action_ids',
        'corrective_action_ids.name',
        'corrective_action_ids.done',
    )
    def _compute_agile_rca_dashboard_html(self):
        from .agile_rca_dashboard_content import render_agile_rca_dashboard_html

        for request in self:
            request.agile_rca_dashboard_html = render_agile_rca_dashboard_html(
                request._agile_rca_dashboard_payload()
            )

    def _why_workflow_step(self):
        self.ensure_one()
        if self.stage_id.done:
            return 'close'
        if (self.final_root_cause or '').strip():
            if self.corrective_action_ids and not all(self.corrective_action_ids.mapped('done')):
                return 'corrective'
            if self.impact_level == 'high':
                return 'escalate'
            return 'root'
        if self.rca_line_ids:
            return 'why'
        return 'detect'

    def _build_why_lines_for_display(self):
        """Return 5-Why chain from saved lines, or auto-build from fishbone/root cause."""
        self.ensure_one()
        from .plant_rca_dashboard_content import _parse_fishbone_summary

        saved = [
            {
                'problem': (line.problem_statement or '').strip(),
                'cause': (line.cause_statement or '').strip(),
            }
            for line in self.rca_line_ids.sorted(lambda l: (l.sequence, l.id))
            if (line.problem_statement or line.cause_statement)
        ]
        if saved:
            return saved, False

        branches = _parse_fishbone_summary(self.fishbone_summary or '')
        if not any(branches.values()):
            return [], False

        title = (self.name or _('Equipment failure')).strip()
        machine = '; '.join(branches.get('Machine', []))
        material = '; '.join(branches.get('Material', []))
        method = '; '.join(branches.get('Method', []))
        manpower = '; '.join(branches.get('Manpower', []))
        environment = '; '.join(branches.get('Environment', []))

        chain = [{
            'problem': _('Why did %s occur?') % title,
            'cause': _('Equipment tripped due to unstable discharge pressure and high discharge temperature.'),
        }]
        if machine:
            chain.append({
                'problem': _('Why did discharge temperature rise / mechanical stress increase?'),
                'cause': machine,
            })
        if material:
            chain.append({
                'problem': _('Why was discharge pressure unstable?'),
                'cause': material,
            })
        if environment and len(chain) < 5:
            chain.append({
                'problem': _('Why did cooling/airflow degrade?'),
                'cause': environment,
            })
        if method:
            chain.append({
                'problem': _('Why was the fault not detected before breakdown?'),
                'cause': method,
            })
        if manpower and len(chain) < 5:
            chain.append({
                'problem': _('Why was downtime extended?'),
                'cause': manpower,
            })
        return chain[:5], True

    def _why_rca_dashboard_payload(self):
        """Why-Why RCA dashboard — chain from rca_line_ids."""
        from .why_rca_dashboard_content import _parse_fishbone_counts

        self.ensure_one()
        dash = '—'
        today = fields.Date.context_today(self)
        equipment = self.equipment_id
        owner = self.owner_user_id or self.user_id

        team_domain = [
            ('maintenance_team_id', '=', self.maintenance_team_id.id),
            ('archive', '=', False),
        ] if self.maintenance_team_id else [('id', '=', self.id)]
        team_requests = self.search(team_domain, order='request_date desc, id desc', limit=12)

        seen = set()
        issues = []
        for req in team_requests:
            key = req.work_order_sequence or req.id
            if key in seen:
                continue
            seen.add(key)
            title = (req.name or _('Issue'))[:48]
            issues.append({
                'id': req.id,
                'name': title,
                'count': len(req.rca_line_ids) or 1,
            })
            if len(issues) >= 8:
                break

        failure_risk = int(max(0, min(100, round(self.failure_risk_percent or 0))))
        has_root = bool((self.final_root_cause or '').strip())
        confidence = max(55, min(97, 100 - failure_risk)) if has_root and failure_risk else (
            max(0, 100 - failure_risk) if failure_risk else 0
        )

        capa_lines = self.corrective_action_ids
        capa_done = len(capa_lines.filtered('done'))
        capa_total = len(capa_lines)
        capa_pct = int(round(100 * capa_done / capa_total)) if capa_total else 0

        critical_count = len(team_requests.filtered(
            lambda r: r.impact_level in ('high', 'medium') and not r.stage_id.done
        ))

        week_start = today - timedelta(days=6)
        week_requests = self.search(
            team_domain + [('request_date', '>=', week_start), ('request_date', '<=', today)],
        )
        high_week = len(week_requests.filtered(lambda r: r.impact_level == 'high'))
        slab_pct = (
            f'{(100.0 * high_week / len(week_requests)):.1f}%'
            if week_requests else dash
        )

        prod_eff = dash
        if self.planned_hours:
            prod_eff = f'{min(100.0, self.actual_vs_plan_percent or 0):.1f}%'

        health_pct = None
        if equipment:
            health_pct = max(0, min(100, int(100 - float(equipment.life_consumed_percent or 0))))

        currency = self.company_id.currency_id.symbol or '$'
        cost = self.total_cost or 0.0
        if cost >= 1000:
            cost_label = f'~{currency}{cost / 1000:.1f}k'
        elif cost:
            cost_label = f'~{currency}{cost:,.0f}'
        else:
            cost_label = dash

        trend_days = []
        max_count = 0
        max_idx = 0
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            count = len(self.search(team_domain + [('request_date', '=', day)]))
            trend_days.append({'label': day.strftime('%a')[:3], 'count': count})
            if count >= max_count:
                max_count = count
                max_idx = len(trend_days) - 1

        fb_counts = _parse_fishbone_counts((self.fishbone_summary or '').strip())
        if not fb_counts and self.rca_line_ids:
            fb_counts = {'RCA factors': len(self.rca_line_ids)}
        total_fb = sum(fb_counts.values()) or 1
        defect_rows = [
            {'label': f'{k} zone' if 'zone' not in k.lower() else k, 'pct': int(round(100 * v / total_fb))}
            for k, v in sorted(fb_counts.items(), key=lambda x: -x[1])[:4]
        ]

        why_lines, why_auto = self._build_why_lines_for_display()
        why_depth = len(why_lines)
        why_confidence = min(97, 40 + why_depth * 11) if why_lines else (
            max(55, min(97, 100 - failure_risk)) if has_root and failure_risk else 0
        )

        heatmap = []
        levels = ['low', 'med', 'high', 'med', 'low', 'high', 'med']
        for hour, lvl in zip(range(6, 13), levels):
            heatmap.append({'label': f'{hour:02d}:00', 'level': lvl})

        alerts = []
        for req in team_requests[:4]:
            if req.stage_id.done:
                continue
            level = 'critical' if req.impact_level == 'high' else 'warn'
            alerts.append({
                'level': level,
                'text': f'{req.name}'[:42],
                'time': '2m ago' if req.id == self.id else '15m ago',
            })

        owner_name = owner.name if owner else dash
        initials = ''.join(w[0].upper() for w in (owner_name or '').split()[:2]) or '—'

        return {
            'current_request_id': self.id,
            'build_version': '1.0.78',
            'confidence': why_confidence,
            'final_root_cause': self.final_root_cause,
            'incident_title': self.name,
            'why_lines': why_lines,
            'why_auto_generated': why_auto,
            'why_depth': why_depth,
            'failure_risk_percent': failure_risk,
            'cost_label': cost_label,
            'health_display': f'{health_pct}/100' if health_pct is not None else dash,
            'health_bar_percent': health_pct or 0,
            'shift_label': _('Morning Shift'),
            'owner_name': owner_name,
            'owner_initials': initials,
            'owner_role': _('Plant Director'),
            'notification_count': critical_count,
            'why_workflow_step': self._why_workflow_step(),
            'team_issues': issues,
            'heatmap_hours': heatmap,
            'trend_days': trend_days,
            'trend_anomaly_idx': max_idx if max_count else -1,
            'defect_rows': defect_rows,
            'live_alerts': alerts,
            'kpis': [
                {'label': 'Critical rate %', 'value': slab_pct, 'trend': '-0.4%', 'trend_cls': 'up'},
                {'label': 'Prod. efficiency', 'value': prod_eff, 'trend': '+1.2%', 'trend_cls': 'up'},
                {'label': 'Why depth', 'value': f'{why_depth}/5', 'trend': f'{why_confidence}%', 'trend_cls': 'up'},
                {'label': 'Active critical', 'value': str(critical_count), 'trend': '-1', 'trend_cls': 'up'},
                {'label': 'Daily output', 'value': (
                    f'{self.planned_hours:.0f}h' if self.planned_hours else dash
                ), 'trend': 'Steady', 'trend_cls': 'neutral'},
                {'label': 'Downtime risk', 'value': (
                    self._rca_selection_label('impact_level', self.impact_level) or dash
                ), 'trend': 'Elevated', 'trend_cls': 'warn'},
                {'label': 'Quality compliance', 'value': (
                    f'{health_pct}%' if health_pct is not None else dash
                ), 'trend': '+0.2%', 'trend_cls': 'up'},
                {'label': 'CAPA completion', 'value': f'{capa_pct}%', 'trend': '+4%', 'trend_cls': 'up'},
            ],
            'corrective_actions': [
                {'name': a.name, 'done': a.done} for a in self.corrective_action_ids
            ],
        }

    @api.depends(
        'name',
        'request_date',
        'equipment_id',
        'equipment_id.life_consumed_percent',
        'work_order_sequence',
        'impact_level',
        'failure_risk_percent',
        'fishbone_summary',
        'final_root_cause',
        'planned_hours',
        'actual_hours',
        'actual_vs_plan_percent',
        'total_cost',
        'stage_id',
        'stage_id.done',
        'maintenance_team_id',
        'user_id',
        'owner_user_id',
        'rca_line_ids',
        'rca_line_ids.sequence',
        'rca_line_ids.problem_statement',
        'rca_line_ids.cause_statement',
        'corrective_action_ids',
        'corrective_action_ids.name',
        'corrective_action_ids.done',
    )
    def _compute_why_rca_dashboard_html(self):
        from .why_rca_dashboard_content import render_why_rca_dashboard_html

        for request in self:
            request.why_rca_dashboard_html = render_why_rca_dashboard_html(
                request._why_rca_dashboard_payload()
            )

    def action_open_why_rca_dashboard(self):
        """Open Why-Why RCA full dashboard for THIS request (never the list)."""
        self.ensure_one()
        return self._rca_method_window_action(
            'maintenance.maintenance_why_rca_form_view',
            _('AI Why-Why Root Cause Analysis'),
        )

    def _capa_workflow_step(self):
        self.ensure_one()
        if self.stage_id.done:
            return 'close'
        capa = self.corrective_action_ids
        capa_done = capa and all(capa.mapped('done'))
        capa_open = capa and not capa_done
        if capa_done and self.go_no_go_decision == 'go':
            return 'audit' if self.execution_status == 'completed' else 'verify'
        if capa_open and any(capa.mapped('done')):
            return 'implement'
        if (self.final_root_cause or '').strip() and capa:
            return 'approve'
        if self.rca_line_ids or (self.fishbone_summary or '').strip():
            return 'analyze'
        return 'detect'

    def _capa_lifecycle_indices(self):
        """Map workflow step to timeline column indices (top, bottom, rail)."""
        self.ensure_one()
        step = self._capa_workflow_step()
        mapping = {
            'detect': (0, 3, 0),
            'analyze': (1, 3, 1),
            'approve': (2, 3, 1),
            'implement': (3, 2, 2),
            'verify': (3, 1, 3),
            'audit': (3, 0, 3),
            'close': (3, 0, 3),
        }
        return mapping.get(step, (1, 3, 1))

    def _capa_rca_dashboard_payload(self):
        """CAPA management dashboard from corrective actions and RCA fields."""
        from .capa_rca_dashboard_content import _classification_rows, _parse_fishbone_counts

        self.ensure_one()
        dash = '—'
        today = fields.Date.context_today(self)
        equipment = self.equipment_id
        owner = self.owner_user_id or self.user_id

        team_domain = [
            ('maintenance_team_id', '=', self.maintenance_team_id.id),
            ('archive', '=', False),
        ] if self.maintenance_team_id else [('id', '=', self.id)]
        team_requests = self.search(team_domain, order='request_date desc, id desc', limit=20)

        seen = set()
        issues = []
        for req in team_requests:
            key = req.work_order_sequence or req.id
            if key in seen:
                continue
            seen.add(key)
            capa_count = len(req.corrective_action_ids) or (
                1 if (req.final_root_cause or '').strip() else 0
            )
            issues.append({
                'id': req.id,
                'name': (req.name or _('Issue'))[:42],
                'count': capa_count,
            })
            if len(issues) >= 8:
                break

        failure_risk = int(max(0, min(100, round(self.failure_risk_percent or 0))))
        has_root = bool((self.final_root_cause or '').strip())
        confidence = max(55, min(98, 100 - failure_risk)) if has_root else (
            max(0, 100 - failure_risk) if failure_risk else 0
        )

        capa_lines = self.corrective_action_ids
        capa_done = len(capa_lines.filtered('done'))
        capa_total = len(capa_lines)
        capa_open = capa_total - capa_done
        capa_pct = int(round(100 * capa_done / capa_total)) if capa_total else 0

        open_capa_team = 0
        overdue_capa = 0
        resolved_count = 0
        escalations = 0
        board_open = board_review = board_progress = board_verify = 0
        week_start = today - timedelta(days=6)

        for req in team_requests:
            lines = req.corrective_action_ids
            if lines:
                open_capa_team += len(lines.filtered(lambda l: not l.done))
                if req.request_date and req.request_date < today - timedelta(days=7):
                    overdue_capa += len(lines.filtered(lambda l: not l.done))
            if req.stage_id.done or (lines and all(lines.mapped('done'))):
                resolved_count += 1
            if req.impact_level == 'high' and lines and not all(lines.mapped('done')):
                escalations += 1
            if not lines:
                continue
            if not all(lines.mapped('done')):
                board_open += 1
                if (req.final_root_cause or '').strip():
                    board_review += 1
                if req.execution_status == 'in_progress':
                    board_progress += 1
                elif req.go_no_go_decision == 'go':
                    board_verify += 1

        week_requests = self.search(
            team_domain + [('request_date', '>=', week_start), ('request_date', '<=', today)],
        )
        high_week = len(week_requests.filtered(lambda r: r.impact_level == 'high'))
        reject_pct = (
            f'{(100.0 * high_week / len(week_requests)):.1f}%'
            if week_requests else dash
        )

        health_pct = None
        if equipment:
            health_pct = max(0, min(100, int(100 - float(equipment.life_consumed_percent or 0))))

        currency = self.company_id.currency_id.symbol or '$'
        cost = self.total_cost or 0.0
        if cost >= 1000:
            cost_label = f'~{currency}{cost / 1000:.1f}k/wk'
        elif cost:
            cost_label = f'~{currency}{cost:,.0f}'
        else:
            cost_label = dash

        trend_days = []
        max_count = 0
        max_idx = 0
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            count = len(self.search(team_domain + [('request_date', '=', day)]))
            trend_days.append({'label': day.strftime('%a')[:3], 'count': count})
            if count >= max_count:
                max_count = count
                max_idx = len(trend_days) - 1

        fb_counts = _parse_fishbone_counts((self.fishbone_summary or '').strip())
        if not fb_counts and self.rca_line_ids:
            fb_counts = {'RCA factors': len(self.rca_line_ids)}

        due = self.request_date + timedelta(days=7) if self.request_date else None
        due_label = due.strftime('%b %d, %Y') if due else dash
        if due and due < today and capa_open:
            due_label = f'{due_label} (overdue)'

        impact = self.impact_level or 'medium'
        severity_map = {
            'high': (_('Critical'), 'critical'),
            'medium': (_('High'), 'high'),
            'low': (_('Medium'), 'med'),
        }
        severity_label, severity_cls = severity_map.get(impact, (_('Medium'), 'med'))

        risk_level = _('High') if failure_risk >= 70 else (_('Medium') if failure_risk >= 40 else _('Low'))
        audit_status = _('At risk') if capa_open and impact == 'high' else (
            _('Compliant') if capa_total and capa_done == capa_total else _('Pending')
        )
        esc_priority = _('Immediate') if impact == 'high' and capa_open else _('Normal')

        preventive = ' '.join(
            a.name for a in capa_lines.filtered(lambda l: not l.done)[:2]
        ) or (self.mom_decision or '')[:120]

        insight_parts = []
        if self.final_root_cause:
            insight_parts.append(self.final_root_cause)
        if equipment:
            insight_parts.append(_('Equipment: %s') % equipment.display_name)
        if failure_risk:
            insight_parts.append(_('Failure risk %s%%.') % failure_risk)
        ai_insight = ' '.join(insight_parts) or self.name or dash

        capa_id = f'CP-{today.year}-{self.id}'
        incident_id = f'RCA-{self.id}'

        alerts = []
        if capa_open and due and due < today:
            alerts.append({
                'level': 'critical',
                'text': _('Overdue CAPA (%s)') % capa_id,
                'time': _('Just now'),
            })
        for req in team_requests[:3]:
            if req.id == self.id and alerts:
                continue
            if req.stage_id.done:
                continue
            level = 'critical' if req.impact_level == 'high' else 'warn'
            alerts.append({
                'level': level,
                'text': (req.name or '')[:42],
                'time': '4m ago' if level == 'warn' else '12m ago',
            })

        owner_name = self.mom_action_owner or (owner.name if owner else dash)
        initials = ''.join(w[0].upper() for w in (owner_name or '').split()[:2]) or '—'

        capa_step = self._capa_workflow_step()
        top_idx, bottom_idx, rail_idx = self._capa_lifecycle_indices()
        rail_percent = int(round(100 * (rail_idx + 1) / 4))
        preventive_bullets = [
            a.name for a in capa_lines.filtered(lambda l: not l.done)
        ][:3]
        if not preventive_bullets and (self.mom_decision or '').strip():
            preventive_bullets = [
                s.strip()
                for s in (self.mom_decision or '').replace(';', '.').split('.')
                if len(s.strip()) > 8
            ][:3]

        return {
            'current_request_id': self.id,
            'build_version': '1.0.81',
            'confidence': confidence,
            'final_root_cause': self.final_root_cause,
            'hub_title': self.name,
            'ai_insight': ai_insight,
            'preventive_hint': preventive,
            'failure_risk_percent': failure_risk,
            'risk_level': risk_level,
            'cost_label': cost_label,
            'audit_status': audit_status,
            'escalation_priority': esc_priority,
            'health_display': f'{health_pct}/100' if health_pct is not None else dash,
            'health_bar_percent': health_pct or 0,
            'shift_label': _('Morning Shift'),
            'owner_name': owner_name,
            'owner_initials': initials,
            'owner_role': _('QA Director'),
            'notification_count': escalations or overdue_capa,
            'capa_workflow_step': capa_step,
            'lifecycle_top_idx': top_idx,
            'lifecycle_bottom_idx': bottom_idx,
            'lifecycle_rail_idx': rail_idx,
            'lifecycle_rail_percent': rail_percent,
            'lifecycle_close_muted': capa_step not in ('audit', 'close'),
            'preventive_bullets': preventive_bullets,
            'capa_id': capa_id,
            'incident_id': incident_id,
            'project_label': self.work_area or (
                equipment.category_id.name if equipment and equipment.category_id else dash
            ),
            'severity_label': severity_label,
            'severity_cls': severity_cls,
            'assigned_dept': self.affected_department or (
                self.maintenance_team_id.name if self.maintenance_team_id else dash
            ),
            'due_date_label': due_label,
            'team_issues': issues,
            'classification_rows': _classification_rows(fb_counts),
            'trend_days': trend_days,
            'trend_anomaly_idx': max_idx if max_count else -1,
            'status_board': [
                {'label': 'Open', 'count': board_open or open_capa_team, 'cls': 'st-open'},
                {'label': 'In review', 'count': board_review, 'cls': 'st-review'},
                {'label': 'In progress', 'count': board_progress, 'cls': 'st-progress'},
                {'label': 'Verify', 'count': board_verify, 'cls': 'st-verify'},
            ],
            'live_alerts': alerts,
            'kpis': [
                {'label': 'Open CAPAs', 'value': str(open_capa_team or capa_open), 'trend': '-2', 'trend_cls': 'up'},
                {'label': 'Overdue actions', 'value': str(overdue_capa), 'trend': '+1', 'trend_cls': 'down'},
                {'label': 'Resolved issues', 'value': str(resolved_count), 'trend': '+12', 'trend_cls': 'up'},
                {'label': 'Critical rate %', 'value': reject_pct, 'trend': '+2.4%', 'trend_cls': 'up'},
                {'label': 'Quality imp.', 'value': f'{capa_pct}%', 'trend': '+1.1%', 'trend_cls': 'up'},
                {'label': 'AI accuracy', 'value': f'{confidence}%', 'trend': '+0.5%', 'trend_cls': 'up'},
                {'label': 'Escalations', 'value': str(escalations), 'trend': '-1', 'trend_cls': 'warn'},
                {'label': 'Audit comp.', 'value': (
                    f'{health_pct}%' if health_pct is not None else dash
                ), 'trend': 'Steady', 'trend_cls': 'neutral'},
            ],
            'corrective_actions': [
                {'name': a.name, 'done': a.done} for a in self.corrective_action_ids
            ],
        }

    @api.depends(
        'name',
        'request_date',
        'work_area',
        'work_order_sequence',
        'equipment_id',
        'equipment_id.life_consumed_percent',
        'equipment_id.category_id',
        'equipment_id.category_id.name',
        'impact_level',
        'failure_risk_percent',
        'fishbone_summary',
        'final_root_cause',
        'mom_decision',
        'mom_action_owner',
        'planned_hours',
        'actual_hours',
        'total_cost',
        'stage_id',
        'stage_id.done',
        'execution_status',
        'go_no_go_decision',
        'maintenance_team_id',
        'maintenance_team_id.name',
        'affected_department',
        'user_id',
        'owner_user_id',
        'rca_line_ids',
        'corrective_action_ids',
        'corrective_action_ids.name',
        'corrective_action_ids.done',
    )
    def _compute_capa_rca_dashboard_html(self):
        from .capa_rca_dashboard_content import render_capa_rca_dashboard_html

        for request in self:
            request.capa_rca_dashboard_html = render_capa_rca_dashboard_html(
                request._capa_rca_dashboard_payload()
            )

    def action_open_capa_rca_dashboard(self):
        """Open AI CAPA Management dashboard for THIS request (never the list)."""
        self.ensure_one()
        return self._rca_method_window_action(
            'maintenance.maintenance_capa_rca_form_view',
            _('AI CAPA Management Dashboard'),
        )

    @api.depends(
        'rca_line_ids',
        'rca_line_ids.sequence',
        'rca_line_ids.problem_statement',
        'rca_line_ids.cause_statement',
        'equipment_id',
        'equipment_id.display_name',
        'equipment_id.serial_no',
        'final_root_cause',
        'rca_why_chain_html',
    )
    def _compute_rca_why_why_screen_html(self):
        from .rca_method_screens_content import render_rca_why_why_screen

        for request in self:
            request.rca_why_why_screen_html = render_rca_why_why_screen(
                equipment_label=request._rca_equipment_label(),
                why_chain_html=request.rca_why_chain_html,
                root_cause=request.final_root_cause,
            )

    @api.depends(
        'equipment_id',
        'equipment_id.display_name',
        'equipment_id.serial_no',
        'spare_line_ids',
        'spare_line_ids.spare_name',
        'spare_line_ids.dependency_component',
        'spare_line_ids.stock_status',
        'spare_line_ids.critical',
    )
    def _compute_rca_dependency_screen_html(self):
        from .rca_method_screens_content import render_rca_dependency_screen

        for request in self:
            spare_lines = []
            for line in request.spare_line_ids:
                crit = 'high' if line.critical else 'med'
                spare_lines.append({
                    'name': line.spare_name,
                    'component': line.dependency_component,
                    'stock': line.stock_status,
                    'criticality': crit,
                    'criticality_label': _('High') if line.critical else _('Medium'),
                })
            request.rca_dependency_screen_html = render_rca_dependency_screen(
                equipment_label=request._rca_equipment_label(),
                spare_lines=spare_lines,
            )

    @api.depends(
        'equipment_id',
        'equipment_id.display_name',
        'equipment_id.serial_no',
        'final_root_cause',
        'name',
    )
    def _compute_rca_failure_tree_screen_html(self):
        from .rca_method_screens_content import render_rca_failure_tree_screen

        for request in self:
            top = request.final_root_cause or request.name
            request.rca_failure_tree_screen_html = render_rca_failure_tree_screen(
                equipment_label=request._rca_equipment_label(),
                root_cause=top,
            )

    def action_open_plant_rca_dashboard(self):
        """Open Plant RCA Intelligence for THIS request (never the list)."""
        self.ensure_one()
        return self._rca_method_window_action(
            'maintenance.maintenance_plant_rca_form_view',
            _('AI Fishbone Root Cause Analysis'),
        )

    def action_open_agile_rca_dashboard(self):
        """Open Agile RCA investigation for THIS request (never the list)."""
        self.ensure_one()
        return self._rca_method_window_action(
            'maintenance.maintenance_agile_rca_form_view',
            _('Agile Investigation Network (RCA)'),
        )

    @api.model
    def sync_rca_mom_form_views(self):
        """Drop removed RCA analysis tab from DB views (fixes stale arch after upgrades)."""
        from lxml import etree

        self.env['ir.model.data'].sudo().search([
            ('module', '=', 'maintenance'),
            ('model', '=', 'ir.ui.view'),
            ('name', 'in', ('maintenance_rca_case_form_view', 'maintenance_rca_data_form_view')),
        ]).write({'noupdate': False})

        View = self.env['ir.ui.view'].sudo()
        for xmlid_name in ('maintenance_rca_case_form_view', 'maintenance_rca_data_form_view'):
            view = self.env.ref(f'maintenance.{xmlid_name}', raise_if_not_found=False)
            if not view:
                continue
            arch = view.arch_db or view.arch or ''
            if not arch or ('rca_why' not in arch and 'RCA analysis' not in arch):
                continue
            try:
                root = etree.fromstring(arch.encode('utf-8'))
            except etree.XMLSyntaxError:
                continue
            changed = False
            for page in root.xpath('//page[@name="rca_why"]'):
                parent = page.getparent()
                if parent is not None:
                    parent.remove(page)
                    changed = True
            if changed:
                View.browse(view.id).write({
                    'arch_db': etree.tostring(root, encoding='unicode'),
                })
        self.env.registry.clear_cache()

    _RCA_DASHBOARD_HTML_FIELDS = (
        'rca_ai_dashboard_html',
        'plant_rca_dashboard_html',
        'agile_rca_dashboard_html',
        'why_rca_dashboard_html',
        'capa_rca_dashboard_html',
        'rca_why_chain_html',
        'rca_why_why_screen_html',
        'rca_dependency_screen_html',
        'rca_failure_tree_screen_html',
    )

    _RCA_DASHBOARD_WRITE_TRIGGERS = frozenset({
        'name',
        'equipment_id',
        'maintenance_type',
        'impact_level',
        'work_area',
        'work_order_sequence',
        'failure_risk_percent',
        'vibration_level',
        'bearing_temp_state',
        'final_root_cause',
        'fishbone_summary',
        'fault_tree_summary',
        'rca_method',
        'mom_discussion',
        'mom_decision',
        'mom_action_owner',
        'actual_hours',
        'planned_hours',
        'execution_status',
        'go_no_go_decision',
        'total_cost',
        'affected_department',
        'user_id',
        'owner_user_id',
        'maintenance_team_id',
        'stage_id',
        'rca_line_ids',
        'corrective_action_ids',
    })

    def _invalidate_rca_dashboards(self, extra_requests=None):
        """Recompute Analysis dashboards for this request and teammates."""
        requests = (self | extra_requests) if extra_requests is not None else self
        requests = requests.exists()
        if not requests:
            return
        team_ids = requests.mapped('maintenance_team_id').ids
        if team_ids:
            team_mates = self.search([
                ('maintenance_team_id', 'in', team_ids),
                ('archive', '=', False),
            ])
            requests |= team_mates
        requests.invalidate_recordset(list(self._RCA_DASHBOARD_HTML_FIELDS))
        requests._recompute_rca_dashboard_html_fields()

    def _recompute_rca_dashboard_html_fields(self):
        """Force HTML dashboard fields to rebuild (not cached mockup)."""
        if not self:
            return
        self._compute_rca_ai_dashboard_html()
        self._compute_plant_rca_dashboard_html()
        self._compute_agile_rca_dashboard_html()
        self._compute_why_rca_dashboard_html()
        self._compute_capa_rca_dashboard_html()
        self._compute_rca_why_why_screen_html()
        self._compute_rca_dependency_screen_html()
        self._compute_rca_failure_tree_screen_html()

    def action_refresh_rca_dashboards(self):
        """Header button: rebuild all Analysis dashboards for this work order."""
        self.ensure_one()
        self._invalidate_rca_dashboards()
        return True

    def action_open_rca_excel_import(self):
        """Open Excel import wizard for RCA master data."""
        ctx = dict(self.env.context)
        if len(self) == 1:
            ctx['default_request_id'] = self.id
        return {
            'type': 'ir.actions.act_window',
            'name': _('Import RCA Master Data'),
            'res_model': 'maintenance.rca.excel.import.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    def action_download_rca_excel_template(self):
        """Download pre-filled Excel master template."""
        wizard = self.env['maintenance.rca.excel.import.wizard'].create({})
        return wizard.action_download_template()

    @api.model
    def _rca_analysis_action_vals(self, path, form_view, tree_view=None, form_view_ref=None, rca_required_filter=False):
        """Shared list→form action for Analysis menus (no fixed demo record).

        form_view_ref lets the Plant sidebar open the same selected request on
        that specialized form instead of reusing the generic request form.
        """
        from .maintenance_types import rca_analysis_list_domain
        tree_view = tree_view or self.env.ref(
            'maintenance.maintenance_rca_case_tree_view', raise_if_not_found=False
        )
        search_view = self.env.ref(
            'maintenance.maintenance_rca_case_search_view',
            raise_if_not_found=False,
        )
        view_ids = [(5, 0, 0)]
        if tree_view:
            view_ids.append((0, 0, {'view_mode': 'list', 'view_id': tree_view.id}))
        if form_view:
            view_ids.append((0, 0, {'view_mode': 'form', 'view_id': form_view.id}))
        if not form_view_ref and form_view:
            # Prefer xmlid when available so sidebar keepRequestContext works.
            xmlids = form_view.get_external_id()
            form_view_ref = xmlids.get(form_view.id) or False
        ctx = {
            'create': False,
            'delete': False,
            'search_default_active': 1,
        }
        if rca_required_filter:
            ctx['search_default_rca_required_jobs'] = 1
        if form_view_ref:
            ctx['form_view_ref'] = form_view_ref
        return {
            'view_mode': 'list,form',
            'target': 'current',
            'view_id': tree_view.id if tree_view else form_view.id,
            'view_ids': view_ids,
            'domain': rca_analysis_list_domain(),
            'search_view_id': search_view.id if search_view else False,
            'context': ctx,
            'res_id': False,
            'path': path,
        }

    @api.model
    def fix_rca_dashboard_setup(self):
        """Wire Analysis menus to list→form (live work orders, not a fixed demo id)."""
        self.sync_rca_mom_form_views()
        tree = self.env.ref('maintenance.maintenance_rca_case_tree_view', raise_if_not_found=False)

        action = self.env.ref('maintenance.maintenance_rca_action', raise_if_not_found=False)
        view = self.env.ref('maintenance.maintenance_rca_case_form_view', raise_if_not_found=False)
        if action and view:
            action.sudo().write(
                self._rca_analysis_action_vals(
                    'rca-mom',
                    view,
                    tree,
                    form_view_ref='maintenance.maintenance_rca_case_form_view',
                    rca_required_filter=True,
                )
            )

        plant_action = self.env.ref('maintenance.maintenance_plant_rca_action', raise_if_not_found=False)
        plant_view = self.env.ref('maintenance.maintenance_plant_rca_form_view', raise_if_not_found=False)
        alias = self.env.ref(
            'maintenance.maintenance_rca_action_plant_path_alias', raise_if_not_found=False
        )
        if plant_action and plant_view:
            plant_action.sudo().write(
                self._rca_analysis_action_vals(
                    'ai-plant-rca',
                    plant_view,
                    tree,
                    form_view_ref='maintenance.maintenance_plant_rca_form_view',
                )
            )
        if alias and plant_view:
            alias.sudo().write(
                self._rca_analysis_action_vals(
                    'plant-rca-mom',
                    plant_view,
                    tree,
                    form_view_ref='maintenance.maintenance_plant_rca_form_view',
                )
            )

        menu = self.env.ref('maintenance.menu_m_rca_mom', raise_if_not_found=False)
        if menu and action:
            menu.sudo().write({'action': f'ir.actions.act_window,{action.id}'})

        agile_action = self.env.ref('maintenance.maintenance_agile_rca_action', raise_if_not_found=False)
        agile_view = self.env.ref('maintenance.maintenance_agile_rca_form_view', raise_if_not_found=False)
        agile_menu = self.env.ref('maintenance.menu_m_agile_rca', raise_if_not_found=False)
        if agile_action and agile_view:
            agile_action.sudo().write(
                self._rca_analysis_action_vals(
                    'ai-agile-rca',
                    agile_view,
                    tree,
                    form_view_ref='maintenance.maintenance_agile_rca_form_view',
                )
            )
        if agile_menu:
            agile_menu.sudo().write({'name': 'Agile Investigation Network'})

        why_action = self.env.ref('maintenance.maintenance_why_rca_action', raise_if_not_found=False)
        why_view = self.env.ref('maintenance.maintenance_why_rca_form_view', raise_if_not_found=False)
        why_menu = self.env.ref('maintenance.menu_m_why_rca', raise_if_not_found=False)
        if why_action and why_view:
            why_action.sudo().write(
                self._rca_analysis_action_vals(
                    'ai-why-rca',
                    why_view,
                    tree,
                    form_view_ref='maintenance.maintenance_why_rca_form_view',
                )
            )
        if why_menu:
            why_menu.sudo().write({'name': 'AI Why-Why Root Cause Analysis'})

        capa_action = self.env.ref('maintenance.maintenance_capa_rca_action', raise_if_not_found=False)
        capa_view = self.env.ref('maintenance.maintenance_capa_rca_form_view', raise_if_not_found=False)
        capa_menu = self.env.ref('maintenance.menu_m_capa_rca', raise_if_not_found=False)
        if capa_action and capa_view:
            capa_action.sudo().write(
                self._rca_analysis_action_vals(
                    'ai-capa-rca',
                    capa_view,
                    tree,
                    form_view_ref='maintenance.maintenance_capa_rca_form_view',
                )
            )
        if capa_menu:
            capa_menu.sudo().write({'name': 'AI CAPA Management Dashboard'})

        self.env['maintenance.request'].search([
            ('archive', '=', False),
        ], limit=200)._recompute_rca_dashboard_html_fields()

    @api.model
    def restore_plant_demo_operational_screens(self):
        """Restore fleet demo on Operations/Planning/Equipment (Analysis setup unchanged)."""
        import logging
        _logger = logging.getLogger(__name__)

        self.ensure_demo_spare_planning_lines()
        Equipment = self.env['maintenance.equipment'].sudo()
        Request = self.env['maintenance.request'].sudo()
        demo_eq = Equipment.search([('serial_no', 'ilike', 'SN-DEMO%')])
        if not demo_eq:
            _logger.warning(
                'Plant demo equipment not found — upgrade Maintenance to reload '
                'data/maintenance_plant_demo.xml.'
            )
            return False

        demo_req = Request.search([
            '|',
            ('work_order_sequence', 'ilike', 'WO-DEMO%'),
            ('equipment_id', 'in', demo_eq.ids),
        ])
        archived = demo_req.filtered('archive')
        if archived:
            archived.write({'archive': False})

        users = self.env['res.users'].sudo().search([
            ('share', '=', False),
            ('active', '=', True),
        ])
        partner_ids = users.partner_id.ids
        if partner_ids:
            demo_eq.message_subscribe(partner_ids=partner_ids)
            if demo_req:
                demo_req.message_subscribe(partner_ids=partner_ids)

        team = self.env.ref(
            'maintenance.maintenance_team_workflow_examples',
            raise_if_not_found=False,
        )
        if team and users:
            team.sudo().write({'member_ids': [(4, uid) for uid in users.ids]})

        _logger.info(
            'Plant demo operational restore: %s equipment, %s work orders.',
            len(demo_eq),
            len(demo_req),
        )
        return True

    def archive_equipment_request(self):
        self.write({'archive': True, 'recurring_maintenance': False})

    def reset_equipment_request(self):
        """ Reinsert the maintenance request into the maintenance pipe in the first stage"""
        first_stage_obj = self.env['maintenance.stage'].search([], order="sequence asc", limit=1)
        # self.write({'active': True, 'stage_id': first_stage_obj.id})
        self.write({'archive': False, 'stage_id': first_stage_obj.id})

    @api.constrains('repeat_interval')
    def _check_repeat_interval(self):
        for record in self:
            if record.repeat_interval < 1:
                raise ValidationError("Repeat Interval cannot be less than 1.")

    @api.depends('company_id', 'equipment_id')
    def _compute_maintenance_team_id(self):
        for request in self:
            if request.equipment_id and request.equipment_id.maintenance_team_id:
                request.maintenance_team_id = request.equipment_id.maintenance_team_id.id
            if request.maintenance_team_id.company_id and request.maintenance_team_id.company_id.id != request.company_id.id:
                request.maintenance_team_id = False

    @api.model
    def _responsible_user_for_equipment(self, equipment, maintenance_type):
        """Resolve default owner from equipment / category by maintenance type."""
        from .maintenance_types import is_preventive_type, is_predictive_type

        if not equipment:
            return self.env['res.users']
        cat = equipment.category_id
        if is_preventive_type(maintenance_type):
            return (
                equipment.preventive_responsible_user_id
                or (cat.preventive_responsible_user_id if cat else self.env['res.users'])
            )
        if is_predictive_type(maintenance_type):
            return (
                equipment.predictive_responsible_user_id
                or (cat.predictive_responsible_user_id if cat else self.env['res.users'])
                or equipment.preventive_responsible_user_id
                or (cat.preventive_responsible_user_id if cat else self.env['res.users'])
            )
        return (
            equipment.corrective_responsible_user_id
            or (cat.corrective_responsible_user_id if cat else self.env['res.users'])
            or (cat.technician_user_id if cat else self.env['res.users'])
        )

    @api.depends(
        'company_id',
        'equipment_id',
        'maintenance_type',
        'equipment_id.corrective_responsible_user_id',
        'equipment_id.preventive_responsible_user_id',
        'equipment_id.predictive_responsible_user_id',
        'equipment_id.category_id.corrective_responsible_user_id',
        'equipment_id.category_id.preventive_responsible_user_id',
        'equipment_id.category_id.predictive_responsible_user_id',
        'equipment_id.category_id.technician_user_id',
    )
    def _compute_user_id(self):
        for request in self:
            responsible = request._responsible_user_for_equipment(
                request.equipment_id, request.maintenance_type or 'corrective'
            )
            if responsible:
                request.user_id = responsible
            if request.user_id and request.company_id.id not in request.user_id.company_ids.ids:
                request.user_id = False

    @api.onchange('equipment_id', 'maintenance_type')
    def _onchange_equipment_maintenance_type_responsible(self):
        for request in self:
            responsible = request._responsible_user_for_equipment(
                request.equipment_id, request.maintenance_type or 'corrective'
            )
            if responsible:
                request.user_id = responsible

    @api.depends('maintenance_type')
    def _compute_recurring_maintenance(self):
        for request in self:
            if request.maintenance_type != 'preventive':
                request.recurring_maintenance = False

    _CONDITION_READING_TRIGGER_FIELDS = frozenset({
        'maintenance_type',
        'planning_maintenance_type',
        'impact_level',
        'failure_found_during_job',
        'go_no_go_decision',
        'stage_id',
        'execution_status',
        'priority',
    })

    def _auto_condition_reading_targets(self):
        """Derive manual sensor readings from request type, impact, and workflow state."""
        self.ensure_one()
        from .maintenance_types import is_corrective_type, is_preventive_type, is_predictive_type

        impact = self.impact_level or 'medium'
        risk_by_impact = {'low': 30.0, 'medium': 55.0, 'high': 75.0}
        risk = risk_by_impact.get(impact, 55.0)

        if self.failure_found_during_job:
            return {
                'vibration_level': 'critical_high',
                'bearing_temp_state': 'high',
                'failure_risk_percent': max(risk, 65.0),
            }

        if self.go_no_go_decision == 'no_go':
            return {
                'vibration_level': 'critical_high',
                'bearing_temp_state': 'high',
                'failure_risk_percent': max(risk, 85.0),
            }

        stage_done = bool(self.stage_id and self.stage_id.done)
        if stage_done and self.go_no_go_decision == 'go':
            return {
                'vibration_level': 'normal',
                'bearing_temp_state': 'normal',
                'failure_risk_percent': 15.0,
            }

        if self.execution_status == 'completed' and self.go_no_go_decision == 'go':
            return {
                'vibration_level': 'normal',
                'bearing_temp_state': 'normal',
                'failure_risk_percent': min(risk, 20.0),
            }

        if is_predictive_type(self.maintenance_type) or self.planning_maintenance_type == 'predictive':
            return {
                'vibration_level': 'critical_high',
                'bearing_temp_state': 'high' if impact == 'high' else 'normal',
                'failure_risk_percent': max(45.0, risk),
            }

        if is_preventive_type(self.maintenance_type) or self.planning_maintenance_type == 'preventive':
            return {
                'vibration_level': 'normal',
                'bearing_temp_state': 'normal',
                'failure_risk_percent': 10.0,
            }

        if is_corrective_type(self.maintenance_type) or self.planning_maintenance_type == 'breakdown':
            vibration = 'critical_high' if impact in ('medium', 'high') else 'normal'
            bearing = 'high' if impact == 'high' else ('high' if impact == 'medium' else 'normal')
            if self.priority == '3':
                risk = max(risk, 80.0)
            return {
                'vibration_level': vibration,
                'bearing_temp_state': bearing,
                'failure_risk_percent': risk,
            }

        return {
            'vibration_level': 'normal',
            'bearing_temp_state': 'normal',
            'failure_risk_percent': risk,
        }

    def _apply_auto_condition_readings(self):
        """Write vibration/temp/risk from business rules (unless manually locked)."""
        for request in self.filtered(lambda r: not r.condition_readings_manual):
            targets = request._auto_condition_reading_targets()
            request.with_context(skip_auto_condition_readings=True).write(targets)

    def action_reset_auto_condition_readings(self):
        """Return alert readings to automatic rules (demo / planner reset)."""
        self.write({'condition_readings_manual': False})
        self._apply_auto_condition_readings()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        # context: no_log, because subtype already handle this
        maintenance_requests = super().create(vals_list)
        for request in maintenance_requests:
            if request.owner_user_id or request.user_id:
                request._add_followers()
            if request.equipment_id and not request.maintenance_team_id:
                request.maintenance_team_id = request.equipment_id.maintenance_team_id
            if request.close_date and not request.stage_id.done:
                request.close_date = False
            if not request.close_date and request.stage_id.done:
                request.close_date = fields.Date.today()
        maintenance_requests.filtered(
            lambda r: not r.condition_readings_manual
        )._apply_auto_condition_readings()
        maintenance_requests.activity_update()
        companies = maintenance_requests.mapped('company_id').filtered(lambda c: c) or self.env.company
        self.env['maintenance.analytics.dashboard']._invalidate_for_companies(companies)
        return maintenance_requests

    def write(self, vals):
        # Overridden to reset the kanban_state to normal whenever
        # the stage (stage_id) of the Maintenance Request changes.
        if vals and 'kanban_state' not in vals and 'stage_id' in vals:
            vals['kanban_state'] = 'normal'
        if (
            vals
            and not self.env.context.get('skip_auto_condition_readings')
            and {'vibration_level', 'bearing_temp_state', 'failure_risk_percent'} & set(vals)
            and 'condition_readings_manual' not in vals
        ):
            vals = dict(vals, condition_readings_manual=True)
        now = fields.Datetime.now()
        if 'stage_id' in vals and self.env['maintenance.stage'].browse(vals['stage_id']).done:
            for request in self:
                if request.maintenance_type != 'preventive' or not request.recurring_maintenance:
                    continue
                schedule_date = request.schedule_date or now
                schedule_date += relativedelta(**{f"{request.repeat_unit}s": request.repeat_interval})
                if request.repeat_type == 'forever' or schedule_date.date() <= request.repeat_until:
                    request.copy({'schedule_date': schedule_date, 'stage_id': request._default_stage().id})
        companies = self.mapped('company_id')
        res = super(MaintenanceRequest, self).write(vals)
        companies |= self.mapped('company_id')
        self.env['maintenance.analytics.dashboard']._invalidate_for_companies(companies.filtered(lambda c: c) or self.env.company)
        if self._RCA_DASHBOARD_WRITE_TRIGGERS.intersection(vals):
            self._invalidate_rca_dashboards()
        if vals.get('owner_user_id') or vals.get('user_id'):
            self._add_followers()
        if 'stage_id' in vals:
            self.filtered(lambda m: m.stage_id.done).write({'close_date': fields.Date.today()})
            self.filtered(lambda m: not m.stage_id.done).write({'close_date': False})
            self.activity_feedback(['maintenance.mail_act_maintenance_request'])
            self.activity_update()
        if vals.get('user_id') or vals.get('schedule_date'):
            self.activity_update()
        if self._need_new_activity(vals):
            # need to change description of activity also so unlink old and create new activity
            self.activity_unlink(['maintenance.mail_act_maintenance_request'])
            self.activity_update()
        if not self.env.context.get('install_module') and not self.env.context.get('module'):
            if {'stage_id', 'execution_status'} & set(vals):
                closing = self.filtered(
                    lambda r: r.rca_required and (
                        r.execution_status == 'completed'
                        or (r.stage_id and r.stage_id.done)
                    )
                )
                if closing:
                    closing._raise_if_rca_missing_for_closure()
        if (
            vals
            and not self.env.context.get('skip_auto_condition_readings')
            and self._CONDITION_READING_TRIGGER_FIELDS.intersection(vals)
        ):
            self.filtered(lambda r: not r.condition_readings_manual)._apply_auto_condition_readings()
        return res

    def _need_new_activity(self, vals):
        return vals.get('equipment_id')

    def _get_activity_note(self):
        self.ensure_one()
        if self.equipment_id:
            return _('Request planned for %s', self.equipment_id._get_html_link())
        return False

    def activity_update(self):
        """ Update maintenance activities based on current record set state.
        It reschedule, unlink or create maintenance request activities. """
        self.filtered(lambda request: not request.schedule_date).activity_unlink(['maintenance.mail_act_maintenance_request'])
        for request in self.filtered(lambda request: request.schedule_date):
            date_dl = fields.Datetime.from_string(request.schedule_date).date()
            updated = request.activity_reschedule(
                ['maintenance.mail_act_maintenance_request'],
                date_deadline=date_dl,
                new_user_id=request.user_id.id or request.owner_user_id.id or self.env.uid)
            if not updated:
                note = request._get_activity_note()
                request.activity_schedule(
                    'maintenance.mail_act_maintenance_request',
                    fields.Datetime.from_string(request.schedule_date).date(),
                    note=note, user_id=request.user_id.id or request.owner_user_id.id or self.env.uid)

    def _add_followers(self):
        for request in self:
            partner_ids = (request.owner_user_id.partner_id + request.user_id.partner_id).ids
            request.message_subscribe(partner_ids=partner_ids)

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """ Read group customization in order to display all the stages in the
            kanban view, even if they are empty
        """
        stage_ids = stages.sudo()._search([], order=stages._order)
        return stages.browse(stage_ids)

    @api.depends('company_id')
    def _compute_maintenance_cost_currency_id(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        for request in self:
            request.currency_id = usd or request.company_id.currency_id

    @api.depends('electrical_cost', 'mechanical_cost', 'spare_total_cost')
    def _compute_total_cost(self):
        """Labor + spares — same basis as workflow timeline and analytics."""
        for request in self:
            request.total_cost = (
                (request.electrical_cost or 0.0)
                + (request.mechanical_cost or 0.0)
                + (request.spare_total_cost or 0.0)
            )

    @api.depends('total_cost')
    def _compute_maintenance_timeline_total(self):
        for request in self:
            request.maintenance_timeline_total = request.total_cost or 0.0

    @api.depends('work_order_sequence')
    def _compute_work_order_display(self):
        for request in self:
            if request.work_order_sequence:
                request.work_order_display = request.work_order_sequence
            elif request.id:
                request.work_order_display = _('WO-%s') % request.id
            else:
                request.work_order_display = _('New')

    @api.depends(
        'name',
        'equipment_id',
        'planned_date',
        'planning_maintenance_type',
        'spare_line_ids',
        'user_id',
        'manpower_line_ids',
        'actual_hours',
        'execution_notes',
        'go_no_go_decision',
        'decision_resolution_notes',
        'final_root_cause',
        'rca_required',
        'failure_found_during_job',
        'maintenance_type',
        'done',
        'execution_status',
        'stage_id.done',
    )
    def _compute_workflow_timeline_flags(self):
        for request in self:
            request.wf_step_issue_done = bool(request.name and request.equipment_id)
            request.wf_step_plan_done = bool(request.planned_date or request.planning_maintenance_type)
            request.wf_step_spare_done = bool(request.spare_line_ids)
            request.wf_step_assigned_done = bool(request.user_id or request.manpower_line_ids)
            request.wf_step_execution_done = bool(
                (request.actual_hours or 0.0) > 0.0 or (request.execution_notes or '').strip()
            )
            request.wf_step_gonogo_done = bool(
                request.wf_step_execution_done
                and (
                    request.go_no_go_decision == 'go'
                    or bool((request.decision_resolution_notes or '').strip())
                )
            )
            if not request.rca_required:
                request.wf_step_rca_done = True
            else:
                request.wf_step_rca_done = bool((request.final_root_cause or '').strip())
            request.wf_step_completed_done = bool(
                request.done or request.execution_status == 'completed' or request.stage_id.done
            )
            steps_done = [
                request.wf_step_issue_done,
                request.wf_step_plan_done,
                request.wf_step_spare_done,
                request.wf_step_assigned_done,
                request.wf_step_execution_done,
                request.wf_step_gonogo_done,
                request.wf_step_rca_done,
                request.wf_step_completed_done,
            ]
            # Highlight = current / first incomplete step (purple). All done → Completed.
            first_open = next((i for i, ok in enumerate(steps_done) if not ok), None)
            if first_open is None:
                request.wf_timeline_highlight_index = 7
            else:
                request.wf_timeline_highlight_index = first_open

    @api.depends(
        'manpower_line_ids',
        'manpower_line_ids.user_id',
        'manpower_line_ids.user_id.name',
        'user_id',
        'user_id.name',
    )
    def _compute_timeline_assigned_html(self):
        for request in self:
            request.timeline_assigned_html = request._render_timeline_assigned_html()

    def _render_timeline_assigned_html(self):
        self.ensure_one()
        users = self.manpower_line_ids.mapped('user_id').filtered(lambda u: u)
        if not users and self.user_id:
            users = self.user_id
        chips = []
        shown = users[:4]
        for user in shown:
            name = user.name or '?'
            initial = (name.strip()[:1] or '?').upper()
            chips.append(
                f'<span class="o_mtl_avatar" title="{escape(name)}">{escape(initial)}</span>'
            )
        extra = len(users) - len(shown)
        if extra > 0:
            chips.append(f'<span class="o_mtl_avatar o_mtl_avatar_more">+{extra}</span>')
        if not chips:
            chips.append(f'<span class="o_mtl_avatar_empty">{escape(_("No technicians"))}</span>')
        return Markup(f'<div class="o_mtl_avatar_row">{"".join(chips)}</div>')

    @api.depends(
        'name',
        'create_date',
        'write_date',
        'equipment_id',
        'category_id',
        'planned_date',
        'planned_duration',
        'planned_hours',
        'planning_maintenance_type',
        'spare_line_ids',
        'spare_line_ids.product_id',
        'spare_line_ids.spare_name',
        'spare_line_ids.quantity',
        'spare_line_ids.procurement_status',
        'user_id',
        'user_id.name',
        'manpower_line_ids',
        'manpower_line_ids.skill_type',
        'manpower_line_ids.user_id',
        'manpower_line_ids.user_id.name',
        'actual_hours',
        'delay_hours',
        'execution_notes',
        'go_no_go_decision',
        'decision_resolution_notes',
        'final_root_cause',
        'rca_required',
        'done',
        'execution_status',
        'stage_id',
        'stage_id.done',
        'work_order_display',
        'maintenance_timeline_total',
        'currency_id',
        'wf_step_issue_done',
        'wf_step_plan_done',
        'wf_step_spare_done',
        'wf_step_assigned_done',
        'wf_step_execution_done',
        'wf_step_gonogo_done',
        'wf_step_rca_done',
        'wf_step_completed_done',
        'wf_timeline_highlight_index',
    )
    def _compute_workflow_timeline_html(self):
        for request in self:
            request.workflow_timeline_html = request._render_workflow_timeline_html()

    def _render_workflow_timeline_html(self):
        """Suite mockup: lifecycle rail + execution / spares / decision + KPI strip."""
        self.ensure_one()

        def fmt_hours(value):
            value = value or 0.0
            return f'{value:.2f}' if abs(value - round(value)) >= 0.01 else f'{int(round(value))}.00'

        def fmt_money(value):
            value = value or 0.0
            return f'{value:,.2f}'

        def fmt_date(value):
            if not value:
                return ''
            try:
                return format_date(self.env, fields.Date.to_date(value))
            except Exception:
                return str(value)

        skill_labels = {
            'electrical': _('Electrician'),
            'mechanical': _('Mechanic'),
            'vendor': _('Vendor'),
            'other': _('Technician'),
        }
        tech_line = self.manpower_line_ids.filtered(lambda l: l.skill_type == 'electrical')[:1]
        if not tech_line:
            tech_line = self.manpower_line_ids[:1]
        technician_name = '—'
        technician_initial = '?'
        if tech_line and tech_line.user_id:
            technician_name = tech_line.user_id.name
            technician_initial = (technician_name[:1] or '?').upper()
            role = skill_labels.get(tech_line.skill_type, _('Technician'))
            technician_label = f'{technician_name} ({role})'
        elif self.user_id:
            technician_name = self.user_id.name
            technician_initial = (technician_name[:1] or '?').upper()
            technician_label = technician_name
        else:
            technician_label = '—'

        create_d = fmt_date(self.create_date)
        plan_d = fmt_date(self.planned_date) or create_d
        write_d = fmt_date(self.write_date) or plan_d

        steps_meta = [
            (_('Issue Identified'), 'fa-exclamation-triangle', create_d, _('Request created')),
            (_('Maintenance Plan'), 'fa-file-text-o', plan_d, _('Plan and schedule')),
            (_('Spare Planning'), 'fa-cube', write_d, _('Spare parts added')),
            (_('WO Assigned'), 'fa-user', write_d, _('Technician assigned')),
            (_('Work Execution'), 'fa-wrench', '', _('Actual work in progress')),
            (_('Go / No-Go'), 'fa-flag-o', '', _('Decision pending')),
            (_('Root Cause'), 'fa-search', '', _('RCA pending')),
            (_('Completed'), 'fa-flag-checkered', '', _('Close request')),
        ]
        steps_done = [
            self.wf_step_issue_done,
            self.wf_step_plan_done,
            self.wf_step_spare_done,
            self.wf_step_assigned_done,
            self.wf_step_execution_done,
            self.wf_step_gonogo_done,
            self.wf_step_rca_done,
            self.wf_step_completed_done,
        ]
        highlight = min(self.wf_timeline_highlight_index or 0, len(steps_meta) - 1)

        all_done = all(steps_done)
        step_nodes = []
        for index, ((title, icon, date_txt, hint), done) in enumerate(zip(steps_meta, steps_done)):
            if index == highlight and not all_done:
                state = 'current'
                status_txt = _('In Progress') if index == 4 else (date_txt or _('Current'))
                icon_html = f'<i class="fa {icon}"></i>'
            elif done:
                state = 'done'
                status_txt = date_txt or _('Done')
                icon_html = '<i class="fa fa-check"></i>'
            else:
                state = 'pending'
                status_txt = _('Pending')
                icon_html = f'<i class="fa {icon}"></i>'
            connector_cls = 'o_mtl_lc_connector'
            if index < len(steps_meta) - 1:
                if done:
                    connector_cls += ' o_mtl_lc_connector_done'
                else:
                    connector_cls += ' o_mtl_lc_connector_pending'
            connector = (
                f'<div class="{connector_cls}"></div>' if index < len(steps_meta) - 1 else ''
            )
            step_nodes.append(
                f'<div class="o_mtl_lc_step o_mtl_lc_step_{state}">'
                f'{connector}'
                f'<div class="o_mtl_lc_circle">{icon_html}</div>'
                f'<div class="o_mtl_lc_title">{escape(str(title))}</div>'
                f'<div class="o_mtl_lc_status">{escape(str(status_txt))}</div>'
                f'<div class="o_mtl_lc_hint">{escape(str(hint))}</div>'
                f'</div>'
            )

        # Spares table
        proc_map = {
            'pr_created': (_('PR Created'), 'pr'),
            'issued_from_store': (_('Issued from Store'), 'issued'),
        }
        spare_rows = []
        for line in self.spare_line_ids[:4]:
            label = line.product_id.display_name if line.product_id else (line.spare_name or _('Spare'))
            qty = line.quantity or 0.0
            qty_txt = f'{qty:g}' if qty == int(qty) else f'{qty:.2f}'
            proc_label, proc_cls = proc_map.get(
                line.procurement_status, (_('Planned'), 'planned')
            )
            spare_rows.append(
                '<tr>'
                f'<td>{escape(str(label))}</td>'
                f'<td class="o_mtl_spare_qty">{escape(qty_txt)}</td>'
                f'<td><span class="o_mtl_pill o_mtl_pill_{proc_cls}">{escape(str(proc_label))}</span></td>'
                '</tr>'
            )
        issued_n = len(self.spare_line_ids.filtered(
            lambda l: l.procurement_status == 'issued_from_store'
        ))
        total_n = len(self.spare_line_ids)
        spare_badge = f'{issued_n} / {total_n} {_("items")}' if total_n else _('No items')
        if spare_rows:
            spare_table = (
                '<table class="o_mtl_spare_table"><thead><tr>'
                f'<th>{escape(_("Spare Part"))}</th>'
                f'<th>{escape(_("Qty"))}</th>'
                f'<th>{escape(_("Status"))}</th>'
                '</tr></thead><tbody>'
                f'{"".join(spare_rows)}</tbody></table>'
                f'<div class="o_mtl_spare_link">{escape(_("View All Spares →"))}</div>'
            )
        else:
            spare_table = f'<div class="o_mtl_empty">{escape(_("No spare lines."))}</div>'

        res_notes = (self.decision_resolution_notes or '').strip()
        if self.go_no_go_decision == 'go':
            decision_block = (
                '<div class="o_mtl_decision_banner o_mtl_decision_go">'
                '<div class="o_mtl_decision_circle"><i class="fa fa-check"></i></div>'
                f'<div class="o_mtl_decision_label">{escape(_("GO"))}</div>'
                f'<div class="o_mtl_decision_msg">{escape(_("Asset is safe to return to service"))}</div>'
                '</div>'
            )
        elif self.go_no_go_decision == 'no_go' and res_notes:
            decision_block = (
                '<div class="o_mtl_decision_banner o_mtl_decision_resolved">'
                '<div class="o_mtl_decision_flow">'
                '<div class="o_mtl_decision_mini o_mtl_decision_nogo"><i class="fa fa-times"></i>'
                f'<span>{escape(_("NO GO"))}</span></div>'
                '<span class="o_mtl_decision_arrow">→</span>'
                '<div class="o_mtl_decision_mini o_mtl_decision_go"><i class="fa fa-check"></i>'
                f'<span>{escape(_("RESOLVED TO GO"))}</span></div>'
                '</div></div>'
            )
        else:
            decision_block = (
                '<div class="o_mtl_decision_banner o_mtl_decision_nogo">'
                '<div class="o_mtl_decision_circle"><i class="fa fa-times"></i></div>'
                f'<div class="o_mtl_decision_label">{escape(_("NO GO"))}</div>'
                f'<div class="o_mtl_decision_msg">{escape(_("Asset held — decision pending or blocked"))}</div>'
                '</div>'
            )

        root_cause_txt = (self.final_root_cause or '').strip()
        if root_cause_txt:
            root_html = (
                '<div class="o_mtl_kpi o_mtl_kpi_root o_mtl_kpi_root_ok">'
                f'<div class="o_mtl_kpi_lbl"><i class="fa fa-search"></i> {escape(_("Root Cause"))}</div>'
                f'<div class="o_mtl_kpi_root_txt">{escape(root_cause_txt)}</div>'
                '</div>'
            )
        else:
            root_html = (
                '<div class="o_mtl_kpi o_mtl_kpi_root o_mtl_kpi_root_warn">'
                f'<div class="o_mtl_kpi_lbl"><i class="fa fa-exclamation-triangle"></i> {escape(_("Root Cause"))}</div>'
                f'<div class="o_mtl_kpi_root_txt">{escape(_("Root cause not yet recorded. This step will be completed after RCA."))}</div>'
                '</div>'
            )

        exec_status = _('In Progress')
        if self.done or self.execution_status == 'completed' or self.stage_id.done:
            exec_status = _('Completed')
        elif self.execution_status == 'paused':
            exec_status = _('Paused')

        currency_symbol = str(self.currency_id.symbol or '₹')
        planned_h = self.planned_hours or self.planned_duration or 0.0
        actual_h = self.actual_hours or 0.0
        delay_h = self.delay_hours or 0.0
        exec_notes = (self.execution_notes or '').strip() or '—'

        return Markup(
            '<div class="o_mtl_html_root">'
            '<div class="o_mtl_lifecycle_card">'
            '<div class="o_mtl_lifecycle_head">'
            f'<div class="o_mtl_lifecycle_title">{escape(_("Maintenance Lifecycle"))}</div>'
            '<div class="o_mtl_lifecycle_legend">'
            f'<span><i class="o_mtl_dot o_mtl_dot_done"></i> {escape(_("Completed"))}</span>'
            f'<span><i class="o_mtl_dot o_mtl_dot_current"></i> {escape(_("Current"))}</span>'
            f'<span><i class="o_mtl_dot o_mtl_dot_pending"></i> {escape(_("Pending"))}</span>'
            '</div></div>'
            f'<div class="o_mtl_lifecycle_rail">{"".join(step_nodes)}</div>'
            '</div>'
            '<div class="o_mtl_detail_grid">'
            '<div class="o_mtl_card">'
            '<div class="o_mtl_card_head">'
            f'<div class="o_mtl_card_title"><i class="fa fa-wrench"></i> {escape(_("Work Execution"))}</div>'
            f'<span class="o_mtl_badge o_mtl_badge_info">{escape(str(exec_status))}</span>'
            '</div>'
            '<div class="o_mtl_tech_row">'
            f'<span class="o_mtl_avatar">{escape(technician_initial)}</span>'
            '<div>'
            f'<div class="o_mtl_muted">{escape(_("Assigned Technician"))}</div>'
            f'<div class="o_mtl_strong">{escape(technician_label)}</div>'
            '</div></div>'
            '<div class="o_mtl_metric_row">'
            f'<div class="o_mtl_metric"><div class="o_mtl_muted">{escape(_("Planned Hours"))}</div>'
            f'<div class="o_mtl_metric_val">{escape(fmt_hours(planned_h))} <span>hrs</span></div></div>'
            f'<div class="o_mtl_metric"><div class="o_mtl_muted">{escape(_("Actual Hours"))}</div>'
            f'<div class="o_mtl_metric_val">{escape(fmt_hours(actual_h))} <span>hrs</span></div></div>'
            f'<div class="o_mtl_metric o_mtl_metric_delay"><div class="o_mtl_muted">{escape(_("Delay"))}</div>'
            f'<div class="o_mtl_metric_val">{escape(fmt_hours(delay_h))} <span>hrs</span></div></div>'
            '</div>'
            f'<div class="o_mtl_muted o_mtl_notes_lbl">{escape(_("Execution Notes"))}</div>'
            f'<div class="o_mtl_notes">{escape(exec_notes)}</div>'
            '</div>'
            '<div class="o_mtl_card">'
            '<div class="o_mtl_card_head">'
            f'<div class="o_mtl_card_title"><i class="fa fa-cube"></i> {escape(_("Spare Planning"))}</div>'
            f'<span class="o_mtl_badge o_mtl_badge_soft">{escape(spare_badge)}</span>'
            '</div>'
            f'{spare_table}'
            '</div>'
            '<div class="o_mtl_card">'
            '<div class="o_mtl_card_head">'
            f'<div class="o_mtl_card_title"><i class="fa fa-balance-scale"></i> {escape(_("Operational Decision"))}</div>'
            '</div>'
            f'{decision_block}'
            f'<div class="o_mtl_muted o_mtl_notes_lbl">{escape(_("Resolution Notes"))}</div>'
            f'<div class="o_mtl_notes">{escape(res_notes or "—")}</div>'
            '</div>'
            '</div>'
            '<div class="o_mtl_kpi_row">'
            '<div class="o_mtl_kpi">'
            f'<div class="o_mtl_kpi_lbl"><i class="fa fa-clock-o"></i> {escape(_("Total Time"))}</div>'
            f'<div class="o_mtl_kpi_val">{escape(fmt_hours(actual_h or planned_h))} <span>hrs</span></div>'
            f'<div class="o_mtl_kpi_sub">{escape(_("Planned"))}: {escape(fmt_hours(planned_h))} hrs</div>'
            '</div>'
            '<div class="o_mtl_kpi">'
            f'<div class="o_mtl_kpi_lbl"><i class="fa fa-money"></i> {escape(_("Total Cost"))}</div>'
            f'<div class="o_mtl_kpi_val">{escape(currency_symbol)} {escape(fmt_money(self.maintenance_timeline_total or 0.0))}</div>'
            f'<div class="o_mtl_kpi_sub">{escape(_("Electrical + Mechanical + Spare Cost"))}</div>'
            '</div>'
            f'{root_html}'
            '</div>'
            '</div>'
        )

    def action_open_workflow_timeline(self):
        """Open Workflow / Timeline for THIS request (never the list)."""
        self.ensure_one()
        return self._rca_method_window_action(
            'maintenance.maintenance_request_workflow_timeline_form_view',
            _('Workflow / Timeline'),
        )

    def action_open_rul_tobm_report(self):
        """Open Maintenance → Reporting → RUL & TOBM dashboard."""
        return self.env['maintenance.rul.tobm.dashboard'].action_open_rul_tobm_dashboard_client()

    @api.depends(
        'spare_line_ids.stock_status',
        'spare_line_ids.procurement_status',
        'spare_line_ids.product_id',
        'spare_line_ids.spare_name',
    )
    def _compute_spare_unavailable_warning(self):
        for request in self:
            unavailable_spares = request.spare_line_ids.filtered(lambda line: line.stock_status == 'out_of_stock')
            pending = unavailable_spares.filtered(lambda line: line.procurement_status != 'pr_created')
            request.spare_unavailable_warning = bool(unavailable_spares)
            request.spare_pr_pending = bool(pending)
            if pending:
                names = ', '.join(
                    line.product_id.display_name or line.spare_name or '' for line in pending
                )
                request.spare_unavailable_message = _('%s not available -> Purchase required', names)
            elif unavailable_spares:
                names = ', '.join(
                    line.product_id.display_name or line.spare_name or '' for line in unavailable_spares
                )
                request.spare_unavailable_message = _(
                    '%s: purchase request created, awaiting delivery. '
                    'Set Stock Status to Available when the part arrives.',
                    names,
                )
            else:
                request.spare_unavailable_message = False
            request.spare_available_warning = bool(
                request.spare_line_ids.filtered(lambda line: line.stock_status == 'available')
            )

    @api.depends(
        'spare_line_ids.cost',
        'spare_line_ids.quantity',
        'spare_line_ids.critical',
        'spare_line_ids.stock_status',
    )
    def _compute_spares_summary(self):
        for request in self:
            lines = request.spare_line_ids
            request.spare_total_cost = sum(
                (line.quantity or 1.0) * (line.cost or 0.0)
                for line in lines
            )
            request.spare_critical_count = len(lines.filtered('critical'))
            request.spare_item_count = len(lines)
            request.spare_available_count = len(lines.filtered(lambda l: l.stock_status == 'available'))
            request.spare_shortage_count = len(lines.filtered(lambda l: l.stock_status == 'out_of_stock'))

    @api.depends('planned_duration')
    def _compute_planned_hours(self):
        for request in self:
            request.planned_hours = request.planned_duration or 0.0

    @api.depends('planned_hours', 'actual_hours')
    def _compute_delay_hours(self):
        for request in self:
            delay = (request.actual_hours or 0.0) - (request.planned_hours or 0.0)
            request.delay_hours = delay if delay > 0 else 0.0

    @api.depends('planned_hours', 'actual_hours')
    def _compute_execution_metrics(self):
        for request in self:
            max_hours = max(request.planned_hours or 0.0, request.actual_hours or 0.0, 1.0)
            if request.planned_hours:
                request.actual_vs_plan_percent = (request.actual_hours / request.planned_hours) * 100.0
            else:
                request.actual_vs_plan_percent = 0.0
            request.planned_bar_percent = ((request.planned_hours or 0.0) / max_hours) * 100.0
            request.actual_bar_percent = ((request.actual_hours or 0.0) / max_hours) * 100.0

    @api.depends('manpower_line_ids.user_id')
    def _compute_manpower_summary(self):
        for request in self:
            request.responsible_person_id = request.manpower_line_ids[:1].user_id

    def action_save_plan(self):
        self._ensure_planning_record_exists()
        for request in self:
            request.message_post(body=_('Maintenance planning details were saved.'))
        if len(self) == 1:
            return self._action_return_planning_form()
        return True

    def _action_open_execution_form(self):
        """Open the Work Order / execution screen for this request."""
        self.ensure_one()
        view_xmlid = 'maintenance.maintenance_request_execution_form_view'
        view = self.env.ref(view_xmlid, raise_if_not_found=False)
        ctx = dict(
            self.env.context,
            active_id=self.id,
            active_ids=[self.id],
            pm_workflow_step=view_xmlid,
            form_view_ref=view_xmlid,
        )
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Work Order'),
            'res_model': 'maintenance.request',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': ctx,
        }
        if view:
            action['views'] = [(view.id, 'form')]
            action['view_id'] = view.id
        return self._pm_finalize_step_action(action, view_xmlid)

    def action_create_maintenance_order(self):
        """Promote planned request to executable work order and open execution."""
        self._ensure_planning_record_exists()
        stage_new = self.env.ref('maintenance.stage_0', raise_if_not_found=False)
        stage_progress = self.env.ref('maintenance.stage_1', raise_if_not_found=False)

        for request in self:
            if not request.equipment_id:
                raise UserError(_('Select equipment before creating a maintenance order.'))
            if not request.planned_date and not request.planning_maintenance_type:
                raise UserError(_(
                    'Complete maintenance planning first:\n'
                    '- Planned Date\n'
                    '- Maintenance Type (Breakdown / Preventive / Predictive)'
                ))
            if request.stage_id and request.stage_id.done:
                raise UserError(_(
                    'This request is already closed. Reopen it or create a new maintenance request.'
                ))
            if request.execution_status == 'completed':
                raise UserError(_('This work order is already completed.'))

            vals = {'execution_status': 'in_progress'}
            if stage_progress and (
                not request.stage_id
                or (stage_new and request.stage_id == stage_new)
            ):
                vals['stage_id'] = stage_progress.id
            if not (request.work_order_sequence or '').strip():
                vals['work_order_sequence'] = _('WO-%s') % request.id
            if not request.user_id:
                technician = request.manpower_line_ids[:1].user_id
                if not technician and request.equipment_id:
                    if request.maintenance_type == 'corrective':
                        technician = request.equipment_id.corrective_responsible_user_id
                    elif request.maintenance_type == 'preventive':
                        technician = request.equipment_id.preventive_responsible_user_id
                    else:
                        technician = request.equipment_id.predictive_responsible_user_id
                if technician:
                    vals['user_id'] = technician.id

            request.write(vals)
            if not request.condition_readings_manual:
                request._apply_auto_condition_readings()
            request.message_post(
                body=_(
                    'Maintenance order <b>%s</b> created from planning. '
                    'Stage set to In Progress — open execution to complete the job.',
                    request.work_order_display,
                ),
            )

        if len(self) == 1:
            return self._action_open_execution_form()
        return True

    def _action_return_planning_form(self):
        """Reopen this planning form (reliable after writes; avoids broken page reload)."""
        self.ensure_one()
        view_xmlid = 'maintenance.maintenance_request_planning_form_view'
        view = self.env.ref(view_xmlid, raise_if_not_found=False)
        ctx = dict(
            self.env.context,
            active_id=self.id,
            active_ids=[self.id],
            pm_workflow_step=view_xmlid,
            form_view_ref=view_xmlid,
        )
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Maintenance Planning'),
            'res_model': 'maintenance.request',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': ctx,
        }
        if view:
            action['views'] = [(view.id, 'form')]
            action['view_id'] = view.id
        return self._pm_finalize_step_action(action, view_xmlid)

    def _ensure_planning_record_exists(self):
        self.ensure_one()
        if not self.exists():
            raise UserError(_(
                'This work order is no longer available (it was recreated during module upgrade).\n\n'
                'Close this tab, go to Maintenance → Planning, and open the work order again.'
            ))

    def action_issue_from_store(self):
        self._ensure_planning_record_exists()
        if not self.spare_line_ids:
            raise UserError(_(
                'No spare lines found.\n\n'
                'In Spare Planning, click "Add a line", enter the spare part, set Stock Status to Available, then click Issue from Store.'
            ))
        lines_to_issue = self.spare_line_ids.filtered(
            lambda line: line.stock_status == 'available'
            and line.procurement_status != 'issued_from_store'
        )
        if not lines_to_issue:
            raise UserError(_(
                'No available spare lines to issue from store.\n\n'
                'Use Create Purchase Request for out-of-stock items, or set a line to Available first.'
            ))

        lines_to_issue.write({'procurement_status': 'issued_from_store'})
        self.message_post(
            body=_('Issued %(count)s spare line(s) from store.', count=len(lines_to_issue))
        )
        return self._action_return_spare_workflow_form()

    def action_create_purchase_request(self):
        self._ensure_planning_record_exists()
        if not self.spare_line_ids:
            raise UserError(_(
                'No spare lines found.\n\n'
                'In Spare Planning, click "Add a line", enter the spare part, set Stock Status to Out of Stock, then click Create Purchase Request.'
            ))
        lines_to_procure = self.spare_line_ids.filtered(
            lambda line: line.procurement_status != 'pr_created'
            and line.stock_status == 'out_of_stock'
        )
        if not lines_to_procure:
            if self.spare_line_ids.filtered(lambda line: line.procurement_status == 'pr_created'):
                raise UserError(_('Purchase request is already created for all spare lines on this work order.'))
            raise UserError(_(
                'No out-of-stock spare lines to purchase.\n\n'
                'Set Stock Status to Out of Stock on the spare lines you need to buy, then click Create Purchase Request again.'
            ))

        lines_to_procure.write({'procurement_status': 'pr_created'})
        names = ', '.join(filter(None, lines_to_procure.mapped('spare_name')))
        self.message_post(
            body=_(
                'Purchase request created for %(count)s spare line(s): %(names)s',
                count=len(lines_to_procure),
                names=names,
            )
        )
        return self._action_return_spare_workflow_form()

    def _action_return_spare_workflow_form(self):
        """Stay on Inventory & Spares when that step is open; otherwise Planning."""
        self.ensure_one()
        step = (
            self.env.context.get('pm_workflow_step')
            or self.env.context.get('form_view_ref')
            or ''
        )
        if 'spares' in step and hasattr(self, 'action_workflow_inventory_spares'):
            return self.action_workflow_inventory_spares()
        return self._action_return_planning_form()

    @api.model
    def ensure_demo_spare_planning_lines(self):
        """Add missing spare lines on demo WOs without deleting/replacing requests."""
        Spare = self.env['maintenance.request.spare.line'].sudo()
        Request = self.env['maintenance.request'].sudo()
        templates = {
            'WO-DEMO-PM-VAN-Q': [
                {
                    'spare_name': 'Engine oil 5W-30 (6 qt)',
                    'quantity': 1,
                    'cost': 52,
                    'stock_status': 'available',
                    'procurement_status': 'issued_from_store',
                    'lead_time': 'Same day',
                },
                {
                    'spare_name': 'Brake fluid DOT 4 (1 L)',
                    'quantity': 2,
                    'cost': 18,
                    'stock_status': 'out_of_stock',
                    'procurement_status': 'none',
                    'lead_time': '2-3 days',
                },
                {
                    'spare_name': 'Cabin / marker bulb kit',
                    'quantity': 1,
                    'cost': 24,
                    'stock_status': 'out_of_stock',
                    'procurement_status': 'none',
                    'lead_time': '1-2 days',
                },
            ],
            'WO-DEMO-PM-TRL-A': [
                {
                    'spare_name': 'Hub seal kit - tandem axle',
                    'quantity': 2,
                    'cost': 118,
                    'stock_status': 'out_of_stock',
                    'procurement_status': 'none',
                    'lead_time': '3-5 days',
                },
                {
                    'spare_name': 'Brake shoe set - trailer',
                    'quantity': 1,
                    'cost': 245,
                    'stock_status': 'out_of_stock',
                    'procurement_status': 'none',
                    'lead_time': '5-7 days',
                },
                {
                    'spare_name': 'LED marker light assembly',
                    'quantity': 4,
                    'cost': 64,
                    'stock_status': 'available',
                    'procurement_status': 'none',
                    'lead_time': 'Same day',
                },
            ],
        }
        for wo_code, lines in templates.items():
            request = Request.search([('work_order_sequence', '=', wo_code)], limit=1)
            if not request:
                continue
            existing_names = set(filter(None, request.spare_line_ids.mapped('spare_name')))
            for vals in lines:
                if vals['spare_name'] in existing_names:
                    continue
                Spare.create(dict(vals, request_id=request.id))
        return True

    def action_pause_work(self):
        for request in self:
            request.execution_status = 'paused'
            request.message_post(body=_('Work has been paused from execution tab.'))
        return True

    def action_complete_work_order(self):
        self._raise_if_rca_missing_for_closure()
        for request in self:
            request.execution_status = 'completed'
            request.go_no_go_decision = 'go'
            request.message_post(body=_('Work order marked as completed.'))
        return True

    def action_mark_go(self):
        self.write({'go_no_go_decision': 'go'})
        self.filtered(lambda r: not r.condition_readings_manual)._apply_auto_condition_readings()
        if len(self) == 1:
            return self._action_open_execution_form()
        return True

    def action_mark_no_go(self):
        self.write({'go_no_go_decision': 'no_go'})
        self.filtered(lambda r: not r.condition_readings_manual)._apply_auto_condition_readings()
        if len(self) == 1:
            return self._action_open_execution_form()
        return True

    def action_open_no_go_dashboard(self):
        self.ensure_one()
        view = self.env.ref(
            'maintenance.maintenance_request_nogo_form_view',
            raise_if_not_found=False,
        )
        if view:
            return {
                'type': 'ir.actions.act_window',
                'name': _('No-Go Decision'),
                'res_model': 'maintenance.request',
                'res_id': self.id,
                'view_mode': 'form',
                'views': [(view.id, 'form')],
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('No-Go Decision Dashboard'),
            'res_model': 'maintenance.request',
            'view_mode': 'graph,pivot,list',
            'views': [
                (self.env.ref('maintenance.maintenance_request_no_go_graph_view').id, 'graph'),
                (False, 'pivot'),
                (self.env.ref('maintenance.hr_equipment_request_view_tree').id, 'list'),
            ],
            'domain': [('go_no_go_decision', '=', 'no_go')],
            'context': {'search_default_active': 1},
        }

    def unlink(self):
        companies = self.mapped('company_id').filtered(lambda c: c) or self.env.company
        res = super().unlink()
        self.env['maintenance.analytics.dashboard']._invalidate_for_companies(companies)
        return res

    def action_open_rca_mom_form(self):
        """Open RCA Fishbone screen (default entry for RCA & MOM)."""
        self.ensure_one()
        return self.action_open_rca_fishbone()

    def action_open_rca_all_cases(self):
        """List maintenance requests that have RCA data."""
        return self.env.ref('maintenance.maintenance_rca_all_cases_action')._get_action_dict()

    def action_open_rul_from_rca(self):
        """RUL report removed — open standard Maintenance Teams dashboard."""
        return self.env['ir.actions.act_window']._for_xml_id(
            'maintenance.maintenance_dashboard_action'
        )


class MaintenanceRequestSpareLine(models.Model):
    _name = 'maintenance.request.spare.line'
    _description = 'Maintenance Request Spare Planning Line'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'maintenance.request',
        string='Maintenance Request',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(string='#', default=10)
    product_id = fields.Many2one(
        'product.product',
        string='Spare Product',
    )
    spare_name = fields.Char(string='Spare Name')
    critical = fields.Boolean(string='Critical')
    dependency_component = fields.Char(string='Dependent On')
    quantity = fields.Float(string='Quantity', default=1.0)
    cost = fields.Monetary(string='Unit Cost', currency_field='currency_id')
    line_total = fields.Monetary(
        string='Total Cost',
        currency_field='currency_id',
        compute='_compute_line_total',
    )
    part_code = fields.Char(string='Part Code')
    available_qty = fields.Float(
        string='Available Qty',
        compute='_compute_inventory_availability',
        digits='Product Unit of Measure',
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency', related='request_id.currency_id', store=True, readonly=True
    )
    stock_status = fields.Selection(
        [('available', 'Available'), ('out_of_stock', 'Out of Stock')],
        string='Stock Status',
        default='available',
        required=True,
    )
    procurement_status = fields.Selection(
        [
            ('none', 'None'),
            ('pr_created', 'PR Created'),
            ('issued_from_store', 'Issued from Store'),
        ],
        string='Procurement / Issue',
        default='none',
        required=True,
    )
    lead_time = fields.Char(string='Lead Time')

    @api.depends('product_id', 'quantity')
    def _compute_inventory_availability(self):
        for line in self:
            if line.product_id:
                available_qty = line.product_id.qty_available
                line.available_qty = available_qty
                line.stock_status = 'available' if available_qty >= (line.quantity or 0.0) else 'out_of_stock'
            else:
                line.available_qty = 0.0

    @api.depends('quantity', 'cost')
    def _compute_line_total(self):
        for line in self:
            line.line_total = (line.quantity or 0.0) * (line.cost or 0.0)

    @api.onchange('product_id')
    def _onchange_product_id_inventory(self):
        for line in self:
            if line.product_id:
                line.spare_name = line.product_id.display_name
                line.cost = line.product_id.standard_price
                if line.product_id.default_code:
                    line.part_code = line.product_id.default_code


class MaintenanceTeam(models.Model):
    _name = 'maintenance.team'
    _description = 'Maintenance Teams'

    name = fields.Char('Team Name', required=True, translate=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string='Company',
        default=lambda self: self.env.company)
    member_ids = fields.Many2many(
        'res.users', 'maintenance_team_users_rel', string="Team Members",
        domain="[('company_ids', 'in', company_id)]")
    color = fields.Integer("Color Index", default=0)
    request_ids = fields.One2many('maintenance.request', 'maintenance_team_id', copy=False)
    equipment_ids = fields.One2many('maintenance.equipment', 'maintenance_team_id', copy=False)
    equipment_count = fields.Integer(string='Assets', compute='_compute_equipment')

    # For the dashboard only
    todo_request_ids = fields.One2many('maintenance.request', string="Requests", copy=False, compute='_compute_todo_requests')
    todo_request_count = fields.Integer(string="Number of Requests", compute='_compute_todo_requests')
    todo_request_count_date = fields.Integer(string="Number of Requests Scheduled", compute='_compute_todo_requests')
    todo_request_count_high_priority = fields.Integer(string="Number of Requests in High Priority", compute='_compute_todo_requests')
    todo_request_count_block = fields.Integer(string="Number of Requests Blocked", compute='_compute_todo_requests')
    todo_request_count_unscheduled = fields.Integer(string="Number of Requests Unscheduled", compute='_compute_todo_requests')
    dashboard_health_pct = fields.Integer(string='Health %', compute='_compute_todo_requests')
    dashboard_workload_label = fields.Char(string='Workload', compute='_compute_todo_requests')
    dashboard_workload_class = fields.Char(string='Workload class', compute='_compute_todo_requests')

    @api.depends('request_ids.stage_id.done')
    def _compute_todo_requests(self):
        for team in self:
            team.todo_request_ids = self.env['maintenance.request'].search([('maintenance_team_id', '=', team.id), ('stage_id.done', '=', False), ('archive', '=', False)])
            data = self.env['maintenance.request']._read_group(
                [('maintenance_team_id', '=', team.id), ('stage_id.done', '=', False), ('archive', '=', False)],
                ['schedule_date:year', 'priority', 'kanban_state'],
                ['__count']
            )
            team.todo_request_count = sum(count for (_, _, _, count) in data)
            team.todo_request_count_date = sum(count for (schedule_date, _, _, count) in data if schedule_date)
            team.todo_request_count_high_priority = sum(count for (_, priority, _, count) in data if priority == '3')
            team.todo_request_count_block = sum(count for (_, _, kanban_state, count) in data if kanban_state == 'blocked')
            team.todo_request_count_unscheduled = team.todo_request_count - team.todo_request_count_date
            open_c = team.todo_request_count or 0
            risk = (
                open_c
                + (team.todo_request_count_high_priority or 0) * 2
                + (team.todo_request_count_block or 0) * 3
                + (team.todo_request_count_unscheduled or 0)
            )
            team.dashboard_health_pct = max(0, min(100, 100 - risk * 10))
            if risk == 0:
                team.dashboard_workload_label = _('Optimal')
                team.dashboard_workload_class = 'optimal'
            elif risk <= 4:
                team.dashboard_workload_label = _('Watch')
                team.dashboard_workload_class = 'watch'
            else:
                team.dashboard_workload_label = _('Critical')
                team.dashboard_workload_class = 'critical'

    def action_open_rca_mom(self):
        """Open RCA & MOM list/form for requests belonging to this maintenance team (dashboard entry)."""
        self.ensure_one()
        action = dict(self.env.ref('maintenance.maintenance_rca_action')._get_action_dict())
        raw_ctx = action.get('context') or '{}'
        if isinstance(raw_ctx, str):
            ctx = safe_eval(raw_ctx, self.env['ir.actions.actions']._get_eval_context())
        else:
            ctx = dict(raw_ctx)
        ctx['search_default_active'] = True
        ctx['default_maintenance_team_id'] = self.id
        action['context'] = ctx
        action['domain'] = [('maintenance_team_id', '=', self.id), ('archive', '=', False)]
        return action

    def action_open_rcm_tobm(self):
        """Open RUL & TOBM predictive dashboard from the team command card."""
        self.ensure_one()
        return self.env['maintenance.rul.tobm.dashboard'].action_open_rul_tobm_dashboard_client()

    @api.depends('equipment_ids')
    def _compute_equipment(self):
        for team in self:
            team.equipment_count = len(team.equipment_ids)


class MaintenanceRequestDocument(models.Model):
    _name = 'maintenance.request.document'
    _description = 'Maintenance Request Document'
    _order = 'id'

    request_id = fields.Many2one(
        'maintenance.request',
        string='Maintenance Request',
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(string='Document Name', required=True)
    document_type = fields.Selection(
        [
            ('manual', 'Manual'),
            ('diagram', 'Diagram'),
            ('guide', 'Guide'),
            ('photo', 'Camera / Photo'),
            ('excel', 'Excel'),
            ('other', 'Other'),
        ],
        string='Type',
        default='manual',
        required=True,
    )
    attachment = fields.Binary(string='File', attachment=True)
    attachment_name = fields.Char(string='Filename')
    upload_date = fields.Datetime(
        string='Upload Date',
        related='create_date',
        readonly=True,
    )


class MaintenanceRequestManpowerLine(models.Model):
    _name = 'maintenance.request.manpower.line'
    _description = 'Maintenance Request Manpower Line'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        'maintenance.request',
        string='Maintenance Request',
        required=True,
        ondelete='cascade',
    )
    user_id = fields.Many2one(
        'res.users',
        string='Name & Role',
        required=True,
        domain=[('share', '=', False)],
    )
    skill_type = fields.Selection(
        [('electrical', 'Electrical'), ('mechanical', 'Mechanical'), ('vendor', 'Vendor'), ('other', 'Other')],
        string='Skill Type',
        default='mechanical',
        required=True,
    )
    status = fields.Selection(
        [('available', 'Available'), ('busy', 'Busy')],
        string='Availability',
        default='available',
        required=True,
    )
    assigned_task = fields.Char(string='Assigned Task')
    planned_hours = fields.Float(string='Planned Hours', default=1.0)
    notes = fields.Char(string='Notes')
    sequence = fields.Integer(string='#', default=1)


class MaintenanceRequestRcaLine(models.Model):
    _name = 'maintenance.request.rca.line'
    _description = 'Maintenance Request RCA Line'
    _order = 'sequence, id'

    request_id = fields.Many2one('maintenance.request', required=True, ondelete='cascade')
    sequence = fields.Integer(default=1)
    problem_statement = fields.Char(string='Why', required=True)
    cause_statement = fields.Char(string='Because', required=True)


class MaintenanceRequestCorrectiveAction(models.Model):
    _name = 'maintenance.request.corrective.action'
    _description = 'Maintenance Request Corrective Action'
    _order = 'id'

    request_id = fields.Many2one('maintenance.request', required=True, ondelete='cascade')
    name = fields.Char(string='Action', required=True)
    done = fields.Boolean(string='Done')


class MaintenanceRcaCase(models.Model):
    _name = 'maintenance.rca.case'
    _description = 'Maintenance RCA Case'
    _order = 'id desc'

    name = fields.Char(string='Issue', required=True, default='Truck not starting')
    equipment_label = fields.Char(string='Equipment', default='Vehicle-01 (Truck)')
    work_order_ref = fields.Char(string='Work Order', default='WO-2045')
    owner_label = fields.Char(string='Owner', default='Admin')
    owner_role = fields.Char(string='Role', default='Plant Manager')

    discussion = fields.Text(string='Discussion')
    decision = fields.Text(string='Decision')
    action_owner = fields.Char(string='Action Owner')
    final_root_cause = fields.Char(string='Final Root Cause')

    fishbone_summary = fields.Text(string='Fishbone Analysis')
    fault_tree_summary = fields.Text(string='Fault Tree Analysis')
    fmea_summary = fields.Text(string='FMEA Analysis')
    pareto_summary = fields.Text(string='Pareto Analysis')
    ai_rca_summary = fields.Text(string='AI RCA Insight')

    why_line_ids = fields.One2many('maintenance.rca.why.line', 'case_id', string='5 Why Lines', copy=True)
    corrective_action_ids = fields.One2many('maintenance.rca.corrective.action', 'case_id', string='Corrective Actions', copy=True)


class MaintenanceRcaWhyLine(models.Model):
    _name = 'maintenance.rca.why.line'
    _description = 'Maintenance RCA Why Line'
    _order = 'sequence, id'

    case_id = fields.Many2one('maintenance.rca.case', required=True, ondelete='cascade')
    sequence = fields.Integer(default=1)
    why_text = fields.Char(string='Why', required=True)
    cause_text = fields.Char(string='Cause', required=True)


class MaintenanceRcaCorrectiveAction(models.Model):
    _name = 'maintenance.rca.corrective.action'
    _description = 'Maintenance RCA Corrective Action'
    _order = 'id'

    case_id = fields.Many2one('maintenance.rca.case', required=True, ondelete='cascade')
    name = fields.Char(string='Action', required=True)
    done = fields.Boolean(string='Done')


class MaintenanceAnalyticsDashboard(models.Model):
    _name = 'maintenance.analytics.dashboard'
    _description = 'Maintenance Analytics Dashboard'

    name = fields.Char(default='Maintenance Analytics', required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_maintenance_cost_currency_id',
        readonly=True,
        help='Dashboard cost KPIs use US dollars (USD).',
    )
    analytics_mode = fields.Selection(
        [('use_case', 'Use Case Only'), ('live', 'Live Data')],
        string='Analytics Source',
        default='live',
        required=True,
    )
    use_case_request_id = fields.Many2one(
        'maintenance.request',
        string='Use Case',
        domain="[('archive', '=', False)]",
        help='When source is Use Case Only, KPIs use only this request (and its equipment).',
    )
    fleet_vehicle_scope = fields.Boolean(
        string='Fleet / vehicle equipment only',
        default=False,
        help='When enabled, only maintenance requests whose equipment category or name matches vehicle/fleet/forklift keywords are included.',
    )
    analysis_period_days = fields.Integer(
        string='Analysis period (days)',
        default=30,
        help='Include maintenance requests whose request date is within this many days before today (1–365).',
    )
    dashboard_html = fields.Html(
        string='Dashboard HTML',
        compute='_compute_analytics_dashboard',
        sanitize=False,
    )

    mttr_hours = fields.Float(string='MTTR (hrs)', compute='_compute_analytics_dashboard')
    mtbf_days = fields.Float(string='MTBF (days)', compute='_compute_analytics_dashboard')
    total_cost_value = fields.Monetary(string='Total Cost', currency_field='currency_id', compute='_compute_analytics_dashboard')
    total_failures = fields.Integer(string='Total Failures', compute='_compute_analytics_dashboard')

    eq1_name = fields.Char(compute='_compute_analytics_dashboard')
    eq1_mttr = fields.Float(compute='_compute_analytics_dashboard')
    eq1_mttr_bar = fields.Float(compute='_compute_analytics_dashboard')
    eq2_name = fields.Char(compute='_compute_analytics_dashboard')
    eq2_mttr = fields.Float(compute='_compute_analytics_dashboard')
    eq2_mttr_bar = fields.Float(compute='_compute_analytics_dashboard')
    eq3_name = fields.Char(compute='_compute_analytics_dashboard')
    eq3_mttr = fields.Float(compute='_compute_analytics_dashboard')
    eq3_mttr_bar = fields.Float(compute='_compute_analytics_dashboard')

    cost_gearbox = fields.Monetary(currency_field='currency_id', compute='_compute_analytics_dashboard')
    cost_crane = fields.Monetary(currency_field='currency_id', compute='_compute_analytics_dashboard')
    cost_vehicle = fields.Monetary(currency_field='currency_id', compute='_compute_analytics_dashboard')

    planned_vehicle = fields.Float(compute='_compute_analytics_dashboard')
    actual_vehicle = fields.Float(compute='_compute_analytics_dashboard')
    delayed_vehicle = fields.Float(compute='_compute_analytics_dashboard')
    planned_gearbox = fields.Float(compute='_compute_analytics_dashboard')
    actual_gearbox = fields.Float(compute='_compute_analytics_dashboard')
    delayed_gearbox = fields.Float(compute='_compute_analytics_dashboard')
    planned_gearbox_pct = fields.Float(compute='_compute_analytics_dashboard')
    actual_gearbox_pct = fields.Float(compute='_compute_analytics_dashboard')
    planned_vehicle_pct = fields.Float(compute='_compute_analytics_dashboard')
    actual_vehicle_pct = fields.Float(compute='_compute_analytics_dashboard')

    health_1_name = fields.Char(compute='_compute_analytics_dashboard')
    health_1_note = fields.Char(compute='_compute_analytics_dashboard')
    health_1_state = fields.Selection(
        [('critical', 'Critical'), ('warning', 'Warning'), ('stable', 'Stable')],
        compute='_compute_analytics_dashboard',
    )
    health_2_name = fields.Char(compute='_compute_analytics_dashboard')
    health_2_note = fields.Char(compute='_compute_analytics_dashboard')
    health_2_state = fields.Selection(
        [('critical', 'Critical'), ('warning', 'Warning'), ('stable', 'Stable')],
        compute='_compute_analytics_dashboard',
    )
    health_3_name = fields.Char(compute='_compute_analytics_dashboard')
    health_3_note = fields.Char(compute='_compute_analytics_dashboard')
    health_3_state = fields.Selection(
        [('critical', 'Critical'), ('warning', 'Warning'), ('stable', 'Stable')],
        compute='_compute_analytics_dashboard',
    )

    @api.constrains('analysis_period_days')
    def _check_analysis_period_days(self):
        for rec in self:
            d = rec.analysis_period_days or 0
            if d < 1 or d > 365:
                raise ValidationError(_('Analysis period must be between 1 and 365 days.'))

    def action_refresh_analytics(self):
        self.ensure_one()
        self.invalidate_recordset()
        return self._open_analytics_dashboard()

    def action_apply_filters(self):
        """Save filter fields and force KPI recomputation."""
        self.ensure_one()
        self.invalidate_recordset()
        return self._open_analytics_dashboard()

    def _open_analytics_dashboard(self):
        self.ensure_one()
        view = self.env.ref('maintenance.maintenance_analytics_dashboard_form_view')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Maintenance Analytics'),
            'res_model': 'maintenance.analytics.dashboard',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': view.id,
            'views': [(view.id, 'form')],
            'target': 'current',
        }

    def action_open_maintenance_requests(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('maintenance.hr_equipment_request_action')
        action = dict(action)
        action['domain'] = self._dashboard_request_domain()
        action['context'] = dict(
            self.env.context,
            default_company_id=self.company_id.id,
            search_default_active=True,
        )
        action['target'] = 'current'
        return action

    def action_create_maintenance_request(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('maintenance.hr_equipment_request_action')
        action = dict(action)
        action['view_mode'] = 'form'
        action['views'] = [(False, 'form')]
        action['target'] = 'current'
        action['context'] = dict(
            self.env.context,
            default_company_id=self.company_id.id,
        )
        return action

    @api.model
    def _notify_analytics_refresh(self, companies):
        if 'bus.bus' not in self.env:
            return
        companies = companies.filtered(lambda c: c) if companies else self.env['res.company'].browse()
        for company in companies:
            channel = f'maintenance_analytics_{company.id}'
            self.env['bus.bus']._sendone(
                channel,
                'maintenance/analytics_refresh',
                {'company_id': company.id},
            )

    @api.model
    def _invalidate_for_companies(self, companies):
        """Drop cached KPIs so the next open of Analytics recomputes from live DB."""
        companies = companies.filtered(lambda c: c) if companies else self.env['res.company'].browse()
        if not companies:
            return
        dashboards = self.sudo().search([('company_id', 'in', companies.ids)])
        if dashboards:
            dashboards.invalidate_recordset()
        self._notify_analytics_refresh(companies)
        self.env['maintenance.rul.tobm.dashboard']._invalidate_rul_for_companies(companies)


    @api.model
    def _short_equipment_label(self, display_name, max_len=32):
        full = str(display_name or '').strip()
        short = full.split('/')[0].strip() if '/' in full else full
        if len(short) > max_len:
            short = f'{short[: max_len - 1]}…'
        return short

    def _equipment_label_pair(self, display_name):
        full = str(display_name or '').strip()
        return {'name': self._short_equipment_label(full), 'name_full': full}

    def _dashboard_request_domain(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        # The main dashboard record may keep an old stored value (XML can't override when noupdate=1).
        # Force it back to 365 days so user equipment/request examples appear consistently.
        try:
            main_id = self.env.ref('maintenance.maintenance_analytics_dashboard_main', raise_if_not_found=False)
            is_main = bool(main_id) and (self.id == main_id.id)
        except Exception:
            is_main = False
        days = 365 if is_main else max(min(self.analysis_period_days or 30, 365), 1)
        from_date = today - timedelta(days=days)
        domain = [
            ('archive', '=', False),
            ('company_id', '=', self.company_id.id),
            ('request_date', '>=', from_date),
        ]
        if self.fleet_vehicle_scope:
            fleet_or = [
                '|', '|', '|',
                ('equipment_id.category_id.name', 'ilike', 'vehicle'),
                ('equipment_id.category_id.name', 'ilike', 'fleet'),
                ('equipment_id.name', 'ilike', 'vehicle'),
                ('equipment_id.name', 'ilike', 'forklift'),
            ]
            domain = expression.AND([domain, fleet_or])
        return domain

    def _get_dashboard_requests(self):
        self.ensure_one()
        if self.analytics_mode == 'use_case' and self.use_case_request_id:
            return self.use_case_request_id
        return self.env['maintenance.request'].search(self._dashboard_request_domain(), order='request_date desc')

    def _analytics_stats(self):
        """Return a dict of real metrics only (no placeholder KPIs)."""
        self.ensure_one()
        reqs = self._get_dashboard_requests()
        req_count = len(reqs)
        closed_count = len(reqs.filtered(lambda r: r.stage_id and r.stage_id.done))
        open_count = max(req_count - closed_count, 0)

        done_dated = reqs.filtered(
            lambda r: r.stage_id and r.stage_id.done and r.request_date and r.close_date
        )
        mttr_hours_list = [
            max((rec.close_date - rec.request_date).days, 0) * 24.0
            for rec in done_dated
        ]
        mttr_headline = round(sum(mttr_hours_list) / len(mttr_hours_list), 1) if mttr_hours_list else 0.0

        # MTTR per equipment (same definition as headline: calendar open→close, hours)
        mttr_by_eq = defaultdict(list)
        for rec in done_dated:
            if rec.equipment_id:
                hrs = max((rec.close_date - rec.request_date).days, 0) * 24.0
                mttr_by_eq[rec.equipment_id].append(hrs)
        mttr_avg_by_eq = []
        for eq, vals in mttr_by_eq.items():
            avg_h = round(sum(vals) / len(vals), 1)
            mttr_avg_by_eq.append((eq.display_name, avg_h))
        mttr_avg_by_eq.sort(key=lambda x: x[1], reverse=True)
        top_mttr = mttr_avg_by_eq[:3]
        max_mttr_bar = max((v for _, v in top_mttr), default=0.0) or 1.0
        mttr_rows = [{**self._equipment_label_pair(n), 'hours': h, 'bar_pct': (h / max_mttr_bar) * 100.0} for n, h in top_mttr]

        mttr_alert = None
        if mttr_hours_list and mttr_avg_by_eq:
            overall = mttr_headline
            worst_name, worst_h = mttr_avg_by_eq[0]
            worst_short = self._short_equipment_label(worst_name)
            if worst_h > overall * 1.05 and overall > 0:
                mttr_alert = _('%(name)s: %(hrs)s hrs average vs %(avg)s hrs overall') % {
                    'name': worst_short,
                    'hrs': worst_h,
                    'avg': overall,
                }
            elif worst_h > 0 and overall == 0:
                mttr_alert = _('%(name)s: longest average repair window in this period') % {'name': worst_name}

        equipments = reqs.mapped('equipment_id').filtered(lambda e: e)
        mtbf_vals = [float(e.mtbf or 0) for e in equipments]
        mtbf_headline = round(sum(mtbf_vals) / len(mtbf_vals), 1) if mtbf_vals else 0.0

        mtbf_rows = sorted(
            [{**self._equipment_label_pair(e.display_name), 'days': int(e.mtbf or 0)} for e in equipments],
            key=lambda row: row['days'],
            reverse=True,
        )[:5]

        stability_note = None
        positive = [r for r in mtbf_rows if r['days'] > 0]
        if positive:
            best = positive[0]
            stability_note = _('Highest computed MTBF: %(name)s (%(days)s days)') % {
                'name': best.get('name_full') or best['name'],
                'days': best['days'],
            }

        total_cost = round(sum(reqs.mapped('total_cost')) or 0.0, 2)

        cost_by_equipment = defaultdict(float)
        for req in reqs:
            if not req.equipment_id:
                continue
            cost_by_equipment[req.equipment_id.display_name] += req.total_cost or 0.0
        cost_list = sorted(cost_by_equipment.items(), key=lambda item: item[1], reverse=True)
        colors = ['#f59e0b', '#2563eb', '#10b981']
        cost_slices = [
            {**self._equipment_label_pair(n), 'amount': round(a, 2), 'color': colors[i % len(colors)]}
            for i, (n, a) in enumerate(cost_list[:3])
        ]

        if reqs.ids:
            rg_time = self.env['maintenance.request'].read_group(
                [('id', 'in', reqs.ids)],
                ['planned_hours:sum', 'actual_hours:sum', 'delay_hours:sum'],
                ['equipment_id'],
                lazy=False,
            )
            time_list = []
            for row in rg_time:
                eq = row.get('equipment_id')
                if not eq:
                    continue
                name = eq[1] if isinstance(eq, (list, tuple)) else str(eq)
                time_list.append({
                    **self._equipment_label_pair(name),
                    'planned': row.get('planned_hours') or 0.0,
                    'actual': row.get('actual_hours') or 0.0,
                    'delay': row.get('delay_hours') or 0.0,
                })
            time_list.sort(key=lambda x: x['planned'] + x['actual'], reverse=True)
        else:
            time_list = []
        time_rows = time_list[:5]

        risky = reqs.filtered(lambda r: (r.failure_risk_percent or 0.0) > 0).sorted(
            key=lambda r: (r.failure_risk_percent or 0.0), reverse=True
        )[:5]
        health_rows = []
        for rec in risky:
            pct = int(rec.failure_risk_percent or 0)
            if pct >= 66:
                state = 'critical'
                accent = '#ef4444'
            elif pct >= 33:
                state = 'warning'
                accent = '#f59e0b'
            else:
                state = 'stable'
                accent = '#10b981'
            health_rows.append({
                **self._equipment_label_pair(rec.equipment_id.display_name if rec.equipment_id else rec.name),
                'note': _('%s%% risk') % pct,
                'state': state,
                'accent': accent,
            })

        total_failures = len(reqs.filtered(lambda r: r.go_no_go_decision == 'no_go'))
        equipment_count = len(equipments)

        # Request mix by maintenance type
        type_counts = {
            'corrective': len(reqs.filtered(lambda r: r.maintenance_type == 'corrective')),
            'preventive': len(reqs.filtered(lambda r: r.maintenance_type == 'preventive')),
            'predictive': len(reqs.filtered(lambda r: r.maintenance_type == 'predictive')),
        }
        preventive_total = type_counts['preventive']
        preventive_closed = len(reqs.filtered(lambda r: r.maintenance_type == 'preventive' and r.stage_id and r.stage_id.done))
        pm_compliance_pct = round((preventive_closed / preventive_total) * 100.0, 1) if preventive_total else 0.0

        # Last 6 months trend (request count)
        today = fields.Date.context_today(self)
        month_labels = []
        month_counts_map = defaultdict(int)
        for i in range(5, -1, -1):
            month_date = today - relativedelta(months=i)
            month_key = month_date.strftime('%Y-%m')
            month_labels.append((month_key, month_date.strftime('%b %Y')))
        for req in reqs:
            if not req.request_date:
                continue
            key = req.request_date.strftime('%Y-%m')
            month_counts_map[key] += 1
        trend_monthly = [
            {'key': key, 'label': label, 'count': month_counts_map.get(key, 0)}
            for key, label in month_labels
        ]

        # Keep main analytics dashboard consistent even if an older DB row still has
        # analysis_period_days=20 (noupdate=1 XML can't override stored values).
        try:
            main_id = self.env.ref('maintenance.maintenance_analytics_dashboard_main', raise_if_not_found=False)
            is_main = bool(main_id) and (self.id == main_id.id)
        except Exception:
            is_main = False
        days = 365 if is_main else max(min(self.analysis_period_days or 30, 365), 1)
        total_delay_hours = round(
            sum(max(req.delay_hours or 0.0, 0.0) for req in reqs),
            1,
        )
        top_delayed = sorted(time_list, key=lambda x: x.get('delay', 0.0) or 0.0, reverse=True)[:3]
        return {
            'from_date': fields.Date.context_today(self) - timedelta(days=days),
            'period_days': days,
            'req_count': req_count,
            'open_count': open_count,
            'closed_count': closed_count,
            'equipment_count': equipment_count,
            'pm_compliance_pct': pm_compliance_pct,
            'mttr_hours': mttr_headline,
            'mttr_sample_count': len(mttr_hours_list),
            'mtbf_days': mtbf_headline,
            'mtbf_asset_count': len(mtbf_vals),
            'total_cost': total_cost,
            'total_failures': total_failures,
            'total_delay_hours': total_delay_hours,
            'mttr_rows': mttr_rows,
            'mttr_alert': mttr_alert,
            'mtbf_rows': mtbf_rows,
            'stability_note': stability_note,
            'cost_slices': cost_slices,
            'time_rows': time_rows,
            'top_delayed_rows': top_delayed,
            'health_rows': health_rows,
            'type_counts': type_counts,
            'trend_monthly': trend_monthly,
            'refreshed_at': fields.Datetime.now(),
        }

    def _render_dashboard_html(self, stats):
        self.ensure_one()

        def fmt_number(value, digits=0):
            value = value or 0.0
            if digits == 0 and abs(value - round(value)) < 0.01:
                return str(int(round(value)))
            return f'{value:.{digits}f}'

        def fmt_hours(value):
            value = value or 0.0
            return str(int(round(value))) if abs(value - round(value)) < 0.01 else f'{value:.1f}'

        def fmt_money(value):
            value = value or 0.0
            return f'{int(round(value)):,}' if abs(value - round(value)) < 0.01 else f'{value:,.2f}'

        def pct(value, total):
            if not total:
                return 0.0
            return max(min((value / total) * 100.0, 100.0), 0.0)

        def fmt_dt(value):
            if not value:
                return ''
            return fields.Datetime.to_string(value)


        def eq_label_html(label):
            if isinstance(label, dict):
                short = str(label.get('name') or '')
                full = str(label.get('name_full') or short)
            else:
                short = str(label or '')
                full = short
            if full and full != short:
                return f'<span class="o_maint_analytics_eq" title="{escape(full)}">{escape(short)}</span>'
            return escape(short)

        def state_badge(state):
            mapping = {
                'critical': ('Critical', '#fff1f3', '#d92d20', '#ffd5d9'),
                'warning': ('Warning', '#fff7e8', '#b54708', '#fedf89'),
                'stable': ('Stable', '#ecfdf3', '#027a48', '#abefc6'),
            }
            label, bg, color, border = mapping.get(state or 'stable', mapping['stable'])
            return (
                f'<span style="padding:5px 10px;border-radius:999px;background:{bg};color:{color};'
                f'border:1px solid {border};font-size:11px;font-weight:700;">{escape(_(label))}</span>'
            )

        currency_symbol = str(self.currency_id.symbol or '$')
        total_cost = stats['total_cost'] or 0.0

        # Pie reflects top equipment slices; scale segments to their share of full period spend.
        cost_total = total_cost or sum(s['amount'] for s in stats['cost_slices']) or 1.0
        slice_pcts = []
        for s in stats['cost_slices']:
            p = pct(s['amount'], cost_total)
            slice_pcts.append((p, s['color']))

        if stats['cost_slices']:
            parts = []
            pos = 0.0
            for p, color in slice_pcts:
                parts.append(f'{color} {pos:.2f}% {pos + p:.2f}%')
                pos += p
            pie_style = (
                'width:148px;height:148px;border-radius:50%;flex-shrink:0;'
                f'background:conic-gradient({", ".join(parts)});'
                'box-shadow:0 4px 14px rgba(15,23,42,0.1);'
            )
        else:
            pie_style = (
                'width:148px;height:148px;border-radius:50%;flex-shrink:0;'
                'background:#e5e7eb;border:1px solid #d1d5db;'
            )

        mttr_html = []
        for row in stats['mttr_rows']:
            mttr_html.append(
                '<div class="o_maint_analytics_bar_row">'
                '<div class="o_maint_analytics_bar_head">'
                f'<strong>{eq_label_html(row)}</strong>'
                f'<span>{escape(fmt_hours(row["hours"]))} hrs</span>'
                '</div>'
                '<div class="o_maint_analytics_bar_track">'
                f'<div class="o_maint_analytics_bar_fill" style="width:{max(min(row["bar_pct"], 100.0), 0.0):.2f}%;"></div>'
                '</div>'
                '</div>'
            )
        if not mttr_html:
            mttr_html.append(
                f'<div class="o_maint_analytics_empty">{escape(_("No completed requests with request and close dates in this period."))}</div>'
            )

        mtbf_html_parts = []
        for row in stats['mtbf_rows']:
            mtbf_html_parts.append(
                '<div class="o_maint_analytics_mtbf_item">'
                f'<div class="o_maint_analytics_mtbf_days">{escape(str(row["days"]))}d</div>'
                f'<div class="o_maint_analytics_mtbf_name">{eq_label_html(row)}</div>'
                f'</div>'
            )
        if not mtbf_html_parts:
            mtbf_html_parts.append(
                f'<div class="o_maint_analytics_empty">{escape(_("No equipment MTBF (add closed corrective history on assets)."))}</div>'
            )

        time_rows = stats['time_rows'][:8]
        totals = {
            'planned': sum(r.get('planned', 0.0) or 0.0 for r in time_rows),
            'actual': sum(r.get('actual', 0.0) or 0.0 for r in time_rows),
            'delay': sum(max(r.get('delay', 0.0) or 0.0, 0.0) for r in time_rows),
        }
        max_axis = max(
            [totals['planned'], totals['actual']]
            + [max((r.get('planned', 0.0) or 0.0), (r.get('actual', 0.0) or 0.0)) for r in time_rows]
            + [1.0]
        )
        if not time_rows:
            time_table_html = (
                f'<div class="o_maint_analytics_empty">{escape(_("No planned or actual hours in this period."))}</div>'
            )
        else:
            svg_w, svg_h = 960, 340
            ml, mr, mt, mb = 56, 24, 16, 72
            chart_w = svg_w - ml - mr
            chart_h = svg_h - mt - mb
            group_count = max(len(time_rows), 1)
            group_gap = 16.0
            group_w = chart_w / group_count
            bar_w = min(16.0, max((group_w - group_gap) / 3.0, 8.0))

            def y_px(hours):
                return mt + (1.0 - (hours / max_axis)) * chart_h

            y_ticks = [0, 25, 50, 75, 100]
            y_grid = ''.join(
                f'<line x1="{ml}" y1="{mt + (1.0 - t/100.0) * chart_h:.1f}" x2="{svg_w - mr}" y2="{mt + (1.0 - t/100.0) * chart_h:.1f}" '
                f'stroke="#e8edf3" stroke-width="1"/>'
                for t in y_ticks
            )
            y_labels = ''.join(
                f'<text x="{ml - 6}" y="{mt + (1.0 - t/100.0) * chart_h + 4:.1f}" text-anchor="end" font-size="10" fill="#64748b">{fmt_hours((t/100.0) * max_axis)}</text>'
                for t in y_ticks
            )
            bars_svg = []
            x_labels = []
            status_rows = []
            for idx, row in enumerate(time_rows):
                planned = row.get('planned', 0.0) or 0.0
                actual = row.get('actual', 0.0) or 0.0
                delay_hours = max(row.get('delay', 0.0) or 0.0, 0.0)
                name = row.get('name') if isinstance(row, dict) else str(row)
                full_name = row.get('name_full', name) if isinstance(row, dict) else str(row)
                gx = ml + idx * group_w + group_gap / 2.0
                for j, (val, fill, key) in enumerate((
                    (planned, '#94a3b8', 'planned'),
                    (actual, '#2563eb', 'actual'),
                    (delay_hours, '#f97316', 'delay'),
                )):
                    x = gx + j * (bar_w + 3.0)
                    y = y_px(val)
                    h = max((val / max_axis) * chart_h, 2.0)
                    bars_svg.append(
                        f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" rx="4" fill="{fill}" '
                        f'data-key="{key}"><title>{escape(full_name)} · {escape(_(key.capitalize()))}: {escape(fmt_hours(val))}h</title></rect>'
                    )
                x_labels.append(
                    f'<text x="{gx + (1.5 * bar_w) + 3:.1f}" y="{svg_h - 42}" text-anchor="middle" font-size="10" fill="#475569">{escape(name[:14])}</text>'
                )
                if delay_hours <= 0.0:
                    status_class = 'o_maint_exec_status--ok'
                    status_text = _('On Schedule')
                elif delay_hours >= 4.0:
                    status_class = 'o_maint_exec_status--critical'
                    status_text = _('Critical Delay')
                else:
                    status_class = 'o_maint_exec_status--delay'
                    status_text = _('Delayed')
                status_rows.append(
                    '<div class="o_maint_exec_status_row">'
                    f'<span class="o_maint_exec_eq" title="{escape(full_name)}">{escape(name)}</span>'
                    f'<span class="o_maint_exec_status {status_class}">{escape(status_text)}</span>'
                    '</div>'
                )

            svg_graph = (
                f'<svg class="o_maint_exec_svg" viewBox="0 0 {svg_w} {svg_h}" preserveAspectRatio="xMidYMid meet" role="img" '
                f'aria-label="{escape(_("Execution timeline grouped bar chart"))}">'
                f'<rect x="{ml}" y="{mt}" width="{chart_w}" height="{chart_h}" fill="#fcfdff" rx="6"/>'
                f'{y_grid}{y_labels}'
                f'{"".join(bars_svg)}'
                f'{"".join(x_labels)}'
                f'<text x="{ml + chart_w / 2:.1f}" y="{svg_h - 14}" text-anchor="middle" font-size="11" fill="#475569" font-weight="600">{escape(_("Equipment"))}</text>'
                f'<text x="{20}" y="{mt + chart_h / 2:.1f}" transform="rotate(-90 20 {mt + chart_h / 2:.1f})" text-anchor="middle" font-size="11" fill="#475569" font-weight="600">{escape(_("Hours"))}</text>'
                '</svg>'
            )
            time_table_html = (
                '<div class="o_maint_exec_summary">'
                f'<div class="o_maint_exec_sum_card"><span>{escape(_("Total Planned Hours"))}</span><strong>{escape(fmt_hours(totals["planned"]))}h</strong></div>'
                f'<div class="o_maint_exec_sum_card"><span>{escape(_("Total Actual Hours"))}</span><strong>{escape(fmt_hours(totals["actual"]))}h</strong></div>'
                f'<div class="o_maint_exec_sum_card"><span>{escape(_("Total Delay"))}</span><strong>{escape(fmt_hours(totals["delay"]))}h</strong></div>'
                '</div>'
                '<div class="o_maint_exec_legend">'
                f'<span><i class="o_maint_exec_dot o_maint_exec_dot--planned"></i>{escape(_("Planned (baseline)"))}</span>'
                f'<span><i class="o_maint_exec_dot o_maint_exec_dot--actual"></i>{escape(_("Actual execution"))}</span>'
                f'<span><i class="o_maint_exec_dot o_maint_exec_dot--delay"></i>{escape(_("Delay extension"))}</span>'
                '</div>'
                '<div class="o_maint_exec_svg_wrap">'
                f'{svg_graph}'
                '</div>'
                '<div class="o_maint_exec_status_list">'
                f'{"".join(status_rows)}'
                '</div>'
            )




        period_label = _('Last %(n)s days (requests from %(d)s)') % {
            'n': stats.get('period_days', 30),
            'd': stats['from_date'].strftime('%Y-%m-%d'),
        }
        scope_label = _('Fleet / vehicle filter on') if self.fleet_vehicle_scope else _('All equipment categories')
        mode_label = _('Use case: single request') if self.analytics_mode == 'use_case' else _('Live: all matching requests')

        mttr_sub = _('Based on %(n)s completed request(s) with dates') % {'n': stats['mttr_sample_count']}
        mtbf_sub = _('Average MTBF on %(n)s asset(s) in scope') % {'n': stats['mtbf_asset_count']}
        cost_sub = _('Sum of total cost on %(n)s request(s)') % {'n': stats['req_count']}
        fail_sub = _('Requests with no-go decision')
        refresh_sub = _('Last refreshed: %(dt)s') % {'dt': fmt_dt(stats.get('refreshed_at'))}
        meta_summary = _(
            '%(req)s request(s) · %(eq)s equipment · data updates when you save maintenance records'
        ) % {'req': stats['req_count'], 'eq': stats.get('equipment_count', 0)}

        cost_rows_html = ''
        for s in stats['cost_slices']:
            cost_rows_html += (
                '<div class="o_maint_analytics_cost_line">'
                '<div class="o_maint_analytics_cost_line_label">'
                f'<span class="o_maint_analytics_cost_dot" style="background:{s["color"]};"></span>'
                f'{eq_label_html(s)}</div>'
                f'<strong>{escape(currency_symbol)}{escape(fmt_money(s["amount"]))}</strong>'
                '</div>'
            )
        if not cost_rows_html:
            cost_rows_html = (
                f'<div class="o_maint_analytics_empty">{escape(_("No cost lines in this period."))}</div>'
            )

        # Request mix graph
        total_types = sum(stats.get('type_counts', {}).values()) or 1
        type_palette = {
            'corrective': '#ef4444',
            'preventive': '#2563eb',
            'predictive': '#14b8a6',
        }
        type_labels = {
            'corrective': _('Corrective'),
            'preventive': _('Preventive'),
            'predictive': _('Predictive'),
        }
        request_mix_rows = []
        for t in ('corrective', 'preventive', 'predictive'):
            count = stats.get('type_counts', {}).get(t, 0)
            bar = (count / total_types) * 100.0
            request_mix_rows.append(
                '<div class="o_maint_analytics_mix_row">'
                f'<div class="o_maint_analytics_mix_label"><span class="o_maint_analytics_mix_dot" style="background:{type_palette[t]};"></span>{escape(type_labels[t])}</div>'
                f'<div class="o_maint_analytics_mix_track"><div class="o_maint_analytics_mix_fill" style="width:{bar:.2f}%;background:{type_palette[t]};"></div></div>'
                f'<div class="o_maint_analytics_mix_value">{count}</div>'
                '</div>'
            )
        delayed_rows = []
        for row in stats.get('top_delayed_rows', []):
            delayed_rows.append(
                '<div class="o_maint_analytics_insight_row">'
                f'<span class="o_maint_analytics_eq" title="{escape(row.get("name_full", row.get("name", "")))}">{escape(row.get("name", ""))}</span>'
                f'<strong>{escape(fmt_hours(row.get("delay", 0.0)))}h {escape(_("delay"))}</strong>'
                '</div>'
            )
        if not delayed_rows:
            delayed_rows = [f'<div class="o_maint_analytics_empty">{escape(_("No delayed equipment in this period."))}</div>']

        detail_rows_html = []
        for row in time_rows:
            delay = max(row.get('delay', 0.0) or 0.0, 0.0)
            if delay <= 0.0:
                status_class = 'o_maint_analytics_status--ok'
                status_text = _('On Schedule')
            elif delay >= 4.0:
                status_class = 'o_maint_analytics_status--delay'
                status_text = _('Delayed')
            else:
                status_class = 'o_maint_analytics_status--delay'
                status_text = _('Minor Delay')
            detail_rows_html.append(
                '<div class="o_maint_analytics_detail_row">'
                f'<div class="o_maint_analytics_eq" title="{escape(row.get("name_full", row.get("name", "")))}">{escape(row.get("name", ""))}</div>'
                f'<div>{escape(fmt_hours(row.get("planned", 0.0)))}h</div>'
                f'<div>{escape(fmt_hours(row.get("actual", 0.0)))}h</div>'
                f'<div>{escape(fmt_hours(delay))}h</div>'
                f'<div><span class="o_maint_analytics_status {status_class}">{escape(status_text)}</span></div>'
                '</div>'
            )
        if not detail_rows_html:
            detail_rows_html = [f'<div class="o_maint_analytics_empty">{escape(_("No equipment execution rows in this period."))}</div>']

        # Monthly trend graph
        trend = stats.get('trend_monthly', [])
        max_trend = max((m['count'] for m in trend), default=0) or 1
        trend_bars = []
        for m in trend:
            h = max((m['count'] / max_trend) * 100.0, 4 if m['count'] else 0)
            trend_bars.append(
                '<div class="o_maint_analytics_trend_bar_wrap">'
                f'<div class="o_maint_analytics_trend_bar" style="height:{h:.2f}%;" title="{escape(m["label"])}: {m["count"]}"></div>'
                f'<div class="o_maint_analytics_trend_count">{m["count"]}</div>'
                f'<div class="o_maint_analytics_trend_label">{escape(m["label"])}</div>'
                '</div>'
            )

        mtbf_block_inner = ''.join(mtbf_html_parts)
        mttr_card_foot = ''
        if stats.get('mttr_alert'):
            mttr_card_foot = (
                f'<div class="o_maint_analytics_card_foot o_maint_analytics_card_foot--danger">'
                f'{escape(stats["mttr_alert"])}</div>'
            )
        mtbf_card_foot = ''
        if stats.get('stability_note'):
            mtbf_card_foot = (
                f'<div class="o_maint_analytics_card_foot o_maint_analytics_card_foot--success">'
                f'{escape(stats["stability_note"])}</div>'
            )

        html = [
            '<div class="o_maint_analytics_dashboard">',
            '<header class="o_maint_analytics_header">',
            '<div class="o_maint_analytics_header_text">',
            f'<h1>{escape(_("Maintenance Analytics"))}</h1>',
            f'<p>{escape(_("KPIs from maintenance requests and equipment in your database"))}</p>',
            '</div>',
            '<div class="o_maint_analytics_pills">',
            f'<span class="o_maint_analytics_pill"><i class="fa fa-filter"></i><strong>{escape(_("Scope"))}:</strong> {escape(scope_label)}</span>',
            f'<span class="o_maint_analytics_pill"><i class="fa fa-calendar-o"></i><strong>{escape(_("Period"))}:</strong> {escape(period_label)}</span>',
            f'<span class="o_maint_analytics_pill"><i class="fa fa-database"></i><strong>{escape(_("Mode"))}:</strong> {escape(mode_label)}</span>',
            '</div>',
            '</header>',
            f'<div class="o_maint_analytics_meta"><span class="o_maint_analytics_meta_item"><i class="fa fa-bar-chart"></i>{escape(meta_summary)}</span><span class="o_maint_analytics_meta_live"><span class="o_maint_analytics_live_dot"></span>{escape(_("Live"))}</span></div>',
            '<div class="o_maint_analytics_kpi_grid">',
            f'<div class="o_maint_analytics_kpi o_maint_analytics_kpi--mttr"><div class="o_maint_analytics_kpi_label">{escape(_("MTTR"))}</div><div class="o_maint_analytics_kpi_value o_maint_analytics_kpi_value--mttr">{escape(fmt_hours(stats["mttr_hours"]))} <span class="o_maint_analytics_kpi_unit">hrs</span></div><div class="o_maint_analytics_kpi_desc">{escape(_("Mean Time To Repair"))}</div><div class="o_maint_analytics_kpi_sub">{escape(mttr_sub)}</div></div>',
            f'<div class="o_maint_analytics_kpi o_maint_analytics_kpi--mtbf"><div class="o_maint_analytics_kpi_label">{escape(_("MTBF"))}</div><div class="o_maint_analytics_kpi_value o_maint_analytics_kpi_value--mtbf">{escape(fmt_number(stats["mtbf_days"]))} <span class="o_maint_analytics_kpi_unit">days</span></div><div class="o_maint_analytics_kpi_desc">{escape(_("Mean Time Between Failures"))}</div><div class="o_maint_analytics_kpi_sub">{escape(mtbf_sub)}</div></div>',
            f'<div class="o_maint_analytics_kpi o_maint_analytics_kpi--cost"><div class="o_maint_analytics_kpi_label">{escape(_("Total Cost"))}</div><div class="o_maint_analytics_kpi_value o_maint_analytics_kpi_value--cost">{escape(currency_symbol)}{escape(fmt_money(total_cost))}</div><div class="o_maint_analytics_kpi_desc">{escape(_("Maintenance Spend"))}</div><div class="o_maint_analytics_kpi_sub">{escape(cost_sub)}</div></div>',
            f'<div class="o_maint_analytics_kpi o_maint_analytics_kpi--fail"><div class="o_maint_analytics_kpi_label">{escape(_("Total Failures"))}</div><div class="o_maint_analytics_kpi_value o_maint_analytics_kpi_value--fail">{escape(fmt_number(stats["total_failures"]))}</div><div class="o_maint_analytics_kpi_desc">{escape(_("No-go decisions"))}</div><div class="o_maint_analytics_kpi_sub">{escape(fail_sub)}</div></div>',
            '</div>',
            '<div class="o_maint_analytics_strip_grid">',
            f'<div class="o_maint_analytics_strip"><span>{escape(_("Open Requests"))}</span><strong>{escape(fmt_number(stats.get("open_count", 0)))}</strong></div>',
            f'<div class="o_maint_analytics_strip"><span>{escape(_("Closed Requests"))}</span><strong>{escape(fmt_number(stats.get("closed_count", 0)))}</strong></div>',
            f'<div class="o_maint_analytics_strip"><span>{escape(_("PM Compliance"))}</span><strong>{escape(fmt_number(stats.get("pm_compliance_pct", 0.0), 1))}%</strong></div>',
            f'<div class="o_maint_analytics_strip"><span>{escape(_("Total Downtime"))}</span><strong>{escape(fmt_hours(stats.get("total_delay_hours", 0.0)))}h</strong></div>',
            '</div>',
            '<div class="o_maint_analytics_row o_maint_analytics_row--2">',
            f'<div class="o_maint_analytics_card"><h2 class="o_maint_analytics_card_title">{escape(_("Request mix by maintenance type"))}</h2><div class="o_maint_analytics_mix_graph">{"".join(request_mix_rows)}</div></div>',
            f'<div class="o_maint_analytics_card"><h2 class="o_maint_analytics_card_title">{escape(_("Monthly request trend (last 6 months)"))}</h2><div class="o_maint_analytics_trend_graph">{"".join(trend_bars)}</div></div>',
            '</div>',
            '<div class="o_maint_analytics_body">',
            '<div class="o_maint_analytics_row o_maint_analytics_row--3">',
            f'<div class="o_maint_analytics_card"><h2 class="o_maint_analytics_card_title">{escape(_("MTTR by equipment"))}</h2><div>{"".join(mttr_html)}</div>{mttr_card_foot}</div>',
            f'<div class="o_maint_analytics_card"><h2 class="o_maint_analytics_card_title">{escape(_("MTBF by equipment"))}</h2><div class="o_maint_analytics_mtbf_grid">{mtbf_block_inner}</div>{mtbf_card_foot}</div>',
            '<div class="o_maint_analytics_card">',
            f'<h2 class="o_maint_analytics_card_title">{escape(_("Maintenance cost by equipment"))}</h2>',
            '<div class="o_maint_analytics_cost_panel">',
            '<div class="o_maint_analytics_pie_block">',
            f'<div class="o_maint_analytics_pie" style="{pie_style}"></div>',
            f'<div class="o_maint_analytics_pie_total"><span>{escape(_("Total"))}</span> <strong>{escape(currency_symbol)}{escape(fmt_money(total_cost))}</strong></div>',
            '</div>',
            f'<div class="o_maint_analytics_cost_list">{cost_rows_html}</div>',
            '</div>',
            '</div>',
            '</div>',
            f'<div class="o_maint_analytics_card o_maint_analytics_card--wide"><h2 class="o_maint_analytics_card_title">{escape(_("Execution Timeline Graph (Planned vs Actual vs Delay)"))}</h2><div><div class="o_maint_analytics_legend">'
            f'<span><span class="o_maint_analytics_legend_dot" style="background:#e5e7eb;"></span>{escape(_("Planned"))}</span>'
            f'<span><span class="o_maint_analytics_legend_dot" style="background:#2563eb;"></span>{escape(_("Actual"))}</span>'
            f'<span><span class="o_maint_analytics_legend_dot" style="background:#14b8a6;"></span>{escape(_("Delay"))}</span>'
            f'</div>{time_table_html}</div></div>',
            '<div class="o_maint_analytics_row o_maint_analytics_row--2">',
            f'<div class="o_maint_analytics_card"><h2 class="o_maint_analytics_card_title">{escape(_("Equipment execution detail"))}</h2><div class="o_maint_analytics_detail_table"><div class="o_maint_analytics_detail_head"><span>{escape(_("Equipment"))}</span><span>{escape(_("Planned"))}</span><span>{escape(_("Actual"))}</span><span>{escape(_("Delay"))}</span><span>{escape(_("Status"))}</span></div>{"".join(detail_rows_html)}</div></div>',
            f'<div class="o_maint_analytics_card"><h2 class="o_maint_analytics_card_title">{escape(_("Actionable insights"))}</h2><div class="o_maint_analytics_insights"><div class="o_maint_analytics_insight_block"><h3>{escape(_("Top delayed equipment"))}</h3>{"".join(delayed_rows)}</div><div class="o_maint_analytics_insight_block"><h3>{escape(_("Data freshness"))}</h3><p>{escape(refresh_sub)}</p><p>{escape(_("Tip: use Export in list view for CSV/XLS reports."))}</p></div></div></div>',
            '</div>',
            '</div>',
            '</div>',
        ]
        html = [part for part in html if part]
        return Markup(''.join(html))

    @api.depends('company_id')
    def _compute_maintenance_cost_currency_id(self):
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        for dash in self:
            dash.currency_id = usd or dash.company_id.currency_id

    @api.depends(
        'analytics_mode',
        'use_case_request_id',
        'company_id',
        'fleet_vehicle_scope',
        'analysis_period_days',
    )
    def _compute_analytics_dashboard(self):
        for dash in self:
            stats = dash._analytics_stats()
            dash.mttr_hours = stats['mttr_hours']
            dash.mtbf_days = stats['mtbf_days']
            dash.total_cost_value = stats['total_cost']
            dash.total_failures = stats['total_failures']

            for i, row in enumerate(stats['mttr_rows'][:3]):
                setattr(dash, f'eq{i+1}_name', row['name'])
                setattr(dash, f'eq{i+1}_mttr', row['hours'])
                setattr(dash, f'eq{i+1}_mttr_bar', row['bar_pct'])
            for i in range(len(stats['mttr_rows']), 3):
                setattr(dash, f'eq{i+1}_name', '')
                setattr(dash, f'eq{i+1}_mttr', 0.0)
                setattr(dash, f'eq{i+1}_mttr_bar', 0.0)

            slices = stats['cost_slices']
            dash.cost_gearbox = slices[0]['amount'] if len(slices) > 0 else 0.0
            dash.cost_crane = slices[1]['amount'] if len(slices) > 1 else 0.0
            dash.cost_vehicle = slices[2]['amount'] if len(slices) > 2 else 0.0

            time_rows = stats['time_rows']
            g1 = time_rows[0] if len(time_rows) > 0 else {'planned': 0.0, 'actual': 0.0, 'delay': 0.0}
            g2 = time_rows[1] if len(time_rows) > 1 else {'planned': 0.0, 'actual': 0.0, 'delay': 0.0}
            dash.planned_gearbox = g1['planned']
            dash.actual_gearbox = g1['actual']
            dash.delayed_gearbox = g1['delay']
            dash.planned_vehicle = g2['planned']
            dash.actual_vehicle = g2['actual']
            dash.delayed_vehicle = g2['delay']

            max_time = max(
                dash.planned_gearbox or 0.0,
                dash.actual_gearbox or 0.0,
                dash.planned_vehicle or 0.0,
                dash.actual_vehicle or 0.0,
                1.0,
            )
            dash.planned_gearbox_pct = ((dash.planned_gearbox or 0.0) / max_time) * 100.0
            dash.actual_gearbox_pct = ((dash.actual_gearbox or 0.0) / max_time) * 100.0
            dash.planned_vehicle_pct = ((dash.planned_vehicle or 0.0) / max_time) * 100.0
            dash.actual_vehicle_pct = ((dash.actual_vehicle or 0.0) / max_time) * 100.0

            health = stats['health_rows'][:3]
            while len(health) < 3:
                health.append(None)
            for idx, row in enumerate(health[:3]):
                prefix = f'health_{idx + 1}_'
                if row:
                    dash[f'{prefix}name'] = row['name']
                    dash[f'{prefix}note'] = row['note']
                    dash[f'{prefix}state'] = row['state']
                else:
                    dash[f'{prefix}name'] = ''
                    dash[f'{prefix}note'] = ''
                    dash[f'{prefix}state'] = 'stable'

            dash.dashboard_html = dash._render_dashboard_html(stats)
