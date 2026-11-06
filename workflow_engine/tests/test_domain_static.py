# -*- coding: utf-8 -*-
"""Static Phase 3 domain checks (no Odoo runtime required)."""
import re
import unittest
from pathlib import Path

ADDON_ROOT = Path(__file__).resolve().parents[1]
MODELS = ADDON_ROOT / 'models'


def _read(name):
    return (MODELS / name).read_text(encoding='utf-8')


class TestDomainStatic(unittest.TestCase):
    def test_model_names(self):
        expected = {
            'workflow_definition.py': 'workflow.engine.definition',
            'workflow_version.py': 'workflow.engine.version',
            'workflow_node.py': 'workflow.engine.node',
            'workflow_edge.py': 'workflow.engine.edge',
            'workflow_trigger.py': 'workflow.engine.trigger',
            'workflow_template.py': 'workflow.engine.template',
            'approval_hierarchy.py': 'workflow.engine.approval.hierarchy',
            'approval_level.py': 'workflow.engine.approval.level',
            'approver.py': 'workflow.engine.approver',
            'conditional_rule.py': 'workflow.engine.condition.rule',
            'workflow_execution.py': 'workflow.engine.execution',
            'execution_step.py': 'workflow.engine.execution.step',
            'workflow_task.py': 'workflow.engine.task',
            'approval_request.py': 'workflow.engine.approval.request',
            'escalation_rule.py': 'workflow.engine.escalation.rule',
            'escalation_event.py': 'workflow.engine.escalation.event',
            'notification_log.py': 'workflow.engine.notification.log',
            'audit_event.py': 'workflow.engine.audit.event',
        }
        for filename, model in expected.items():
            self.assertIn("_name = '%s'" % model, _read(filename))

    def test_definition_and_version_states(self):
        definition = _read('workflow_definition.py')
        for state in ('draft', 'published', 'active', 'inactive', 'archived'):
            self.assertIn("'%s'" % state, definition)
        self.assertNotIn("'cancelled'", definition)
        version = _read('workflow_version.py')
        for state in ('draft', 'published', 'active', 'inactive', 'superseded'):
            self.assertIn("'%s'" % state, version)

    def test_node_types(self):
        node = _read('workflow_node.py')
        for ntype in ('start', 'end', 'action', 'approval', 'task', 'notification', 'conditional'):
            self.assertIn("'%s'" % ntype, node)

    def test_execution_and_task_states(self):
        execution = _read('workflow_execution.py')
        for state in (
            'running', 'waiting_approval', 'waiting_task', 'escalated', 'completed', 'failed',
        ):
            self.assertIn("'%s'" % state, execution)
        self.assertNotIn("'cancelled'", execution)
        task = _read('workflow_task.py')
        for state in ('open', 'in_progress', 'done', 'escalated'):
            self.assertIn("'%s'" % state, task)

    def test_rule_types_and_operators(self):
        rule = _read('conditional_rule.py')
        for rtype in ('approval_routing', 'assignment', 'branch'):
            self.assertIn("'%s'" % rtype, rule)
        for op in ("'='", "'!='", "'in'", "'<'", "'<='", "'>'", "'>='"):
            self.assertIn(op, rule)
        for criterion in ('department', 'role', 'value', 'property', 'site', 'module'):
            self.assertIn("'%s'" % criterion, rule)

    def test_approval_modes(self):
        level = _read('approval_level.py')
        self.assertIn("'sequential'", level)
        self.assertIn("'parallel'", level)

    def test_no_trigger_or_escalation_service(self):
        services_init = (ADDON_ROOT / 'services' / '__init__.py').read_text(encoding='utf-8')
        for name in (
            'trigger_service', 'execution_service', 'rule_service', 'approval_service',
            'task_service', 'escalation_service', 'notification_service', 'audit_service',
        ):
            self.assertIn('from . import %s' % name, services_init)

    def test_no_property_models(self):
        for path in MODELS.glob('*.py'):
            text = path.read_text(encoding='utf-8')
            self.assertIsNone(re.search(r"_name = 'fms\.(property|site|building)'", text))
