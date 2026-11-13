# Part of Preventive Maintenance Management.

"""Central PM role helpers for backend enforcement."""

GROUP_PM_ADMIN = "preventive_maintenance.group_pm_admin"
GROUP_PM_MANAGER = "preventive_maintenance.group_pm_maintenance_manager"
GROUP_PM_MANAGER_ALIAS = "preventive_maintenance.group_pm_manager"
GROUP_PM_TECHNICIAN = "preventive_maintenance.group_pm_technician"


def _has_manager_group(env):
    return env.user.has_group(GROUP_PM_MANAGER) or env.user.has_group(GROUP_PM_MANAGER_ALIAS)


def pm_is_admin(env):
    return env.user.has_group(GROUP_PM_ADMIN)


def pm_is_manager(env):
    return _has_manager_group(env) or pm_is_admin(env)


def pm_is_technician(env):
    return env.user.has_group(GROUP_PM_TECHNICIAN)


def pm_is_technician_only(env):
    """Technician without manager privileges (excludes PM Admin who implies manager)."""
    return pm_is_technician(env) and not _has_manager_group(env)


def pm_is_any_pm_user(env):
    return pm_is_manager(env) or pm_is_technician(env)
