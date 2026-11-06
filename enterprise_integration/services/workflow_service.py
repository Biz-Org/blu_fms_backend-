# -*- coding: utf-8 -*-
"""End-to-end workflow orchestration helpers (thin layer over services)."""
import uuid

from .api_service import ApiService
from .exceptions import EiValidationError
from .health_service import HealthService
from .logging_service import LoggingService
from .mapping_service import MappingService
from .master_data_service import MasterDataService
from .sync_service import SyncService
from .webhook_service import WebhookService


class WorkflowService:
    """
    Canonical inbound pipeline:

      External system -> API/Webhook -> Validate -> Transform -> Sync -> Log -> Monitor

    Stages are logged on ei.log with operation pipeline_* for Monitoring correlation.
    """

    PIPELINE_STAGES = (
        'external',
        'api_webhook',
        'validate',
        'transform',
        'sync',
        'log',
        'monitor',
    )

    def __init__(self, env):
        self.env = env
        self.logs = LoggingService(env)
        self.mapping = MappingService()

    def test_api_endpoint(self, endpoint, api_key=None):
        """Safe API test — does not expose secrets; records ei.log."""
        if endpoint.state not in ('active', 'restricted', 'inactive'):
            raise EiValidationError('Endpoint cannot be tested in current state')
        key = api_key
        if not key and endpoint.credential_ids:
            correlation_id = str(uuid.uuid4())
            self.logs.log(
                name=f'API test {endpoint.method} {endpoint.path}',
                category='api',
                level='warning',
                operation='api_test',
                endpoint_id=endpoint.id,
                integration_id=endpoint.integration_id.id,
                correlation_id=correlation_id,
                response_summary=(
                    'Configuration test only — provide X-API-Key for authenticated live test. '
                    'Plaintext keys are never recoverable from storage.'
                ),
            )
            return {
                'ok': True,
                'mode': 'config_test',
                'message': 'Endpoint configuration validated. Authenticated call requires API key input.',
                'correlation_id': correlation_id,
            }
        was_state = endpoint.state
        if was_state == 'inactive':
            endpoint.sudo().write({'state': 'active'})
        try:
            result = ApiService(self.env).handle_request(
                endpoint, endpoint.method, payload={}, api_key=key,
                idempotency_key=f'test-{uuid.uuid4().hex[:12]}',
            )
        finally:
            if was_state == 'inactive':
                endpoint.sudo().write({'state': was_state})
        return result

    def test_connector(self, connector):
        return HealthService(self.env).check_connector(connector)

    def run_sync(self, job, correlation_id=None, inbound_records=None):
        return SyncService(self.env).run_job(
            job, correlation_id=correlation_id, inbound_records=inbound_records,
        )

    def sync_master(self, mapping, correlation_id=None):
        return MasterDataService(self.env).synchronize_mapping(
            mapping, correlation_id=correlation_id,
        )

    def enqueue_webhook(self, webhook, payload, event_type=None):
        return WebhookService(self.env).enqueue_outgoing(
            webhook, payload, event_type=event_type,
        )

    def process_webhook_queue(self):
        return WebhookService(self.env).process_pending_outgoing()

    def process_inbound(
        self,
        payload,
        *,
        correlation_id=None,
        source='api',
        integration=None,
        endpoint=None,
        webhook=None,
        sync_job=None,
    ):
        """
        Run Validate -> Transform -> Sync -> Log for an accepted inbound payload.

        When no sync job is linked, still validates and logs so Monitoring can
        show the pipeline path.
        """
        correlation_id = correlation_id or str(uuid.uuid4())
        logger = self.logs.with_correlation(correlation_id)
        integration = integration or (
            endpoint.integration_id if endpoint else (
                webhook.integration_id if webhook else False
            )
        )
        sync_job = sync_job or (
            endpoint.pipeline_sync_job_id if endpoint else False
        ) or (
            webhook.pipeline_sync_job_id if webhook else False
        )
        stages = {
            'external': 'ok',
            'api_webhook': 'ok',
            'validate': 'pending',
            'transform': 'pending',
            'sync': 'skipped',
            'log': 'pending',
            'monitor': 'ok',
        }
        result = {
            'ok': True,
            'correlation_id': correlation_id,
            'pipeline': True,
            'stages': stages,
            'sync_run_id': False,
            'transformed': None,
        }

        # --- Validate ---
        try:
            records = self._validate_inbound_payload(payload)
            stages['validate'] = 'ok'
            logger.log(
                name=f'Pipeline validate ({source})',
                category='system',
                level='success',
                operation='pipeline_validate',
                integration_id=integration.id if integration else False,
                endpoint_id=endpoint.id if endpoint else False,
                webhook_id=webhook.id if webhook else False,
                response_summary=f'records={len(records)}',
            )
        except EiValidationError as exc:
            stages['validate'] = 'failed'
            stages['transform'] = 'skipped'
            stages['sync'] = 'skipped'
            stages['log'] = 'ok'
            result['ok'] = False
            result['error'] = 'invalid_payload'
            result['message'] = str(exc)
            logger.log(
                name=f'Pipeline validate failed ({source})',
                category='system',
                level='rejected',
                operation='pipeline_validate',
                integration_id=integration.id if integration else False,
                endpoint_id=endpoint.id if endpoint else False,
                webhook_id=webhook.id if webhook else False,
                error_class=exc.error_class,
                error_message=str(exc),
                retryable=False,
            )
            return result

        # --- Transform ---
        try:
            mapping_lines = (
                sync_job.mapping_ids.filtered('active')
                if sync_job else self.env['ei.connector.mapping']
            )
            transformed = []
            for item in records:
                if mapping_lines:
                    transformed.append(self.mapping.apply_mappings(item, mapping_lines))
                else:
                    transformed.append(dict(item))
            stages['transform'] = 'ok'
            result['transformed'] = transformed
            logger.log(
                name=f'Pipeline transform ({source})',
                category='system',
                level='success',
                operation='pipeline_transform',
                integration_id=integration.id if integration else False,
                endpoint_id=endpoint.id if endpoint else False,
                webhook_id=webhook.id if webhook else False,
                response_summary=(
                    f'records={len(transformed)} mappings={len(mapping_lines)}'
                ),
            )
        except EiValidationError as exc:
            stages['transform'] = 'failed'
            stages['sync'] = 'skipped'
            stages['log'] = 'ok'
            result['ok'] = False
            result['error'] = 'transform_failed'
            result['message'] = str(exc)
            logger.log(
                name=f'Pipeline transform failed ({source})',
                category='system',
                level='failed',
                operation='pipeline_transform',
                integration_id=integration.id if integration else False,
                endpoint_id=endpoint.id if endpoint else False,
                webhook_id=webhook.id if webhook else False,
                error_class=exc.error_class,
                error_message=str(exc),
                retryable=True,
            )
            return result

        # --- Sync ---
        if sync_job:
            try:
                run = self.run_sync(
                    sync_job,
                    correlation_id=correlation_id,
                    inbound_records=transformed,
                )
                stages['sync'] = (
                    'ok' if run.state in ('completed', 'partially_completed') else 'failed'
                )
                result['sync_run_id'] = run.id
                if stages['sync'] == 'failed':
                    result['ok'] = False
                    result['error'] = 'sync_failed'
                    result['message'] = run.error_message or 'Sync run failed'
            except Exception as exc:  # noqa: BLE001
                stages['sync'] = 'failed'
                result['ok'] = False
                result['error'] = 'sync_failed'
                result['message'] = str(exc)
                logger.log(
                    name=f'Pipeline sync failed ({source})',
                    category='sync',
                    level='failed',
                    operation='pipeline_sync',
                    integration_id=integration.id if integration else False,
                    endpoint_id=endpoint.id if endpoint else False,
                    webhook_id=webhook.id if webhook else False,
                    error_class=type(exc).__name__,
                    error_message=str(exc),
                    retryable=True,
                )
        else:
            stages['sync'] = 'skipped'
            logger.log(
                name=f'Pipeline sync skipped ({source})',
                category='system',
                level='warning',
                operation='pipeline_sync',
                integration_id=integration.id if integration else False,
                endpoint_id=endpoint.id if endpoint else False,
                webhook_id=webhook.id if webhook else False,
                response_summary='No pipeline sync job linked on endpoint/webhook',
            )

        # --- Log summary + Monitor ---
        stages['log'] = 'ok'
        stages['monitor'] = 'ok'
        logger.log(
            name=f'Pipeline complete ({source})',
            category='system',
            level='success' if result['ok'] else 'failed',
            operation='pipeline_complete',
            integration_id=integration.id if integration else False,
            endpoint_id=endpoint.id if endpoint else False,
            webhook_id=webhook.id if webhook else False,
            sync_run_id=result.get('sync_run_id') or False,
            response_summary=str(stages),
        )
        return result

    def _validate_inbound_payload(self, payload):
        """Normalize inbound payload into a list of record dicts."""
        if payload is None:
            raise EiValidationError('Payload is required')
        if isinstance(payload, list):
            if not payload:
                raise EiValidationError('Payload list is empty')
            records = payload
        elif isinstance(payload, dict):
            if isinstance(payload.get('records'), list):
                records = payload['records']
                if not records:
                    raise EiValidationError('Payload records list is empty')
            else:
                records = [payload]
        else:
            raise EiValidationError('Payload must be a JSON object or array')
        for idx, item in enumerate(records):
            if not isinstance(item, dict):
                raise EiValidationError(f'Record at index {idx} must be an object')
        return records
