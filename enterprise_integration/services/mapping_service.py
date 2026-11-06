# -*- coding: utf-8 -*-
"""Configurable field mapping using domain mapping lines + TransformService."""
from .transform_service import TransformService
from .exceptions import EiValidationError


class MappingService:
    def __init__(self, transform_service=None):
        self.transform = transform_service or TransformService()

    def apply_mappings(self, source_record, mapping_lines, require_all=False):
        """
        mapping_lines: iterable of objects/dicts with
        source_field, target_field, transform_type, transform_expr, active
        """
        result = {}
        lines = list(mapping_lines or [])
        if not lines:
            # No mappings configured — shallow copy
            return dict(source_record or {})

        for line in lines:
            active = self._get(line, 'active', True)
            if active is False:
                continue
            source_field = self._get(line, 'source_field')
            target_field = self._get(line, 'target_field')
            if not source_field or not target_field:
                raise EiValidationError('Mapping line missing source/target field')
            raw = (source_record or {}).get(source_field)
            transform_type = self._get(line, 'transform_type', 'none') or 'none'
            transform_expr = self._get(line, 'transform_expr')
            try:
                result[target_field] = self.transform.apply(
                    raw, transform_type=transform_type, transform_expr=transform_expr,
                )
            except Exception as exc:  # noqa: BLE001
                raise EiValidationError(
                    f'Transform failed for {source_field}→{target_field}: {exc}',
                    details={'source_field': source_field, 'target_field': target_field},
                ) from exc

        if require_all and not result:
            raise EiValidationError('No mapped fields produced')
        return result

    def duplicate_key(self, record, keys):
        if not keys:
            return None
        parts = []
        for key in keys:
            parts.append(str((record or {}).get(key, '')))
        return '|'.join(parts)

    @staticmethod
    def _get(line, key, default=None):
        if isinstance(line, dict):
            return line.get(key, default)
        return getattr(line, key, default)
