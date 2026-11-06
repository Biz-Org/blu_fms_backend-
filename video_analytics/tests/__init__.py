# -*- coding: utf-8 -*-
from . import test_structure
try:
    from . import test_models
    from . import test_security
    from . import test_services
    from . import test_ui_integration
except ImportError:
    pass
