# -*- coding: utf-8 -*-
from odoo import models
from odoo.exceptions import UserError


class DocumentManagementAiProvider(models.AbstractModel):
    _name = 'document.management.ai.provider'
    _description = 'Document Management AI Provider'
    _inherit = ['document.management.mixin']

    def is_configured(self):
        return False

    def search(self, query, document_ids=None, filters=None):
        raise UserError('AI Search is not configured')
