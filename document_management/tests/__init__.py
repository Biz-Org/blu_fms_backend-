# -*- coding: utf-8 -*-
from . import test_structure
from . import test_owl_ui
from . import test_visual_ui

try:
    import odoo  # noqa: F401
    from . import test_models
    from . import test_security
    from . import test_services
    from . import test_ui_integration
    from . import test_core_domain
    from . import test_workflows
    from . import test_phase6
except ImportError:
    pass
