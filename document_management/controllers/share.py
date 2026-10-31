# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


class DocumentManagementShareController(http.Controller):

    @http.route(
        '/document_management/share/<string:token>',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def share(self, token, **kwargs):
        if not token:
            return request.not_found()
        link = request.env['document.management.share.link']._dm_find_by_token(token)
        if not link:
            return request.not_found()
        payload = link._dm_prepare_download()
        filename = (payload.get('filename') or 'document').replace('"', '')
        content = payload.get('content') or b''
        headers = [
            ('Content-Type', payload.get('mimetype') or 'application/octet-stream'),
            ('Content-Length', str(len(content))),
            ('Content-Disposition', 'attachment; filename="%s"' % filename),
        ]
        return request.make_response(content, headers=headers)
