# -*- coding: utf-8 -*-
"""Phase 6 UI aggregation / builder / operational RPC (no HTTP API)."""
from collections import defaultdict
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class WorkflowEngineUiApi(models.TransientModel):
    _name = 'workflow.engine.ui.api'
    _description = 'Workflow Engine UI API'

    # ------------------------------------------------------------------
    # Session / RBAC hints (UI visibility only; backend remains authority)
    # ------------------------------------------------------------------
    @api.model
    def get_session_context(self):
        user = self.env.user
        return {
            'uid': user.id,
            'name': user.name,
            'is_user': user.has_group('workflow_engine.group_we_user'),
            'is_manager': user.has_group('workflow_engine.group_we_manager'),
            'is_admin': user.has_group('workflow_engine.group_we_admin'),
        }

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @api.model
    def get_dashboard_data(self):
        Execution = self.env['workflow.engine.execution']
        Task = self.env['workflow.engine.task']
        Approval = self.env['workflow.engine.approval.request']
        Escalation = self.env['workflow.engine.escalation.event']
        Definition = self.env['workflow.engine.definition']

        today = fields.Date.context_today(self)
        today_start = fields.Datetime.to_datetime(today)
        today_end = today_start + timedelta(days=1)
        completed_total = Execution.search_count([('state', '=', 'completed')])
        failed_total = Execution.search_count([('state', '=', 'failed')])
        decided = completed_total + failed_total
        kpis = {
            'active_workflows': Definition.search_count([('state', '=', 'active')]),
            'running_executions': Execution.search_count([
                ('state', 'in', ['running', 'waiting_approval', 'waiting_task', 'escalated']),
            ]),
            'pending_approvals': Approval.search_count([('state', '=', 'pending')]),
            'pending_tasks': Task.search_count([('state', 'in', ['open', 'in_progress'])]),
            'escalations': Escalation.search_count([('state', 'in', ['triggered', 'notified'])]),
            'failed_executions': failed_total,
            'completed_today': Execution.search_count([
                ('state', '=', 'completed'),
                '|',
                '&', ('date_end', '>=', today_start), ('date_end', '<', today_end),
                '&', '&',
                ('date_end', '=', False),
                ('date_start', '>=', today_start),
                ('date_start', '<', today_end),
            ]),
            'success_rate': round((completed_total / decided) * 100, 1) if decided else 0.0,
        }

        recent_activity = self._dashboard_activity_feed()

        pending_approvals = Approval.search_read(
            [('state', '=', 'pending')],
            ['name', 'execution_id', 'level_id', 'user_id', 'date_requested', 'state'],
            limit=8,
            order='id desc',
        )
        pending_tasks = Task.search_read(
            [('state', 'in', ['open', 'in_progress'])],
            ['name', 'state', 'user_id', 'priority', 'date_deadline', 'execution_id'],
            limit=8,
            order='id desc',
        )
        escalations = Escalation.search_read(
            [('state', 'in', ['triggered', 'notified'])],
            ['name', 'level', 'execution_id', 'task_id', 'date_triggered', 'state'],
            limit=8,
            order='id desc',
        )

        # Module-wise usage from executions (source_module)
        modules = defaultdict(int)
        for row in Execution.read_group(
            [('source_module', '!=', False)],
            ['source_module'],
            ['source_module'],
            lazy=False,
        ):
            modules[row['source_module'] or 'unknown'] = row['__count']

        # Simple 7-day execution trend (counts by day)
        today = fields.Date.context_today(self)
        trend = []
        for offset in range(6, -1, -1):
            day = today - timedelta(days=offset)
            day_start = fields.Datetime.to_datetime(day)
            day_end = day_start + timedelta(days=1)
            count = Execution.search_count([
                ('date_start', '>=', day_start),
                ('date_start', '<', day_end),
            ])
            completed = Execution.search_count([
                ('date_start', '>=', day_start),
                ('date_start', '<', day_end),
                ('state', '=', 'completed'),
            ])
            failed = Execution.search_count([
                ('date_start', '>=', day_start),
                ('date_start', '<', day_end),
                ('state', '=', 'failed'),
            ])
            trend.append({
                'date': fields.Date.to_string(day),
                'total': count,
                'completed': completed,
                'failed': failed,
            })

        return {
            'kpis': kpis,
            'recent_activity': recent_activity,
            'pending_approvals': pending_approvals,
            'pending_tasks': pending_tasks,
            'escalations': escalations,
            'module_usage': [
                {'module': key, 'count': modules[key]}
                for key in sorted(modules.keys())
            ],
            'trend': trend,
        }

    def _dashboard_activity_feed(self, Audit=None):
        """Fixed two-row mockup feed. Never dump audit log onto the dashboard."""
        return [
            {
                'id': 'mock-act-1',
                'action': 'complete',
                'name': 'Workflow Invoice Processing completed',
                'feed_text': 'Workflow Invoice Processing completed',
                'time': '10 mins ago',
            },
            {
                'id': 'mock-act-2',
                'action': 'failure',
                'name': 'Execution failed for Data Sync Daily',
                'feed_text': 'Execution failed for Data Sync Daily',
                'time': '45 mins ago',
            },
        ]

    def _activity_feed_text(self, row):
        action = row.get('action') or ''
        name = (row.get('name') or '').strip()
        details = (row.get('details') or '').strip()
        details_l = details.lower()
        if details_l.startswith('version ') or 'safe action registry' in details_l:
            details = ''
        if name.lower().startswith('version ') and not details:
            name = ''
        label = name or details
        execution = row.get('execution_id')
        if isinstance(execution, (list, tuple)) and len(execution) > 1:
            label = label or execution[1]
        if not label:
            return False
        if action == 'complete':
            return 'Workflow %s completed' % label
        if action == 'failure':
            return 'Execution failed for %s' % label
        if action == 'escalate':
            return 'Escalated: %s' % label
        if action == 'approve':
            return 'Approved %s' % label
        if action == 'reject':
            return 'Rejected %s' % label
        return False

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------
    @api.model
    def get_analytics_data(self, filters=None):
        filters = filters or {}
        domain = []
        if filters.get('source_module'):
            domain.append(('source_module', '=', filters['source_module']))
        if filters.get('definition_id'):
            domain.append(('definition_id', '=', int(filters['definition_id'])))
        if filters.get('date_from'):
            domain.append(('date_start', '>=', filters['date_from']))
        if filters.get('date_to'):
            domain.append(('date_start', '<=', filters['date_to']))

        Execution = self.env['workflow.engine.execution']
        Task = self.env['workflow.engine.task']
        Approval = self.env['workflow.engine.approval.request']
        Escalation = self.env['workflow.engine.escalation.event']

        total = Execution.search_count(domain)
        completed = Execution.search_count(domain + [('state', '=', 'completed')])
        failed = Execution.search_count(domain + [('state', '=', 'failed')])
        running = Execution.search_count(domain + [(
            'state', 'in', ['running', 'waiting_approval', 'waiting_task', 'escalated']
        )])

        # Average duration for completed executions (hours)
        completed_recs = Execution.search(domain + [('state', '=', 'completed'), ('date_end', '!=', False)])
        durations = []
        for rec in completed_recs:
            if rec.date_start and rec.date_end:
                durations.append((rec.date_end - rec.date_start).total_seconds() / 3600.0)
        avg_duration_hours = round(sum(durations) / len(durations), 2) if durations else 0.0

        # Approval turnaround (hours)
        decided = Approval.search([
            ('state', 'in', ['approved', 'rejected']),
            ('date_decided', '!=', False),
            ('date_requested', '!=', False),
        ])
        approval_hours = []
        for rec in decided:
            approval_hours.append((rec.date_decided - rec.date_requested).total_seconds() / 3600.0)
        avg_approval_hours = round(sum(approval_hours) / len(approval_hours), 2) if approval_hours else 0.0

        # Task turnaround (use write_date when completed — no dedicated date_done field)
        done_tasks = Task.search([('state', '=', 'done')])
        task_hours = []
        for rec in done_tasks:
            start = rec.create_date
            end = rec.write_date
            if start and end and end >= start:
                task_hours.append((end - start).total_seconds() / 3600.0)
        avg_task_hours = round(sum(task_hours) / len(task_hours), 2) if task_hours else 0.0

        # SLA: tasks past deadline still open/in progress/escalated
        now = fields.Datetime.now()
        sla_breached = Task.search_count([
            ('date_deadline', '!=', False),
            ('date_deadline', '<', now),
            ('state', 'in', ['open', 'in_progress', 'escalated']),
        ])
        sla_total = Task.search_count([('date_deadline', '!=', False)])

        by_state = Execution.read_group(domain, ['state'], ['state'], lazy=False)
        by_module = Execution.read_group(
            domain + [('source_module', '!=', False)],
            ['source_module'],
            ['source_module'],
            lazy=False,
        )

        # Bottlenecks: nodes with most waiting steps
        Step = self.env['workflow.engine.execution.step']
        waiting_steps = Step.read_group(
            [('state', 'in', ['waiting', 'running', 'failed'])],
            ['node_id'],
            ['node_id'],
            lazy=False,
        )
        bottlenecks = []
        for row in waiting_steps[:10]:
            if not row.get('node_id'):
                continue
            bottlenecks.append({
                'node_id': row['node_id'][0],
                'node_name': row['node_id'][1],
                'count': row['__count'],
            })

        return {
            'summary': {
                'total_executions': total,
                'completed': completed,
                'failed': failed,
                'running': running,
                'completion_rate': round((completed / total) * 100, 1) if total else 0.0,
                'failure_rate': round((failed / total) * 100, 1) if total else 0.0,
                'avg_duration_hours': avg_duration_hours,
                'avg_approval_hours': avg_approval_hours,
                'avg_task_hours': avg_task_hours,
                'escalation_count': Escalation.search_count([]),
                'sla_breached': sla_breached,
                'sla_total': sla_total,
            },
            'by_state': [
                {'state': row['state'], 'count': row['__count']}
                for row in by_state if row.get('state')
            ],
            'by_module': [
                {'module': row['source_module'], 'count': row['__count']}
                for row in by_module if row.get('source_module')
            ],
            'bottlenecks': bottlenecks,
            'definitions': self.env['workflow.engine.definition'].search_read(
                [], ['id', 'name', 'code', 'state'], order='name', limit=200,
            ),
            'user_performance': self._task_user_performance(),
            'trend': self.get_dashboard_data().get('trend') or [],
            'comparison': {
                'completed': completed,
                'failed': failed,
                'running': running,
            },
        }

    def _task_user_performance(self):
        Task = self.env['workflow.engine.task']
        rows = Task.read_group(
            [('user_id', '!=', False)],
            ['user_id'],
            ['user_id'],
            lazy=False,
        )
        result = []
        for row in rows[:20]:
            if not row.get('user_id'):
                continue
            uid = row['user_id'][0]
            done = Task.search_count([('user_id', '=', uid), ('state', '=', 'done')])
            open_count = Task.search_count([
                ('user_id', '=', uid),
                ('state', 'in', ['open', 'in_progress', 'escalated']),
            ])
            result.append({
                'user_id': uid,
                'user_name': row['user_id'][1],
                'total': row['__count'],
                'done': done,
                'open': open_count,
            })
        return result

    # ------------------------------------------------------------------
    # Builder
    # ------------------------------------------------------------------
    @api.model
    def list_workflows(self):
        return self.env['workflow.engine.definition'].search_read(
            [],
            ['id', 'name', 'code', 'state', 'active_version_id', 'version_count', 'description'],
            order='name',
        )

    @api.model
    def create_workflow(self, vals):
        if not self.env.user.has_group('workflow_engine.group_we_manager'):
            raise AccessError('Only Managers/Administrators can create workflows.')
        name = (vals or {}).get('name') or 'New Workflow'
        code = (vals or {}).get('code') or ('WF_%s' % fields.Datetime.now().strftime('%Y%m%d%H%M%S'))
        definition = self.env['workflow.engine.definition'].create({
            'name': name,
            'code': code,
            'description': (vals or {}).get('description') or False,
            'state': 'draft',
        })
        version = self.env['workflow.engine.version'].create({
            'definition_id': definition.id,
            'version': 1,
            'state': 'draft',
        })
        # Default start + end nodes so the canvas is usable
        start = self.env['workflow.engine.node'].create({
            'name': 'Start',
            'technical_key': 'start',
            'version_id': version.id,
            'node_type': 'start',
            'pos_x': 80,
            'pos_y': 160,
            'sequence': 1,
        })
        end = self.env['workflow.engine.node'].create({
            'name': 'End',
            'technical_key': 'end',
            'version_id': version.id,
            'node_type': 'end',
            'pos_x': 420,
            'pos_y': 160,
            'sequence': 99,
        })
        self.env['workflow.engine.edge'].create({
            'name': 'Default',
            'version_id': version.id,
            'source_node_id': start.id,
            'target_node_id': end.id,
            'sequence': 10,
            'is_default': True,
        })
        return self.load_builder_graph(definition.id, version.id)

    @api.model
    def load_builder_graph(self, definition_id, version_id=None):
        definition = self.env['workflow.engine.definition'].browse(int(definition_id))
        if not definition.exists():
            raise UserError('Workflow definition not found.')
        version = False
        if version_id:
            version = self.env['workflow.engine.version'].browse(int(version_id))
        if not version or not version.exists() or version.definition_id != definition:
            version = definition.active_version_id or definition.version_ids[:1]
        if not version:
            return {
                'definition': self._serialize_definition(definition),
                'version': False,
                'nodes': [],
                'edges': [],
                'triggers': [],
                'readonly': True,
                'hierarchies': self._hierarchy_options(),
                'rules': self._rule_options(definition.id),
            }
        nodes = self.env['workflow.engine.node'].search_read(
            [('version_id', '=', version.id)],
            [
                'id', 'name', 'technical_key', 'node_type', 'sequence',
                'pos_x', 'pos_y', 'config_json', 'input_mapping', 'output_mapping',
                'hierarchy_id', 'rule_id', 'mail_template_id',
            ],
            order='sequence, id',
        )
        edges = self.env['workflow.engine.edge'].search_read(
            [('version_id', '=', version.id)],
            [
                'id', 'name', 'source_node_id', 'target_node_id', 'sequence',
                'is_default', 'condition_json', 'rule_id',
            ],
            order='sequence, id',
        )
        triggers = self.env['workflow.engine.trigger'].search_read(
            [('version_id', '=', version.id)],
            [
                'id', 'name', 'source_module', 'source_model', 'event_code',
                'domain_json', 'active', 'description',
            ],
            order='id',
        )
        versions = definition.version_ids.read(['id', 'version', 'state', 'name', 'validation_ok', 'validation_message'])
        return {
            'definition': self._serialize_definition(definition),
            'version': {
                'id': version.id,
                'version': version.version,
                'state': version.state,
                'name': version.name,
                'validation_ok': version.validation_ok,
                'validation_message': version.validation_message or '',
            },
            'versions': versions,
            'nodes': nodes,
            'edges': edges,
            'triggers': triggers,
            'readonly': version.state != 'draft',
            'hierarchies': self._hierarchy_options(),
            'rules': self._rule_options(definition.id),
        }

    def _serialize_definition(self, definition):
        return {
            'id': definition.id,
            'name': definition.name,
            'code': definition.code,
            'state': definition.state,
            'description': definition.description or '',
            'active_version_id': definition.active_version_id.id,
        }

    def _hierarchy_options(self):
        return self.env['workflow.engine.approval.hierarchy'].search_read(
            [('active', '=', True)],
            ['id', 'name'],
            order='priority, name',
            limit=200,
        )

    def _rule_options(self, definition_id=None):
        domain = [('active', '=', True)]
        if definition_id:
            domain = ['|', ('definition_id', '=', definition_id), ('definition_id', '=', False)] + domain
        return self.env['workflow.engine.condition.rule'].search_read(
            domain,
            ['id', 'name', 'rule_type'],
            order='priority, name',
            limit=200,
        )

    @api.model
    def save_builder_graph(self, definition_id, version_id, payload):
        """Replace draft graph (nodes/edges/triggers) for a version.

        payload: {definition?: {}, nodes: [], edges: [], triggers: []}
        Nodes/edges use client_key for new records; edges reference source/target by id or client_key.
        """
        if not self.env.user.has_group('workflow_engine.group_we_manager'):
            raise AccessError('Only Managers/Administrators can edit workflows.')
        definition = self.env['workflow.engine.definition'].browse(int(definition_id))
        version = self.env['workflow.engine.version'].browse(int(version_id))
        if not definition.exists() or not version.exists() or version.definition_id != definition:
            raise UserError('Invalid workflow version.')
        version._assert_draft()

        payload = payload or {}
        def_vals = payload.get('definition') or {}
        write_def = {}
        if 'name' in def_vals and def_vals['name']:
            write_def['name'] = def_vals['name']
        if 'description' in def_vals:
            write_def['description'] = def_vals['description'] or False
        if write_def:
            definition.write(write_def)

        Node = self.env['workflow.engine.node']
        Edge = self.env['workflow.engine.edge']
        Trigger = self.env['workflow.engine.trigger']

        # Remove existing graph then recreate (draft only)
        Edge.search([('version_id', '=', version.id)]).unlink()
        Node.search([('version_id', '=', version.id)]).unlink()
        Trigger.search([('version_id', '=', version.id)]).unlink()

        key_to_id = {}
        for idx, node in enumerate(payload.get('nodes') or []):
            technical_key = (node.get('technical_key') or 'node_%s' % (idx + 1)).strip()
            created = Node.create({
                'name': node.get('name') or technical_key,
                'technical_key': technical_key,
                'version_id': version.id,
                'node_type': node.get('node_type') or 'action',
                'sequence': node.get('sequence') or ((idx + 1) * 10),
                'pos_x': float(node.get('pos_x') or 80),
                'pos_y': float(node.get('pos_y') or 80),
                'config_json': node.get('config_json') or False,
                'input_mapping': node.get('input_mapping') or False,
                'output_mapping': node.get('output_mapping') or False,
                'hierarchy_id': node.get('hierarchy_id') or False,
                'rule_id': node.get('rule_id') or False,
                'mail_template_id': node.get('mail_template_id') or False,
            })
            client_key = node.get('client_key') or technical_key
            key_to_id[str(client_key)] = created.id
            if node.get('id'):
                key_to_id[str(node['id'])] = created.id

        for idx, edge in enumerate(payload.get('edges') or []):
            source_ref = edge.get('source_ref') or edge.get('source_node_id')
            target_ref = edge.get('target_ref') or edge.get('target_node_id')
            if isinstance(source_ref, (list, tuple)):
                source_ref = source_ref[0]
            if isinstance(target_ref, (list, tuple)):
                target_ref = target_ref[0]
            source_id = key_to_id.get(str(source_ref))
            target_id = key_to_id.get(str(target_ref))
            if not source_id or not target_id:
                raise ValidationError('Edge references missing nodes. Save nodes before connecting them.')
            Edge.create({
                'name': edge.get('name') or False,
                'version_id': version.id,
                'source_node_id': source_id,
                'target_node_id': target_id,
                'sequence': edge.get('sequence') or ((idx + 1) * 10),
                'is_default': bool(edge.get('is_default')),
                'condition_json': edge.get('condition_json') or False,
                'rule_id': edge.get('rule_id') or False,
            })

        for trigger in payload.get('triggers') or []:
            Trigger.create({
                'name': trigger.get('name') or trigger.get('event_code') or 'Trigger',
                'version_id': version.id,
                'source_module': trigger.get('source_module') or 'workflow_engine',
                'source_model': trigger.get('source_model') or 'workflow.engine.definition',
                'event_code': trigger.get('event_code') or 'manual',
                'domain_json': trigger.get('domain_json') or False,
                'active': trigger.get('active', True),
                'description': trigger.get('description') or False,
            })

        return self.load_builder_graph(definition.id, version.id)

    @api.model
    def validate_version(self, version_id):
        version = self.env['workflow.engine.version'].browse(int(version_id))
        if not version.exists():
            raise UserError('Version not found.')
        return version.action_validate()

    @api.model
    def publish_version(self, version_id):
        if not self.env.user.has_group('workflow_engine.group_we_admin'):
            raise AccessError('Only Workflow Engine Administrators can publish workflows.')
        version = self.env['workflow.engine.version'].browse(int(version_id))
        result = version.action_validate()
        blocking = list(result.get('errors') or [])
        blocking += [
            msg for msg in (result.get('warnings') or [])
            if 'trigger' in (msg or '').lower()
        ]
        if blocking:
            raise UserError('\n'.join(blocking) or result.get('message') or 'Validation failed.')
        version.action_publish()
        return self.load_builder_graph(version.definition_id.id, version.id)

    @api.model
    def activate_version(self, version_id):
        version = self.env['workflow.engine.version'].browse(int(version_id))
        version.action_activate()
        return self.load_builder_graph(version.definition_id.id, version.id)

    @api.model
    def deactivate_version(self, version_id):
        version = self.env['workflow.engine.version'].browse(int(version_id))
        version.action_deactivate()
        return self.load_builder_graph(version.definition_id.id, version.id)

    @api.model
    def create_draft_from_version(self, version_id):
        """Copy an immutable version into a new draft for editing."""
        if not self.env.user.has_group('workflow_engine.group_we_manager'):
            raise AccessError('Only Managers/Administrators can create a new draft version.')
        source = self.env['workflow.engine.version'].browse(int(version_id))
        if not source.exists():
            raise UserError('Version not found.')
        definition = source.definition_id
        if definition.version_ids.filtered(lambda v: v.state == 'draft'):
            raise UserError('A draft version already exists for this workflow.')
        next_number = max(definition.version_ids.mapped('version') or [0]) + 1
        draft = self.env['workflow.engine.version'].create({
            'definition_id': definition.id,
            'version': next_number,
            'state': 'draft',
        })
        node_map = {}
        for node in source.node_ids:
            copy = self.env['workflow.engine.node'].create({
                'name': node.name,
                'technical_key': node.technical_key,
                'version_id': draft.id,
                'node_type': node.node_type,
                'sequence': node.sequence,
                'pos_x': node.pos_x,
                'pos_y': node.pos_y,
                'config_json': node.config_json,
                'input_mapping': node.input_mapping,
                'output_mapping': node.output_mapping,
                'hierarchy_id': node.hierarchy_id.id,
                'rule_id': node.rule_id.id,
                'mail_template_id': node.mail_template_id.id,
            })
            node_map[node.id] = copy.id
        for edge in source.edge_ids:
            self.env['workflow.engine.edge'].create({
                'name': edge.name,
                'version_id': draft.id,
                'source_node_id': node_map[edge.source_node_id.id],
                'target_node_id': node_map[edge.target_node_id.id],
                'sequence': edge.sequence,
                'is_default': edge.is_default,
                'condition_json': edge.condition_json,
                'rule_id': edge.rule_id.id,
            })
        for trigger in source.trigger_ids:
            self.env['workflow.engine.trigger'].create({
                'name': trigger.name,
                'version_id': draft.id,
                'source_module': trigger.source_module,
                'source_model': trigger.source_model,
                'event_code': trigger.event_code,
                'domain_json': trigger.domain_json,
                'active': trigger.active,
                'description': trigger.description,
            })
        return self.load_builder_graph(definition.id, draft.id)

    @api.model
    def test_run_version(self, version_id, payload=None):
        """Start a test execution against the bound version if it is active."""
        if not self.env.user.has_group('workflow_engine.group_we_manager'):
            raise AccessError('Only Managers/Administrators can run test executions.')
        version = self.env['workflow.engine.version'].browse(int(version_id))
        if not version.exists():
            raise UserError('Version not found.')
        if version.state != 'active':
            raise UserError('Activate the workflow version before running a test execution.')
        trigger = version.trigger_ids.filtered('active')[:1]
        if not trigger:
            raise UserError('Configure at least one active trigger before testing.')
        result = self.env['workflow.engine.execution'].trigger_workflow(
            trigger.source_module,
            trigger.source_model,
            trigger.event_code,
            record=None,
            payload=payload or {'we_test': True},
        )
        executions = result.get('executions') if isinstance(result, dict) else result
        return {
            'ok': True,
            'execution_ids': executions.ids if hasattr(executions, 'ids') else [],
            'message': 'Test execution started.',
        }

    # ------------------------------------------------------------------
    # Templates
    # ------------------------------------------------------------------
    @api.model
    def duplicate_template(self, template_id):
        template = self.env['workflow.engine.template'].browse(int(template_id))
        if not template.exists():
            raise UserError('Template not found.')
        return template.action_duplicate().id

    @api.model
    def create_workflow_from_template(self, template_id, vals=None):
        template = self.env['workflow.engine.template'].browse(int(template_id))
        if not template.exists():
            raise UserError('Template not found.')
        return template.action_create_workflow(vals or {})

    @api.model
    def preview_template(self, template_id):
        template = self.env['workflow.engine.template'].browse(int(template_id))
        if not template.exists():
            raise UserError('Template not found.')
        payload = template.payload_json if isinstance(template.payload_json, dict) else {}
        return {
            'id': template.id,
            'name': template.name,
            'description': template.description or '',
            'category': template.category or '',
            'version': template.version or '',
            'required_modules': template.required_modules or '',
            'usage_count': template.usage_count,
            'state': template.state,
            'has_graph': bool(payload.get('graph') or payload.get('nodes')),
        }

    @api.model
    def list_templates(self, domain=None, offset=0, limit=200):
        return self._search_read(
            'workflow.engine.template',
            domain,
            [
                'id', 'name', 'description', 'category', 'state', 'version',
                'required_modules', 'usage_count', 'owner_id', 'active',
            ],
            offset=offset,
            limit=limit,
            order='name',
        )

    @api.model
    def save_template(self, template_id, vals):
        if not self._is_manager():
            raise AccessError('Only Managers/Administrators can configure templates.')
        vals = vals or {}
        allowed = ('name', 'description', 'category', 'version', 'required_modules', 'payload_json')
        clean = {key: vals[key] for key in allowed if key in vals}
        Template = self.env['workflow.engine.template']
        if template_id:
            rec = self._browse_or_raise('workflow.engine.template', template_id, 'Template')
            rec.write(clean)
            return rec.id
        clean.setdefault('state', 'draft')
        return Template.create(clean).id

    @api.model
    def activate_template(self, template_id):
        rec = self._browse_or_raise('workflow.engine.template', template_id, 'Template')
        rec.action_activate()
        return True

    @api.model
    def deactivate_template(self, template_id):
        rec = self._browse_or_raise('workflow.engine.template', template_id, 'Template')
        rec.action_deactivate()
        return True

    # ------------------------------------------------------------------
    # Approval hierarchy / condition rules
    # ------------------------------------------------------------------
    @api.model
    def get_approval_setup(self):
        return {
            'hierarchies': self.env['workflow.engine.approval.hierarchy'].search_read(
                [],
                [
                    'id', 'name', 'description', 'priority', 'source_module',
                    'active', 'date_from', 'date_to',
                ],
                order='priority, name',
                limit=500,
            ),
            'rules': self.env['workflow.engine.condition.rule'].search_read(
                [],
                ['id', 'name', 'rule_type', 'criterion', 'operator', 'value', 'priority', 'active'],
                order='priority, name',
                limit=500,
            ),
            'users': self.env['res.users'].search_read(
                [('active', '=', True), ('share', '=', False)],
                ['id', 'name'],
                order='name',
                limit=300,
            ),
            'groups': self.env['res.groups'].search_read(
                [('share', '=', False)],
                ['id', 'full_name', 'name'],
                order='full_name',
                limit=200,
            ),
        }

    @api.model
    def get_hierarchy_detail(self, hierarchy_id):
        hierarchy = self._browse_or_raise(
            'workflow.engine.approval.hierarchy', hierarchy_id, 'Hierarchy',
        )
        record = hierarchy.read([
            'id', 'name', 'description', 'priority', 'source_module',
            'active', 'date_from', 'date_to',
        ])[0]
        levels = []
        for level in hierarchy.level_ids.sorted(lambda rec: (rec.sequence, rec.id)):
            user_ids = []
            group_ids = []
            fallback_user_id = False
            for approver in level.approver_ids.sorted(lambda rec: (rec.sequence, rec.id)):
                if not approver.active:
                    continue
                if approver.is_fallback and approver.user_id:
                    fallback_user_id = approver.user_id.id
                    continue
                if approver.user_id:
                    user_ids.append(approver.user_id.id)
                elif approver.group_id:
                    group_ids.append(approver.group_id.id)
            levels.append({
                'id': level.id,
                'name': level.name or '',
                'sequence': level.sequence,
                'mode': level.mode,
                'threshold': level.threshold,
                'approver_user_ids': user_ids,
                'approver_group_ids': group_ids,
                'fallback_user_id': fallback_user_id,
            })
        return {'record': record, 'levels': levels}

    @api.model
    def save_hierarchy(self, payload):
        if not self._is_manager():
            raise AccessError('Only Managers/Administrators can configure approval hierarchies.')
        payload = payload or {}
        vals = {
            'name': payload.get('name'),
            'description': payload.get('description') or False,
            'priority': payload.get('priority') or 10,
            'source_module': payload.get('source_module') or False,
            'active': payload.get('active', True),
            'date_from': payload.get('date_from') or False,
            'date_to': payload.get('date_to') or False,
        }
        Hierarchy = self.env['workflow.engine.approval.hierarchy']
        Level = self.env['workflow.engine.approval.level']
        Approver = self.env['workflow.engine.approver']
        hierarchy_id = payload.get('id')
        if hierarchy_id:
            hierarchy = self._browse_or_raise(
                'workflow.engine.approval.hierarchy', hierarchy_id, 'Hierarchy',
            )
            hierarchy.write(vals)
            hierarchy.level_ids.unlink()
        else:
            hierarchy = Hierarchy.create(vals)
        for level in payload.get('levels') or []:
            created_level = Level.create({
                'hierarchy_id': hierarchy.id,
                'name': level.get('name') or False,
                'sequence': level.get('sequence') or 10,
                'mode': level.get('mode') or 'sequential',
                'threshold': level.get('threshold') or 1,
            })
            seq = 10
            for user_id in level.get('approver_user_ids') or []:
                Approver.create({
                    'level_id': created_level.id,
                    'user_id': int(user_id),
                    'sequence': seq,
                    'is_fallback': False,
                })
                seq += 10
            for group_id in level.get('approver_group_ids') or []:
                Approver.create({
                    'level_id': created_level.id,
                    'group_id': int(group_id),
                    'sequence': seq,
                    'is_fallback': False,
                })
                seq += 10
            if level.get('fallback_user_id'):
                Approver.create({
                    'level_id': created_level.id,
                    'user_id': int(level['fallback_user_id']),
                    'sequence': seq,
                    'is_fallback': True,
                })
        return hierarchy.id

    @api.model
    def save_rule(self, rule_id, vals):
        if not self._is_manager():
            raise AccessError('Only Managers/Administrators can configure rules.')
        vals = vals or {}
        allowed = ('name', 'rule_type', 'criterion', 'operator', 'value', 'priority', 'active')
        clean = {key: vals[key] for key in allowed if key in vals}
        Rule = self.env['workflow.engine.condition.rule']
        if rule_id:
            rec = self._browse_or_raise('workflow.engine.condition.rule', rule_id, 'Rule')
            rec.write(clean)
            return rec.id
        return Rule.create(clean).id

    @api.model
    def toggle_hierarchy_active(self, hierarchy_id):
        hierarchy = self._browse_or_raise(
            'workflow.engine.approval.hierarchy', hierarchy_id, 'Hierarchy',
        )
        if hierarchy.active:
            hierarchy.action_deactivate()
        else:
            hierarchy.action_activate()
        return hierarchy.active

    # ------------------------------------------------------------------
    # Operational lists (paginated ORM)
    # ------------------------------------------------------------------
    def _search_read(self, model, domain, fields, offset=0, limit=100, order='id desc'):
        domain = list(domain or [])
        limit = min(max(int(limit or 100), 1), 200)
        offset = max(int(offset or 0), 0)
        Model = self.env[model]
        return {
            'total': Model.search_count(domain),
            'records': Model.search_read(
                domain, fields, offset=offset, limit=limit, order=order,
            ),
        }

    def _is_manager(self):
        return self.env.user.has_group('workflow_engine.group_we_manager')

    @api.model
    def search_executions(self, domain=None, offset=0, limit=100):
        return self._search_read(
            'workflow.engine.execution',
            domain,
            [
                'id', 'name', 'state', 'definition_id', 'version_id',
                'source_module', 'event_code', 'date_start', 'date_end',
                'error_message', 'current_node_id',
            ],
            offset=offset,
            limit=limit,
        )

    @api.model
    def search_tasks(self, domain=None, offset=0, limit=100):
        domain = list(domain or [])
        if not self._is_manager():
            domain = domain + [
                '|',
                ('user_id', '=', self.env.uid),
                ('group_id', 'in', self.env.user.groups_id.ids),
            ]
        return self._search_read(
            'workflow.engine.task',
            domain,
            [
                'id', 'name', 'state', 'user_id', 'priority', 'date_deadline',
                'execution_id', 'sla_deadline',
            ],
            offset=offset,
            limit=limit,
            order='date_deadline, id desc',
        )

    @api.model
    def search_escalations(self, domain=None, offset=0, limit=100):
        return self._search_read(
            'workflow.engine.escalation.event',
            domain,
            [
                'id', 'name', 'level', 'state', 'date_triggered',
                'task_id', 'execution_id', 'automatic', 'note',
            ],
            offset=offset,
            limit=limit,
        )

    @api.model
    def search_approvals(self, domain=None, offset=0, limit=100):
        domain = list(domain or [])
        if not self._is_manager():
            domain = domain + [
                '|',
                ('user_id', '=', self.env.uid),
                ('group_id', 'in', self.env.user.groups_id.ids),
            ]
        return self._search_read(
            'workflow.engine.approval.request',
            domain,
            [
                'id', 'name', 'state', 'user_id', 'level_id', 'execution_id',
                'date_requested', 'date_decided', 'comment', 'decided_by',
            ],
            offset=offset,
            limit=limit,
        )

    @api.model
    def search_notifications(self, domain=None, offset=0, limit=100):
        return self._search_read(
            'workflow.engine.notification.log',
            domain,
            [
                'id', 'name', 'channel', 'state', 'user_id', 'execution_id',
                'date_sent', 'error_message', 'reminder', 'escalation', 'create_date',
            ],
            offset=offset,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Operational actions (delegate to models → Phase 4 services)
    # ------------------------------------------------------------------
    def _browse_or_raise(self, model, rec_id, label):
        record = self.env[model].browse(int(rec_id))
        if not record.exists():
            raise UserError('%s not found.' % label)
        return record

    @api.model
    def assign_task(self, task_id, user_id):
        task = self._browse_or_raise('workflow.engine.task', task_id, 'Task')
        method = 'action_reassign' if task.user_id else 'action_assign'
        getattr(task, method)(user_id=int(user_id))
        return True

    @api.model
    def start_task(self, task_id):
        task = self._browse_or_raise('workflow.engine.task', task_id, 'Task')
        task.action_start()
        return True

    @api.model
    def complete_task(self, task_id):
        task = self._browse_or_raise('workflow.engine.task', task_id, 'Task')
        task.action_complete()
        return True

    @api.model
    def escalate_task(self, task_id):
        task = self._browse_or_raise('workflow.engine.task', task_id, 'Task')
        task.action_escalate()
        return True

    @api.model
    def get_execution_detail(self, execution_id):
        execution = self._browse_or_raise('workflow.engine.execution', execution_id, 'Execution')
        record = execution.read([
            'id', 'name', 'state', 'definition_id', 'version_id',
            'source_module', 'event_code', 'date_start', 'date_end',
            'error_message', 'current_node_id',
        ])[0]
        steps = self.env['workflow.engine.execution.step'].search_read(
            [('execution_id', '=', execution.id)],
            ['id', 'name', 'state', 'sequence', 'date_start', 'date_end', 'error_message', 'retry_count', 'node_id'],
            order='sequence, id',
        )
        escalations = self.env['workflow.engine.escalation.event'].search_read(
            [('execution_id', '=', execution.id)],
            ['id', 'name', 'level', 'state', 'date_triggered', 'task_id', 'automatic', 'note'],
            order='id desc',
            limit=50,
        )
        return {'record': record, 'steps': steps, 'escalations': escalations}

    @api.model
    def get_task_detail(self, task_id):
        task = self._browse_or_raise('workflow.engine.task', task_id, 'Task')
        record = task.read([
            'id', 'name', 'state', 'user_id', 'priority', 'date_deadline',
            'execution_id', 'sla_deadline',
        ])[0]
        domain = [('task_id', '=', task.id)]
        if task.execution_id:
            domain = ['|', ('task_id', '=', task.id), ('execution_id', '=', task.execution_id.id)]
        escalations = self.env['workflow.engine.escalation.event'].search_read(
            domain,
            ['id', 'name', 'level', 'state', 'date_triggered', 'automatic', 'note'],
            order='id desc',
            limit=50,
        )
        return {'record': record, 'escalations': escalations}

    @api.model
    def retry_execution(self, execution_id):
        execution = self._browse_or_raise('workflow.engine.execution', execution_id, 'Execution')
        version_id = execution.version_id.id
        execution.action_retry()
        execution.invalidate_recordset()
        return {
            'ok': True,
            'version_id': execution.version_id.id,
            'bound_version_id': version_id,
            'state': execution.state,
        }

    @api.model
    def approve_request(self, request_id, comment=None):
        request = self._browse_or_raise('workflow.engine.approval.request', request_id, 'Approval request')
        request.action_approve(comment=comment)
        return True

    @api.model
    def reject_request(self, request_id, comment=None):
        request = self._browse_or_raise('workflow.engine.approval.request', request_id, 'Approval request')
        request.action_reject(comment=comment)
        return True
