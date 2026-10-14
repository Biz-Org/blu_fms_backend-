# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.tools import html2plaintext
from odoo.tools.translate import _

from .constants import ALLOWED_ATTACHMENT_MIMETYPES, MAX_ATTACHMENT_SIZE


class CommunityBoundMixin(models.AbstractModel):
    _name = "community.communication.bound.mixin"
    _description = "Community-bound record"

    def _cc_default_community(self):
        resident_community = self.env.user.cc_resident_ids[:1].community_id
        if resident_community:
            return resident_community
        Community = self.env["community.communication.community"].sudo()
        community = Community.search([("company_id", "=", self.env.company.id)], limit=1)
        if not community:
            community = Community.search([], limit=1)
        if not community:
            community = Community.create({
                "name": self.env.company.name or "Community",
                "code": "MAIN",
                "company_id": self.env.company.id,
            })
        return community

    community_id = fields.Many2one(
        "community.communication.community",
        required=True,
        index=True,
        ondelete="restrict",
        default=lambda self: self._cc_default_community(),
    )
    company_id = fields.Many2one(
        "res.company",
        related="community_id.company_id",
        store=True,
        index=True,
        readonly=True,
    )

    def _cc_current_resident(self):
        resident = self.env.user.cc_resident_ids[:1]
        if not resident:
            raise ValidationError(_("No resident profile is linked to the current user."))
        return resident

    def _cc_require_officer(self):
        if self.env.su:
            return True
        if not self.env.user._cc_is_community_officer():
            raise AccessError(_("Only community staff can perform this action."))
        return True

    def _cc_mail_partners(self):
        self.ensure_one()
        if hasattr(self, "_cc_audience_resident_ids"):
            residents = self._cc_audience_resident_ids()
        elif self.community_id:
            residents = self.community_id.resident_ids
        else:
            residents = self.env["community.communication.resident"]
        return residents.mapped("partner_id").filtered("email")

    def _cc_send_mail_template(self, xmlid, partners=None):
        template = self.env.ref(xmlid, raise_if_not_found=False)
        if not template:
            return
        for record in self:
            recipients = partners if partners is not None else record._cc_mail_partners()
            recipients = recipients.filtered("email")
            if not recipients:
                continue
            template.sudo().send_mail(
                record.id,
                force_send=False,
                email_values={"recipient_ids": [(4, pid) for pid in recipients.ids]},
            )

    def _cc_has_html_text(self, value):
        return bool((html2plaintext(value or "") or "").strip())

    @api.model_create_multi
    def create(self, vals_list):
        fallback = self._cc_default_community()
        for vals in vals_list:
            if not vals.get("community_id") and fallback:
                vals["community_id"] = fallback.id
        return super().create(vals_list)


class CommunityAudienceMixin(models.AbstractModel):
    _name = "community.communication.audience.mixin"
    _inherit = "community.communication.bound.mixin"
    _description = "Audience targeting"

    audience_type = fields.Selection(
        [
            ("community", "Entire Community"),
            ("buildings", "Specific Buildings / Towers"),
            ("groups", "Specific Resident Groups"),
            ("residents", "Specific Residents"),
            ("users", "Specific Users"),
        ],
        default="community",
        required=True,
    )

    def _cc_audience_buildings(self):
        return self.building_ids

    def _cc_audience_groups(self):
        return self.audience_group_ids

    def _cc_audience_residents(self):
        return getattr(self, "audience_resident_ids", self.env["community.communication.resident"])

    def _cc_audience_users(self):
        return getattr(self, "audience_user_ids", self.env["res.users"])

    @api.constrains("audience_type", "community_id")
    def _check_audience(self):
        for record in self:
            buildings = record._cc_audience_buildings()
            groups = record._cc_audience_groups()
            residents = record._cc_audience_residents()
            users = record._cc_audience_users()
            if buildings.filtered(lambda b: b.community_id != record.community_id):
                raise ValidationError(_("Targeted buildings must belong to the same community."))
            if groups.filtered(lambda g: g.community_id != record.community_id):
                raise ValidationError(_("Targeted groups must belong to the same community."))
            if residents.filtered(lambda r: r.community_id != record.community_id):
                raise ValidationError(_("Targeted residents must belong to the same community."))
            if record.audience_type == "buildings" and not buildings:
                raise ValidationError(_("Select at least one building for this audience."))
            if record.audience_type == "groups" and not groups:
                raise ValidationError(_("Select at least one group for this audience."))
            if record.audience_type == "residents" and not residents:
                raise ValidationError(_("Select at least one resident for this audience."))
            if record.audience_type == "users" and not users:
                raise ValidationError(_("Select at least one user for this audience."))

    def _cc_audience_resident_ids(self):
        """Residents estimated to receive this record. Used for KPIs."""
        self.ensure_one()
        residents = self.community_id.resident_ids
        if self.audience_type == "buildings":
            return residents.filtered(lambda r: r.building_id in self._cc_audience_buildings())
        if self.audience_type == "groups":
            members = self._cc_audience_groups().member_ids.filtered(lambda m: m.state == "member")
            return members.resident_id
        if self.audience_type == "residents":
            return self._cc_audience_residents()
        if self.audience_type == "users":
            user_ids = self._cc_audience_users().ids
            return residents.filtered(lambda r: r.user_id.id in user_ids)
        return residents

    def _cc_mail_partners(self):
        self.ensure_one()
        if getattr(self, "audience_type", None) == "users" and hasattr(self, "audience_user_ids"):
            return self.audience_user_ids.mapped("partner_id").filtered("email")
        return super()._cc_mail_partners()


class CommunityAttachmentMixin(models.AbstractModel):
    _name = "community.communication.attachment.mixin"
    _description = "Attachment validation"

    def _cc_validate_attachments(self):
        for record in self:
            for attachment in record.attachment_ids:
                if attachment.file_size and attachment.file_size > MAX_ATTACHMENT_SIZE:
                    raise ValidationError(_("Attachments must be 10MB or smaller."))
                mimetype = attachment.mimetype or ""
                if mimetype and mimetype not in ALLOWED_ATTACHMENT_MIMETYPES:
                    raise ValidationError(
                        _("Allowed attachments are PDF, PNG, JPG, SVG, and DOCX.")
                    )

    @api.constrains("attachment_ids")
    def _check_attachments(self):
        self._cc_validate_attachments()

    def action_set_attachments(self, attachment_ids):
        """Link uploaded ir.attachment records and pin them to this record."""
        self.ensure_one()
        ids = [int(item) for item in (attachment_ids or [])]
        self.write({"attachment_ids": [(6, 0, ids)]})
        if ids:
            self.env["ir.attachment"].browse(ids).sudo().write({
                "res_model": self._name,
                "res_id": self.id,
            })
        return True

    def action_upload_attachments(self, files):
        """Create ir.attachment records from uploaded payloads and link them."""
        self.ensure_one()
        created = self.env["ir.attachment"]
        for item in files or []:
            name = (item.get("name") or "attachment").strip()
            datas = item.get("datas")
            if not datas:
                continue
            created |= self.env["ir.attachment"].sudo().create({
                "name": name,
                "datas": datas,
                "mimetype": item.get("mimetype") or False,
                "res_model": self._name,
                "res_id": self.id,
            })
        if created:
            self.write({"attachment_ids": [(4, att.id) for att in created]})
        return created.ids
