# -*- coding: utf-8 -*-
"""Master data integration service with source-of-truth awareness."""
import uuid

from odoo import fields

from .exceptions import EiValidationError
from .logging_service import LoggingService
from .mapping_service import MappingService
from .transform_service import TransformService


class MasterDataService:
    ENTITY_CODES = (
        'customer', 'supplier', 'product', 'employee',
        'account', 'site_location', 'department',
    )

    def __init__(self, env):
        self.env = env
        self.logs = LoggingService(env)
        self.mapping = MappingService()
        self.transform = TransformService()

    def synchronize_mapping(self, mapping, correlation_id=None):
        correlation_id = correlation_id or str(uuid.uuid4())
        logger = self.logs.with_correlation(correlation_id)
        self._validate_mapping(mapping)

        # Source-of-truth determines direction of authority
        sot = mapping.source_of_truth
        logger.log(
            name=f'Master sync {mapping.name}',
            category='master_data',
            level='warning',
            operation='master_sync_start',
            integration_id=mapping.integration_id.id if mapping.integration_id else False,
            master_mapping_id=mapping.id,
            source_system=mapping.source_system,
            destination_system=mapping.target_system,
            response_summary=f'source_of_truth={sot}',
        )

        # If linked connectors exist, reuse sync engine via ephemeral-like path:
        # Prefer pushing through SyncService when a sync job is not required —
        # perform a lightweight fetch/map/validate cycle here.
        source_records = []
        if mapping.source_connector_id:
            from .connectors.registry import get_adapter
            adapter = get_adapter(self.env, mapping.source_connector_id)
            adapter.authenticate()
            entity_code = mapping.entity_id.code
            source_records = adapter.fetch(entity_code).get('records') or []

        field_maps = self._mapping_lines_from_json(mapping)
        conflicts = 0
        synced = 0
        for record in source_records or [{'external_id': f'mock-{mapping.entity_id.code}', 'name': mapping.entity_id.name}]:
            mapped = self.mapping.apply_mappings(record, field_maps) if field_maps else dict(record)
            self._validate_record(mapping, mapped)

            dup_key = self.mapping.duplicate_key(
                mapped,
                [k.strip() for k in (mapping.duplicate_detection_keys or 'external_id').split(',') if k.strip()],
            )
            if record.get('_duplicate'):
                self.detect_conflict(mapping, str(record), str(mapped), is_duplicate=True)
                conflicts += 1
                continue
            if record.get('_conflict'):
                self.detect_conflict(mapping, str(record), str(mapped), is_duplicate=False)
                conflicts += 1
                continue

            # Source-of-truth: never silently overwrite the SoT system
            if sot == 'manual' and not record.get('_resolved'):
                self.detect_conflict(mapping, str(record), str(mapped), is_duplicate=False)
                conflicts += 1
                continue
            if sot in ('target', 'precastmps') and not record.get('_from_sot'):
                # Foreign source must not overwrite SoT destination without review
                self.detect_conflict(
                    mapping,
                    left=str(record),
                    right=str(mapped),
                    is_duplicate=False,
                )
                conflicts += 1
                continue

            if mapping.target_connector_id:
                from .connectors.registry import get_adapter
                get_adapter(self.env, mapping.target_connector_id).push(
                    mapping.entity_id.code, mapped,
                )
            synced += 1

        new_state = 'conflict' if conflicts and not synced else ('synced' if conflicts == 0 else 'updated')
        mapping.sudo().write({
            'state': new_state,
            'last_sync_at': fields.Datetime.now(),
            'change_note': f'synced={synced} conflicts={conflicts} sot={sot}',
        })
        logger.log(
            name=f'Master sync done {mapping.name}',
            category='master_data',
            level='success' if conflicts == 0 else 'warning',
            operation='master_sync_finish',
            integration_id=mapping.integration_id.id if mapping.integration_id else False,
            master_mapping_id=mapping.id,
            source_system=mapping.source_system,
            destination_system=mapping.target_system,
            response_summary=mapping.change_note,
        )
        return {'synced': synced, 'conflicts': conflicts, 'state': new_state}

    def detect_conflict(self, mapping, left, right, is_duplicate=False):
        conflict = self.env['ei.master.conflict'].sudo().create({
            'name': f'{"Duplicate" if is_duplicate else "Conflict"} on {mapping.name}',
            'mapping_id': mapping.id,
            'state': 'conflict',
            'left_payload': left,
            'right_payload': right,
            'is_duplicate': is_duplicate,
        })
        mapping.sudo().write({'state': 'conflict'})
        self.logs.log(
            name=f'Master data conflict {mapping.name}',
            category='master_data',
            level='warning',
            operation='master_conflict',
            integration_id=mapping.integration_id.id if mapping.integration_id else False,
            master_mapping_id=mapping.id,
            source_system=mapping.source_system,
            destination_system=mapping.target_system,
            retryable=False,
        )
        return conflict

    def resolve(self, conflict, resolution, user):
        conflict.write({
            'state': 'resolved',
            'resolution': resolution,
            'resolved_by': user.id,
            'resolved_at': fields.Datetime.now(),
        })
        if conflict.mapping_id:
            conflict.mapping_id.write({
                'state': 'synced',
                'change_note': f'Resolved conflict {conflict.id}',
                'last_sync_at': fields.Datetime.now(),
            })
        self.logs.log(
            name=f'Resolved conflict {conflict.name}',
            category='master_data',
            level='success',
            operation='master_conflict_resolve',
            master_mapping_id=conflict.mapping_id.id,
        )
        return conflict

    def _validate_mapping(self, mapping):
        if mapping.entity_id.code not in self.ENTITY_CODES:
            raise EiValidationError(f'Unsupported master entity {mapping.entity_id.code}')
        if mapping.source_system == mapping.target_system:
            raise EiValidationError('Source and target systems must differ')

    def _validate_record(self, mapping, record):
        rules = (mapping.validation_rules or '').strip()
        if not rules:
            return True
        # Simple required: field list "required:a,b,c"
        if rules.lower().startswith('required:'):
            fields_req = [f.strip() for f in rules.split(':', 1)[1].split(',') if f.strip()]
            missing = [f for f in fields_req if not (record or {}).get(f)]
            if missing:
                raise EiValidationError(f'Missing required fields: {", ".join(missing)}')
        return True

    def _mapping_lines_from_json(self, mapping):
        """Parse field_mapping_json as list of {source_field,target_field,transform_type,transform_expr}."""
        import json
        raw = mapping.field_mapping_json
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        if isinstance(data, dict):
            # {"src": "dst"} shorthand
            return [
                {'source_field': k, 'target_field': v, 'transform_type': 'none', 'active': True}
                for k, v in data.items()
            ]
        return data
