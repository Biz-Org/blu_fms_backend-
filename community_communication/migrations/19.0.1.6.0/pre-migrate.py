# -*- coding: utf-8 -*-


def _xmlid(cr, module, name):
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
        WHERE module = %s AND name = %s
        """,
        (module, name),
    )
    row = cr.fetchone()
    return row[0] if row else None


def migrate(cr, version):
    """Convert Community residents off Internal User before Resident implies Portal."""
    resident_id = _xmlid(cr, "community_communication", "group_community_resident")
    officer_id = _xmlid(cr, "community_communication", "group_community_officer")
    portal_id = _xmlid(cr, "base", "group_portal")
    user_id = _xmlid(cr, "base", "group_user")
    if not (resident_id and portal_id and user_id):
        return

    if officer_id:
        cr.execute(
            """
            DELETE FROM res_groups_users_rel
            WHERE gid = %s
              AND uid IN (
                SELECT uid FROM res_groups_users_rel WHERE gid = %s
              )
            """,
            (resident_id, officer_id),
        )

    cr.execute("DELETE FROM res_groups_implied_rel WHERE gid = %s", (resident_id,))
    cr.execute(
        "INSERT INTO res_groups_implied_rel (gid, hid) VALUES (%s, %s)",
        (resident_id, portal_id),
    )

    cr.execute("SELECT uid FROM res_groups_users_rel WHERE gid = %s", (resident_id,))
    uids = [row[0] for row in cr.fetchall()]
    if not uids:
        return

    cr.execute(
        "DELETE FROM res_groups_users_rel WHERE gid = %s AND uid = ANY(%s)",
        (user_id, uids),
    )
    cr.execute("SELECT uid FROM res_groups_users_rel WHERE gid = %s", (portal_id,))
    already = {row[0] for row in cr.fetchall()}
    missing = [uid for uid in uids if uid not in already]
    for uid in missing:
        cr.execute(
            "INSERT INTO res_groups_users_rel (uid, gid) VALUES (%s, %s)",
            (uid, portal_id),
        )
    cr.execute(
        "UPDATE res_users SET share = true WHERE id = ANY(%s)",
        (uids,),
    )
