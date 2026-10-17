# -*- coding: utf-8 -*-

import logging

from . import maintenance
from . import maintenance_domain
from . import maintenance_request_workflow
from . import maintenance_demo_cleanup
from . import maintenance_equipment_import
from . import plant_app_dashboard
from . import equipment_overview_dashboard
from . import rul_tobm_dashboard
from . import res_config_settings

_logger = logging.getLogger(__name__)
_logger.info('maintenance module: rul_tobm_dashboard loaded')
