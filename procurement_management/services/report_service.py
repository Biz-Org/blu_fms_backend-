# -*- coding: utf-8 -*-
import base64
import csv
import io
import zipfile
from xml.sax.saxutils import escape

from odoo import fields
from odoo.exceptions import AccessError, UserError

from .common import audit, has_group
from .notification_service import NotificationService


class ReportService:
    def __init__(self, env):
        self.env = env

    def _manager(self):
        if not has_group(self.env, 'group_procurement_manager'):
            raise AccessError('Only a procurement manager can run procurement reports.')

    def preview(self, definition):
        definition.ensure_one()
        self._manager()
        rows = self._rows(definition)
        return {'columns': rows[0], 'rows': rows[1:]}

    def export(self, definition, file_format):
        definition.ensure_one()
        self._manager()
        if file_format not in ('csv', 'xlsx', 'pdf'):
            raise UserError('Unsupported report format.')
        run = self.env['procurement.management.report.run'].create({
            'name': '%s %s' % (definition.name, file_format.upper()),
            'definition_id': definition.id,
            'state': 'generating',
            'file_format': file_format,
            'started_on': fields.Datetime.now(),
        })
        try:
            rows = self._rows(definition)
            if file_format == 'csv':
                payload, mimetype, ext = self._csv(rows), 'text/csv', 'csv'
            elif file_format == 'xlsx':
                payload, mimetype, ext = self._xlsx(rows), (
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                ), 'xlsx'
            else:
                payload = self._pdf(run)
                if not payload:
                    return self._fail(run, definition, 'PDF export is unavailable.')
                mimetype, ext = 'application/pdf', 'pdf'
            attachment = self.env['ir.attachment'].create({
                'name': '%s.%s' % (definition.name, ext),
                'datas': base64.b64encode(payload),
                'res_model': run._name,
                'res_id': run.id,
                'mimetype': mimetype,
                'public': False,
            })
            run.write({
                'state': 'exported',
                'attachment_id': attachment.id,
                'finished_on': fields.Datetime.now(),
                'error_detail': False,
            })
            audit(self.env, definition.company_id, 'created', model=run._name,
                  reference=run.name, after='exported', detail=file_format)
            return {'ok': True, 'run_id': run.id, 'attachment_id': attachment.id}
        except Exception as exc:
            message = str(exc) or 'Report export failed.'
            return self._fail(run, definition, message)

    def _fail(self, run, definition, message):
        run.write({
            'state': 'failed',
            'error_detail': message,
            'finished_on': fields.Datetime.now(),
        })
        audit(self.env, definition.company_id, 'modified', model=run._name,
              reference=run.name, after='failed', detail=message)
        return {'ok': False, 'run_id': run.id, 'error': message}

    _LABELS = {
        'reference': 'Reference',
        'partner': 'Partner',
        'amount': 'Amount',
        'status': 'Status',
        'date': 'Date',
        'department': 'Department',
    }
    _DETAIL_KEYS = ('reference', 'partner', 'amount', 'status', 'date')
    _GROUP_KEYS = ('department', 'partner', 'status', 'date')

    def _rows(self, definition):
        records = list(self._source_records(definition))
        group_key = self._group_key(definition)
        if group_key:
            records = self._aggregate(records, group_key)
        columns = self._columns(definition, grouped=bool(group_key))
        records = self._sort_records(records, definition.sort_by)
        rows = [[self._LABELS[key] for key in columns]]
        for record in records:
            rows.append([record.get(key) for key in columns])
        return rows

    def _columns(self, definition, grouped):
        tokens = [
            part.strip().lower()
            for part in (definition.metrics or '').replace(';', ',').split(',')
            if part.strip()
        ]
        if not tokens:
            keys = list(self._DETAIL_KEYS)
        else:
            keys = []
            for token in tokens:
                if token in self._LABELS and token not in keys and token != 'department':
                    keys.append(token)
            if not keys:
                keys = list(self._DETAIL_KEYS)
            elif 'reference' not in keys:
                keys.insert(0, 'reference')
        if grouped:
            group_key = self._group_key(definition)
            keys = [key for key in keys if key != 'reference' and key != group_key]
            if 'amount' not in keys and (not tokens or 'amount' in tokens):
                keys.append('amount')
            return [group_key] + keys
        return keys

    def _group_key(self, definition):
        token = (definition.group_by or '').strip().lower()
        if token in self._GROUP_KEYS:
            return token
        return None

    def _aggregate(self, records, group_key):
        buckets = {}
        order = []
        for record in records:
            value = record.get(group_key) or ''
            if value not in buckets:
                buckets[value] = []
                order.append(value)
            buckets[value].append(record)
        grouped = []
        for value in order:
            members = buckets[value]
            row = dict(members[0])
            row[group_key] = value
            row['amount'] = sum((member.get('amount') or 0.0) for member in members)
            row['reference'] = ''
            for key in ('partner', 'status', 'date', 'department'):
                if key == group_key:
                    continue
                values = {(member.get(key) or '') for member in members}
                row[key] = next(iter(values)) if len(values) == 1 else ''
            grouped.append(row)
        return grouped

    def _sort_records(self, records, sort_by):
        token = (sort_by or '').strip().lower()
        if not token or not records:
            return records
        descending = token.endswith(' desc') or token.startswith('-')
        key_name = token[:-5].strip() if token.endswith(' desc') else token
        key_name = key_name[:-4].strip() if key_name.endswith(' asc') else key_name
        key_name = key_name[1:].strip() if key_name.startswith('-') else key_name
        if key_name not in self._LABELS:
            return records

        def sort_key(record):
            value = record.get(key_name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return (0, float(value), str(record.get('department') or ''), str(record.get('reference') or ''))
            return (1, str(value or '').casefold(), str(record.get('reference') or ''))

        return sorted(records, key=sort_key, reverse=descending)

    def _source_records(self, definition):
        company = definition.company_id
        if definition.report_type in ('spend', 'custom'):
            domain = [
                ('company_id', '=', company.id),
                ('state', 'in', ['issued', 'acknowledged', 'closed']),
            ]
            if definition.date_from:
                domain.append(('create_date', '>=', fields.Datetime.to_datetime(definition.date_from)))
            if definition.date_to:
                domain.append(('create_date', '<=', fields.Datetime.to_datetime(definition.date_to)))
            if definition.partner_id:
                domain.append(('partner_id', '=', definition.partner_id.id))
            if definition.department:
                domain.append(('department', '=', definition.department))
            if definition.category:
                domain.append(('category', '=', definition.category))
            orders = self.env['procurement.management.purchase.order'].search(domain)
            return [{
                'reference': order.name,
                'partner': order.partner_id.name,
                'department': order.department or '',
                'amount': order.amount_total,
                'status': order.display_status,
                'date': str(order.delivery_date or ''),
            } for order in orders]
        if definition.report_type == 'requisitions':
            domain = [('company_id', '=', company.id)]
            if definition.status:
                domain.append(('state', '=', definition.status))
            if definition.department:
                domain.append(('department', '=', definition.department))
            rows = self.env['procurement.management.requisition'].search(domain)
            return [{
                'reference': row.name,
                'partner': row.requester_id.name,
                'department': row.department or '',
                'amount': row.amount_total,
                'status': row.state,
                'date': str(row.required_date or ''),
            } for row in rows]
        if definition.report_type == 'rfq':
            domain = [('company_id', '=', company.id)]
            if definition.status:
                domain.append(('state', '=', definition.status))
            rows = self.env['procurement.management.rfq'].search(domain)
            return [{
                'reference': row.name,
                'partner': ', '.join(row.supplier_ids.mapped('partner_id.name')),
                'department': row.department or '',
                'amount': row.estimated_value,
                'status': row.state,
                'date': str(row.deadline or ''),
            } for row in rows]
        profiles = self.env['procurement.management.supplier.profile'].search([
            ('company_id', '=', company.id),
        ])
        if definition.partner_id:
            profiles = profiles.filtered(lambda profile: profile.partner_id == definition.partner_id)
        if definition.category:
            profiles = profiles.filtered(lambda profile: profile.category == definition.category)
        return [{
            'reference': profile.vendor_code or profile.partner_id.name,
            'partner': profile.partner_id.name,
            'department': '',
            'amount': profile.score,
            'status': profile.state,
            'date': '',
        } for profile in profiles]

    def _csv(self, rows):
        buffer = io.StringIO()
        csv.writer(buffer).writerows(rows)
        return buffer.getvalue().encode('utf-8')

    def _xlsx(self, rows):
        sheet = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for index, row in enumerate(rows, start=1):
            cells = []
            for column, value in enumerate(row, start=1):
                letter = chr(64 + column)
                cells.append('<c r="%s%s" t="inlineStr"><is><t>%s</t></is></c>' % (
                    letter, index, escape(str(value if value is not None else '')),
                ))
            sheet.append('<row r="%s">%s</row>' % (index, ''.join(cells)))
        sheet.append('</sheetData></worksheet>')
        content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
        rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
        workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Report" sheetId="1" r:id="rId1"/></sheets></workbook>"""
        workbook_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('[Content_Types].xml', content_types)
            archive.writestr('_rels/.rels', rels)
            archive.writestr('xl/workbook.xml', workbook)
            archive.writestr('xl/_rels/workbook.xml.rels', workbook_rels)
            archive.writestr('xl/worksheets/sheet1.xml', ''.join(sheet))
        return buffer.getvalue()

    def _pdf(self, run):
        report = self.env.ref('procurement_management.action_report_pm_run', raise_if_not_found=False)
        if not report:
            raise UserError('PDF export is unavailable because the report action is missing.')
        try:
            pdf, _report_type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'procurement_management.action_report_pm_run', [run.id],
            )
        except Exception as exc:
            raise UserError('PDF export is unavailable. %s' % exc)
        if not pdf or not bytes(pdf).startswith(b'%PDF'):
            raise UserError(
                'PDF export is unavailable. The server did not return a PDF document.'
            )
        return pdf

    def send_due(self):
        current = fields.Date.context_today(self.env.user)
        definitions = self.env['procurement.management.report.definition'].sudo().search([
            ('schedule', 'in', ['weekly', 'monthly']),
        ])
        for definition in definitions:
            if definition.last_run_on == current:
                continue
            if definition.schedule == 'weekly' and current.weekday() != (definition.weekday or 0):
                continue
            if definition.schedule == 'monthly' and current.day != (definition.month_day or 0):
                continue
            result = self.export(definition.with_user(self.env.user), 'csv')
            run = self.env['procurement.management.report.run'].browse(result.get('run_id'))
            if not result.get('ok'):
                continue
            emails = definition.recipient_emails or ''
            if not emails:
                run.write({'state': 'failed', 'error_detail': 'No report recipients are configured.'})
                audit(self.env, definition.company_id, 'modified', model=run._name,
                      reference=run.name, after='failed', detail='No report recipients are configured.')
                continue
            sent = NotificationService(self.env).report_ready(run, emails)
            if sent is not True:
                run.write({
                    'state': 'failed',
                    'error_detail': sent or 'The scheduled report email could not be queued.',
                })
                continue
            definition.sudo().write({'last_run_on': current})
        return True
