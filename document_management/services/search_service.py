# -*- coding: utf-8 -*-
import csv
from io import StringIO

from odoo.osv import expression

from .access_service import DocumentAccessService


class DocumentSearchService:
    def __init__(self, env):
        self.env = env

    def _access(self):
        return DocumentAccessService(self.env)

    def _search_domain(self, query=None, filters=None):
        filters = filters or {}
        domain = []
        query = (query or '').strip()
        if query:
            domain = expression.OR([
                [('name', 'ilike', query)],
                [('code', 'ilike', query)],
                [('description', 'ilike', query)],
                [('tag_ids.name', 'ilike', query)],
                [('owner_id.name', 'ilike', query)],
                [('type_id.name', 'ilike', query)],
                [('category_id.name', 'ilike', query)],
                [('department_label', 'ilike', query)],
                [('property_ref', 'ilike', query)],
                [('asset_ref', 'ilike', query)],
            ])
        extra = []
        if filters.get('state'):
            extra.append(('state', '=', filters['state']))
        if filters.get('folder_id'):
            extra.append(('folder_id', '=', filters['folder_id']))
        if filters.get('type_id'):
            extra.append(('type_id', '=', filters['type_id']))
        if filters.get('category_id'):
            extra.append(('category_id', '=', filters['category_id']))
        if filters.get('access_level'):
            extra.append(('access_level', '=', filters['access_level']))
        if filters.get('department') or filters.get('department_label'):
            extra.append(('department_label', 'ilike', filters.get('department') or filters.get('department_label')))
        if filters.get('property_ref') or filters.get('property'):
            extra.append(('property_ref', 'ilike', filters.get('property_ref') or filters.get('property')))
        if filters.get('asset_ref') or filters.get('asset'):
            extra.append(('asset_ref', 'ilike', filters.get('asset_ref') or filters.get('asset')))
        if filters.get('date_from'):
            extra.append(('effective_date', '>=', filters['date_from']))
        if filters.get('date_to'):
            extra.append(('effective_date', '<=', filters['date_to']))
        if extra:
            domain = expression.AND([domain, extra]) if domain else extra
        return domain

    def _hit(self, document):
        return {
            'id': document.id,
            'name': document.name,
            'code': document.code,
            'description': document.description,
            'state': document.state,
            'owner': document.owner_id.name,
            'type': document.type_id.name if document.type_id else False,
            'category': document.category_id.name if document.category_id else False,
            'tags': document.tag_ids.mapped('name'),
            'department_label': document.department_label,
            'property_ref': document.property_ref,
            'asset_ref': document.asset_ref,
        }

    def keyword_search(self, query=None, filters=None):
        domain = self._search_domain(query, filters)
        documents = self._access().visible_documents(extra_domain=domain)
        return {
            'hits': [self._hit(document) for document in documents],
            'total': len(documents),
            'query': query or '',
        }

    def export_search_csv(self, query=None, filters=None, mode=None):
        data = self.keyword_search(query, filters)
        handle = StringIO()
        writer = csv.writer(handle)
        writer.writerow(['name', 'code', 'state', 'owner', 'type', 'category', 'tags'])
        for hit in data['hits']:
            writer.writerow([
                hit['name'] or '',
                hit['code'] or '',
                hit['state'] or '',
                hit['owner'] or '',
                hit['type'] or '',
                hit['category'] or '',
                ', '.join(hit['tags'] or []),
            ])
        return {
            'filename': 'document-search.csv',
            'csv': handle.getvalue(),
        }
