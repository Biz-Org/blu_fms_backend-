# -*- coding: utf-8 -*-
"""Synchronization execution engine."""
import uuid

from odoo import fields

from .connectors.registry import get_adapter
from .exceptions import EiDuplicateError, EiValidationError
from .logging_service import LoggingService
from .mapping_service import MappingService



class SyncService:
    def __init__(self, env):
        self.env = env
        self.logs = LoggingService(env)
        self.mapping = MappingService()

    def run_job(self, job, correlation_id=None, inbound_records=None):
        correlation_id = correlation_id or str(uuid.uuid4())
        logger = self.logs.with_correlation(correlation_id)
        self._validate_job(job)

        run = self.env['ei.sync.run'].sudo().create({
            'name': f'{job.name} @ {fields.Datetime.now()}',
            'job_id': job.id,
            'state': 'running',
            'started_at': fields.Datetime.now(),
            'correlation_id': correlation_id,
        })
        logger.log(
            name=f'Sync started {job.name}',
            category='sync',
            level='warning',
            operation='sync_start',
            integration_id=job.integration_id.id,
            sync_run_id=run.id,
            source_system=job.source_system or (job.source_connector_id.name if job.source_connector_id else ''),
            destination_system=job.dest_system or (job.dest_connector_id.name if job.dest_connector_id else ''),
        )

        total = success = failed = conflicts = duplicates = 0
        try:
            if inbound_records is not None:
                records = list(inbound_records)
            else:
                records = self._fetch_source(job, correlation_id)
            seen_keys = set()
            mapping_lines = job.mapping_ids.filtered('active')

            if not records:
                # Still record a successful empty/full placeholder for mock jobs
                self.env['ei.sync.record'].sudo().create({
                    'run_id': run.id,
                    'external_id': f'empty-{correlation_id[:8]}',
                    'state': 'success',
                    'correlation_id': correlation_id,
                    'external_ref': correlation_id,
                    'payload_summary': f'No source records ({job.mode}/{job.trigger})',
                })
                total = success = 1
            else:
                for item in records:
                    total += 1
                    try:
                        outcome = self._process_record(
                            job, run, item, mapping_lines, seen_keys, correlation_id,
                        )
                        if outcome == 'success':
                            success += 1
                        elif outcome == 'conflict':
                            conflicts += 1
                        elif outcome == 'duplicate':
                            duplicates += 1
                        else:
                            failed += 1
                    except Exception as rec_exc:  # noqa: BLE001
                        failed += 1
                        self.env['ei.sync.record'].sudo().create({
                            'run_id': run.id,
                            'external_id': str(item.get('external_id') or item.get('id') or ''),
                            'state': 'failed',
                            'error_message': str(rec_exc),
                            'correlation_id': correlation_id,
                            'external_ref': correlation_id,
                            'payload_summary': str(item)[:500],
                        })
                        self.env['ei.log'].sudo().ei_log(
                            name=f'Sync record failed {job.name}',
                            category='sync',
                            level='failed',
                            operation='sync_record_fail',
                            integration_id=job.integration_id.id,
                            sync_run_id=run.id,
                            correlation_id=correlation_id,
                            error_message=str(rec_exc),
                            retryable=True,
                        )

            if job.dest_connector_id and success and failed == 0 and conflicts == 0:
                dest_adapter = get_adapter(self.env, job.dest_connector_id)
                dest_adapter.push(job.entity_name, {
                    'correlation_id': correlation_id,
                    'count': success,
                })

            if failed and (success or conflicts or duplicates):
                state = 'partially_completed'
            elif failed and not success and not conflicts and not duplicates:
                state = 'failed'
            elif conflicts and not success and not failed:
                state = 'partially_completed'
            else:
                state = 'completed'

            run.write({
                'state': state,
                'ended_at': fields.Datetime.now(),
                'records_processed': total,
                'records_success': success,
                'records_failed': failed,
                'records_conflict': conflicts,
                'records_duplicate': duplicates,
            })
            if state in ('completed', 'partially_completed'):
                job.sudo().write({
                    'last_success_at': fields.Datetime.now(),
                    'last_run_state': state,
                })
            else:
                job.sudo().write({'last_run_state': state})

            logger.log(
                name=f'Sync finished {job.name}',
                category='sync',
                level='success' if failed == 0 and conflicts == 0 else (
                    'warning' if success or conflicts else 'failed'
                ),
                operation='sync_finish',
                integration_id=job.integration_id.id,
                sync_run_id=run.id,
                source_system=job.source_system,
                destination_system=job.dest_system,
                response_summary=(
                    f'total={total} success={success} failed={failed} '
                    f'conflicts={conflicts} duplicates={duplicates}'
                ),
                retryable=failed > 0,
            )
        except Exception as exc:  # noqa: BLE001
            run.write({
                'state': 'failed',
                'ended_at': fields.Datetime.now(),
                'error_message': str(exc),
                'records_processed': total,
                'records_success': success,
                'records_failed': failed or 1,
            })
            job.sudo().write({'last_run_state': 'failed'})
            logger.log(
                name=f'Sync failed {job.name}',
                category='sync',
                level='failed',
                operation='sync_fail',
                integration_id=job.integration_id.id,
                sync_run_id=run.id,
                error_class=type(exc).__name__,
                error_message=str(exc),
                retryable=True,
            )
        return run

    def _validate_job(self, job):
        if job.state not in ('active', 'draft'):
            # Allow draft manual runs; scheduled requires active (enforced by cron domain)
            pass
        has_source = bool(job.source_connector_id or job.source_system)
        has_dest = bool(job.dest_connector_id or job.dest_system)
        if not has_source or not has_dest:
            raise EiValidationError('Sync job requires source and destination')

    def _fetch_source(self, job, correlation_id):
        if job.source_connector_id:
            adapter = get_adapter(self.env, job.source_connector_id)
            adapter.authenticate()
            params = {'mode': job.mode, 'correlation_id': correlation_id}
            if job.mode == 'incremental' and job.last_success_at:
                params['since'] = str(job.last_success_at)
            result = adapter.synchronize(job.entity_name, params=params)
            return result.get('records') or []
        # Logical system without connector — empty set
        return []

    def _process_record(self, job, run, item, mapping_lines, seen_keys, correlation_id):
        external_id = str(item.get('external_id') or item.get('id') or '')
        mapped = self.mapping.apply_mappings(item, mapping_lines) if mapping_lines else dict(item)

        # Duplicate detection by external id within run + policy
        dup_key = external_id or self.mapping.duplicate_key(mapped, ['code', 'name'])
        if dup_key and dup_key in seen_keys:
            if job.duplicate_policy == 'error':
                raise EiDuplicateError(f'Duplicate key {dup_key}')
            self.env['ei.sync.record'].sudo().create({
                'run_id': run.id,
                'external_id': external_id,
                'state': 'skipped' if job.duplicate_policy == 'skip' else 'success',
                'is_duplicate': True,
                'correlation_id': correlation_id,
                'external_ref': correlation_id,
                'payload_summary': str(mapped)[:500],
            })
            return 'duplicate'
        if dup_key:
            seen_keys.add(dup_key)

        # Conflict detection: marker in payload or two-way mismatch flag
        if item.get('_conflict') or mapped.get('_conflict'):
            if job.conflict_policy == 'skip':
                self.env['ei.sync.record'].sudo().create({
                    'run_id': run.id,
                    'external_id': external_id,
                    'state': 'skipped',
                    'correlation_id': correlation_id,
                    'external_ref': correlation_id,
                    'payload_summary': 'conflict skipped',
                })
                return 'conflict'
            if job.conflict_policy == 'manual':
                self.env['ei.sync.record'].sudo().create({
                    'run_id': run.id,
                    'external_id': external_id,
                    'state': 'conflict',
                    'error_message': 'Conflict requires manual resolution',
                    'correlation_id': correlation_id,
                    'external_ref': correlation_id,
                    'payload_summary': str({'source': item, 'mapped': mapped})[:500],
                })
                return 'conflict'
            # source_wins / destination_wins continue as success with note

        if item.get('_fail'):
            raise EiValidationError('Record marked to fail')

        self.env['ei.sync.record'].sudo().create({
            'run_id': run.id,
            'external_id': external_id,
            'state': 'success',
            'payload_summary': str(mapped)[:500],
            'correlation_id': correlation_id,
            'external_ref': correlation_id,
        })
        return 'success'
