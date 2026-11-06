# -*- coding: utf-8 -*-
from . import test_structure

try:
    import odoo  # noqa: F401
    from . import test_foundation
    from . import test_domain
    from . import test_ui
except ImportError:
    pass
