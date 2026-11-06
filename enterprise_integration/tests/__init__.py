# -*- coding: utf-8 -*-
from . import test_structure
from . import test_domain_static
from . import test_services_static
from . import test_ui_navigation
from . import test_workflows_e2e
from . import test_phase7_qa

try:
    import odoo  # noqa: F401
    from . import odoo_test_models
    from . import odoo_test_security
    from . import odoo_test_services
    from . import odoo_test_workflows
except ImportError:
    pass
