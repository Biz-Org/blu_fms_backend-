# -*- coding: utf-8 -*-
from . import test_structure
from . import test_ui_navigation
from . import test_domain_static

try:
    import odoo  # noqa: F401
    from . import test_odoo_domain
    from . import test_odoo_services
    from . import test_odoo_ui
    from . import test_odoo_integration
    from . import test_odoo_uat
except ImportError:
    pass
