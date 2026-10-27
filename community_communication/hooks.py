# -*- coding: utf-8 -*-

from odoo import Command


AUDIENCE_TAIL = (
    "'|', '|', "
    "('audience_type', '=', 'community'), "
    "'&', ('audience_type', '=', 'buildings'), ('building_ids', 'in', user.cc_building_ids.ids), "
    "'&', ('audience_type', '=', 'groups'), ('audience_group_ids', 'in', user.cc_member_group_ids.ids)"
)

ANNOUNCEMENT_AUDIENCE_TAIL = (
    "'|', '|', '|', '|', "
    "('audience_type', '=', 'community'), "
    "'&', ('audience_type', '=', 'buildings'), ('building_ids', 'in', user.cc_building_ids.ids), "
    "'&', ('audience_type', '=', 'groups'), ('audience_group_ids', 'in', user.cc_member_group_ids.ids), "
    "'&', ('audience_type', '=', 'residents'), "
    "('audience_resident_ids', 'in', user.cc_resident_ids.ids), "
    "'&', ('audience_type', '=', 'users'), "
    "('audience_user_ids', 'in', [user.id])"
)


def _audience_domain(state_term, audience_tail=AUDIENCE_TAIL):
    return (
        "['&', '&', "
        "('community_id', 'in', user.cc_resident_ids.community_id.ids), "
        f"{state_term}, {audience_tail}]"
    )


RESIDENT_RULE_DOMAINS = {
    "announcement_resident_rule": _audience_domain(
        "('state', '=', 'published')",
        ANNOUNCEMENT_AUDIENCE_TAIL,
    ),
    "notice_resident_rule": _audience_domain("('state', '=', 'published')"),
    "poll_resident_rule": _audience_domain("('state', 'in', ['active', 'closed'])"),
    "event_resident_rule": _audience_domain("('state', 'in', ['published', 'completed', 'cancelled'])"),
    "report_resident_rule": "[('reporter_id', '=', user.id)]",
}


def post_init_hook(env):
    """Keep residents on the shared Community OWL app without Internal User rights."""
    _sync_resident_portal_access(env)
    _sync_resident_rule_domains(env)


def _sync_resident_portal_access(env):
    resident_group = env.ref("community_communication.group_community_resident")
    portal = env.ref("base.group_portal")
    internal = env.ref("base.group_user")
    officer = env.ref("community_communication.group_community_officer")
    home = env.ref("community_communication.action_community_dashboard")
    Users = env["res.users"].with_context(active_test=False)

    officers_with_resident = Users.search([
        ("groups_id", "in", resident_group.ids),
        ("groups_id", "in", officer.ids),
    ])
    if officers_with_resident:
        officers_with_resident.write({"groups_id": [Command.unlink(resident_group.id)]})

    users = Users.search([("groups_id", "in", resident_group.ids)])
    for user in users:
        if user.has_group("community_communication.group_community_officer"):
            continue
        groups = (user.groups_id - internal) | portal | resident_group
        user.write({
            "groups_id": [Command.set(groups.ids)],
            "action_id": home.id,
        })


def _sync_resident_rule_domains(env):
    for xmlid, domain in RESIDENT_RULE_DOMAINS.items():
        rule = env.ref(f"community_communication.{xmlid}", raise_if_not_found=False)
        if rule:
            rule.sudo().write({"domain_force": domain})
    comment_rule = env.ref("community_communication.comment_resident_rule", raise_if_not_found=False)
    if comment_rule:
        comment_rule.sudo().write({
            "perm_read": True,
            "perm_write": False,
            "perm_create": False,
            "perm_unlink": False,
        })
