# -*- coding: utf-8 -*-
import csv
import io
import json
import zipfile
from datetime import date, datetime, timedelta
from xml.sax.saxutils import escape

from odoo import fields
from odoo.exceptions import UserError

from .audit_service import AuditService
from .common import config_for, page_window, reading_domain, require_manager, require_staff
from .notification_service import NotificationService


class ReportService(object):
    def __init__(self, env):
        self.env = env
        self.audit = AuditService(env)
        self.notification = NotificationService(env)

    def save_definition(self, values):
        require_manager(self.env, 'Only a Facility Manager can save a report definition.')
        values = dict(values or {})
        model = self.env['utility.management.report.definition'].with_context(utility_report_service=True)
        if values.get('id'):
            definition = model.browse(values['id'])
            if not definition.exists():
                raise UserError('Report definition was not found.')
            definition.write({key: values[key] for key in values if key != 'id'})
            return self.definition_dto(definition)
        if 'report_type' not in values:
            raise UserError('Report type is required.')
        definition = model.create(values)
        return self.definition_dto(definition)

    def rows_for(self, definition):
        filters = {
            'company_id': definition.company_id.id,
            'property_ref': definition.property_ref,
            'site_ref': definition.site_ref,
            'floor_ref': definition.floor_ref,
            'area_ref': definition.area_ref,
            'department_ref': definition.department_ref,
            'utility_type': definition.utility_type,
            'meter_id': definition.meter_id.id,
            'date_from': definition.date_from,
            'date_to': definition.date_to,
            'grouping': definition.grouping,
            'comparison': definition.comparison,
        }
        report_type = definition.report_type
        if report_type == 'electricity_consumption':
            return self._reading_rows(filters, 'electricity')
        if report_type == 'water_consumption':
            return self._reading_rows(filters, 'water')
        if report_type == 'gas_consumption':
            return self._reading_rows(filters, 'gas')
        if report_type == 'combined_usage':
            from .consumption_service import ConsumptionService
            return ConsumptionService(self.env).by_property(filters)
        if report_type == 'grid_vs_generator':
            return self._grid_rows(filters)
        if report_type == 'meter_reading':
            return self._reading_rows(filters, filters.get('utility_type'), verified_only=False)
        if report_type == 'leak_detection':
            from .leak_service import LeakService
            return LeakService(self.env).list(filters)
        if report_type == 'consumption_alert':
            from .alert_service import AlertService
            return AlertService(self.env).list(filters)
        if report_type == 'utility_trend':
            from .consumption_service import ConsumptionService
            return ConsumptionService(self.env).comparison(filters)
        if report_type == 'utility_performance':
            return [self._performance(filters)]
        raise UserError('Report type is not supported.')

    def run(self, definition_id, export_format, values=None):
        require_staff(self.env)
        if definition_id:
            definition = self.env['utility.management.report.definition'].browse(definition_id)
            if not definition.exists():
                raise UserError('Report definition was not found.')
            definition.check_access('read')
        else:
            require_manager(self.env, 'Only a Facility Manager can create a report definition.')
            definition = self.env['utility.management.report.definition'].with_context(
                utility_report_service=True,
            ).create(values or {})
        if export_format not in ('pdf', 'xlsx', 'csv'):
            raise UserError('Export format must be PDF, Excel, or CSV.')
        run = self.env['utility.management.report.run'].with_context(utility_report_service=True).create({
            'definition_id': definition.id,
            'company_id': definition.company_id.id,
            'user_id': self.env.user.id,
            'execution_state': 'pending',
            'export_format': export_format,
            'started_at': fields.Datetime.now(),
        })
        try:
            rows = self.rows_for(definition)
            snapshot = self._snapshot(rows)
            payload, mimetype, extension = self._export(run, rows, export_format)
            if export_format == 'pdf' and (not payload or not bytes(payload).startswith(b'%PDF')):
                raise UserError('PDF export is unavailable. The server did not return a PDF document.')
            attachment = self.env['ir.attachment'].sudo().create({
                'name': '%s.%s' % (run.name, extension),
                'datas': self._b64(payload),
                'mimetype': mimetype,
                'res_model': 'utility.management.report.run',
                'res_id': run.id,
                'public': False,
                'company_id': run.company_id.id,
            })
            run.with_context(utility_report_service=True).write({
                'execution_state': 'completed',
                'attachment_id': attachment.id,
                'result_rows': snapshot,
                'finished_at': fields.Datetime.now(),
            })
            self.audit.log('report_execution', run, 'success', 'Report %s completed.' % run.name, after={
                'execution_state': 'completed',
                'export_format': export_format,
            })
        except Exception as exc:
            run.with_context(utility_report_service=True).write({
                'execution_state': 'failed',
                'error_message': str(exc),
                'finished_at': fields.Datetime.now(),
            })
            self.audit.log('report_execution', run, 'success', 'Report %s failed.' % run.name, after={
                'execution_state': 'failed',
                'error_message': str(exc),
            })
        return self.run_dto(run)

    def send_due(self):
        today = fields.Date.context_today(self.env.user)
        definitions = self.env['utility.management.report.definition'].sudo().search([
            ('schedule', 'in', ('daily', 'weekly', 'monthly')),
            ('active', '=', True),
        ])
        for definition in definitions:
            self._lock_definition(definition)
            if not self._is_due(definition, today):
                continue
            run_payload = self.run(definition.id, 'csv')
            run = self.env['utility.management.report.run'].sudo().browse(run_payload['id'])
            emails = ','.join(user.email for user in definition.recipient_user_ids if user.email)
            if emails and config_for(self.env, definition.company_id).mail_notifications:
                self.notification.send_template(run, 'utility_management.mail_template_utility_report', emails)

    def list_definitions(self):
        require_staff(self.env)
        return [
            self.definition_dto(definition)
            for definition in self.env['utility.management.report.definition'].search([])
        ]

    def list_runs(self, filters=None):
        require_staff(self.env)
        filters = filters or {}
        domain = []
        if filters.get('report_type'):
            domain.append(('definition_id.report_type', '=', filters['report_type']))
        if filters.get('execution_state'):
            domain.append(('execution_state', '=', filters['execution_state']))
        if filters.get('definition_id'):
            domain.append(('definition_id', '=', filters['definition_id']))
        model = self.env['utility.management.report.run']
        order = 'id desc'
        window = page_window(filters)
        if not window:
            return [self.run_dto(run) for run in model.search(domain, order=order)]
        limit, offset = window
        return {
            'rows': [self.run_dto(run) for run in model.search(domain, limit=limit, offset=offset, order=order)],
            'total_count': model.search_count(domain),
            'limit': limit,
            'offset': offset,
        }

    def overview(self):
        require_staff(self.env)
        runs = self.env['utility.management.report.run']
        recent = runs.search([], limit=10, order='id desc')
        return {
            'definitions': len(self.list_definitions()),
            'runs': runs.search_count([]),
            'failed': runs.search_count([('execution_state', '=', 'failed')]),
            'recent': [self.run_dto(run) for run in recent],
        }

    def definition_dto(self, definition):
        return {
            'id': definition.id,
            'name': definition.name,
            'report_type': definition.report_type,
            'grouping': definition.grouping,
            'comparison': definition.comparison,
            'schedule': definition.schedule,
            'date_from': fields.Date.to_string(definition.date_from) if definition.date_from else False,
            'date_to': fields.Date.to_string(definition.date_to) if definition.date_to else False,
            'property_ref': definition.property_ref,
            'site_ref': definition.site_ref,
            'utility_type': definition.utility_type,
            'meter_id': definition.meter_id.id,
            'company_id': definition.company_id.id,
        }

    def run_dto(self, run):
        chart = []
        chart_state = False
        if run.execution_state == 'completed':
            if run.result_rows is False or run.result_rows is None:
                chart_state = 'unavailable'
            else:
                try:
                    chart = self._chart_points(run.result_rows)
                    chart_state = 'ready'
                except Exception:
                    chart = []
                    chart_state = 'unavailable'
        return {
            'id': run.id,
            'name': run.name,
            'definition_id': run.definition_id.id,
            'report_type': run.definition_id.report_type,
            'execution_state': run.execution_state,
            'export_format': run.export_format,
            'attachment_id': run.attachment_id.id,
            'error_message': run.error_message,
            'company_id': run.company_id.id,
            'chart': chart,
            'chart_state': chart_state,
        }

    def _chart_points(self, rows):
        points = []
        if isinstance(rows, dict):
            for key, payload in rows.items():
                if isinstance(payload, dict):
                    for bucket in payload.get('buckets') or []:
                        points.append({
                            'label': '%s %s' % (key, bucket.get('bucket') or ''),
                            'value': bucket.get('consumption') or 0.0,
                        })
                elif isinstance(payload, (int, float)):
                    points.append({'label': key, 'value': payload})
            return points
        if not isinstance(rows, list):
            return points
        for row in rows:
            if not isinstance(row, dict):
                continue
            if 'meters' in row and 'readings' in row:
                for key in ('meters', 'online_events', 'readings', 'verified_readings', 'alerts_open', 'leaks_open'):
                    points.append({'label': key, 'value': row.get(key) or 0.0})
                continue
            label = row.get('meter') or row.get('meter_code') or row.get('property_ref') or row.get('name') or row.get('reading') or row.get('source_kind') or ''
            if isinstance(row.get('consumption'), (int, float)):
                value = row['consumption']
            elif any(name in row for name in ('electricity', 'water', 'gas')):
                value = sum(float(row.get(name) or 0.0) for name in ('electricity', 'water', 'gas'))
            else:
                continue
            points.append({'label': label or 'Result', 'value': value})
        return points

    def _reading_rows(self, filters, utility_type, verified_only=True):
        domain = reading_domain(filters, utility_type)
        if not verified_only:
            domain = [item for item in domain if item[0] != 'status']
        readings = self.env['utility.management.reading'].search(domain)
        return [{
            'reading': reading.name,
            'meter': reading.meter_id.meter_code,
            'utility': reading.meter_id.utility_type,
            'property_ref': reading.property_ref or '',
            'site_ref': reading.site_ref or '',
            'consumption': reading.consumption_qty,
            'demand_kw': reading.demand_kw,
            'flow_rate': reading.flow_rate,
            'pressure': reading.pressure,
            'status': reading.status,
        } for reading in readings]

    def _grid_rows(self, filters):
        from .consumption_service import ConsumptionService
        rows = ConsumptionService(self.env).by_meter(filters)
        grouped = {'grid': 0.0, 'generator': 0.0, 'unassigned': 0.0}
        for row in rows:
            meter = self.env['utility.management.meter'].browse(row['meter_id'])
            kind = meter.power_source_id.source_kind if meter.power_source_id else 'unassigned'
            grouped[kind] = grouped.get(kind, 0.0) + row['consumption']
        return [{'source_kind': key, 'consumption': value} for key, value in grouped.items()]

    def _performance(self, filters):
        meter_domain = []
        if filters.get('company_id'):
            meter_domain.append(('company_id', '=', filters['company_id']))
        if filters.get('property_ref'):
            meter_domain.append(('property_ref', '=', filters['property_ref']))
        meters = self.env['utility.management.meter'].with_context(active_test=False).search(meter_domain)
        logs = self.env['utility.management.connectivity'].search([('meter_id', 'in', meters.ids)])
        online = len(logs.filtered(lambda row: row.status == 'online'))
        domain = [item for item in reading_domain(filters) if item[0] != 'status']
        domain.append(('status', '!=', 'corrected'))
        readings = self.env['utility.management.reading'].search(domain)
        verified = len(readings.filtered(lambda reading: reading.status == 'verified'))
        company_domain = [('company_id', '=', filters['company_id'])] if filters.get('company_id') else []
        alerts = self.env['utility.management.alert'].search(company_domain)
        leaks = self.env['utility.management.leak'].search(company_domain)
        return {
            'meters': len(meters),
            'online_events': online,
            'connectivity_events': len(logs),
            'availability': (online / len(logs)) if logs else 0.0,
            'readings': len(readings),
            'verified_readings': verified,
            'verification_rate': (verified / len(readings)) if readings else 0.0,
            'alerts_open': len(alerts.filtered(lambda alert: alert.state not in ('resolved', 'closed'))),
            'alerts_closed': len(alerts.filtered(lambda alert: alert.state in ('resolved', 'closed'))),
            'leaks_open': len(leaks.filtered(lambda leak: leak.state != 'closed')),
            'leaks_closed': len(leaks.filtered(lambda leak: leak.state == 'closed')),
        }

    def _export(self, run, rows, export_format):
        table = self._table(rows)
        if export_format == 'csv':
            return self._csv(table), 'text/csv', 'csv'
        if export_format == 'xlsx':
            return self._xlsx(table), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'xlsx'
        return self._pdf(run), 'application/pdf', 'pdf'

    def _table(self, rows):
        if isinstance(rows, dict):
            rows = [rows]
        if not rows:
            return [['No rows']]
        if not isinstance(rows[0], dict):
            return [[str(item)] for item in rows]
        headers = list(rows[0].keys())
        table = [headers]
        for row in rows:
            table.append([row.get(header, '') for header in headers])
        return table

    def _csv(self, table):
        buffer = io.StringIO()
        csv.writer(buffer).writerows(table)
        return buffer.getvalue().encode('utf-8')

    def _xlsx(self, table):
        sheet = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for index, row in enumerate(table, start=1):
            cells = []
            for column, value in enumerate(row, start=1):
                letter = chr(64 + column) if column <= 26 else 'A'
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
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
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
        try:
            pdf, _report_type = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'utility_management.action_report_utility_run',
                [run.id],
            )
        except Exception as exc:
            raise UserError('PDF export is unavailable. %s' % exc)
        return pdf

    def _b64(self, payload):
        import base64
        if isinstance(payload, str):
            payload = payload.encode('utf-8')
        return base64.b64encode(payload)

    def _snapshot(self, rows):
        return json.loads(json.dumps(rows, default=self._json_default))

    def _json_default(self, value):
        if isinstance(value, datetime):
            return fields.Datetime.to_string(value)
        if isinstance(value, date):
            return fields.Date.to_string(value)
        return str(value)

    def _lock_definition(self, definition):
        self.env.cr.execute(
            'SELECT id FROM %s WHERE id = %%s FOR UPDATE' % definition._table,
            [definition.id],
        )

    def _is_due(self, definition, today):
        if definition.schedule not in ('daily', 'weekly', 'monthly'):
            return False
        runs = self.env['utility.management.report.run'].sudo().search([
            ('definition_id', '=', definition.id),
        ])
        if runs.filtered(lambda item: item.execution_state == 'pending'):
            return False
        completed = runs.filtered(
            lambda item: item.execution_state == 'completed' and item.started_at
        ).sorted(key=lambda item: (item.started_at, item.id), reverse=True)
        last = completed[:1]
        if not last:
            return True
        last_day = fields.Datetime.context_timestamp(self.env.user, last.started_at).date()
        if last_day == today:
            return False
        if definition.schedule == 'daily':
            return last_day < today
        if definition.schedule == 'weekly':
            return last_day <= today - timedelta(days=7)
        if definition.schedule == 'monthly':
            return last_day <= today - timedelta(days=28)
        return False
