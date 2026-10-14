# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Drop portal membership before Resident starts implying Internal User."""
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
        WHERE module = 'community_communication' AND name = 'group_community_resident'
        """
    )
    resident = cr.fetchone()
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
        WHERE module = 'base' AND name = 'group_portal'
        """
    )
    portal = cr.fetchone()
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
        WHERE module = 'base' AND name = 'group_user'
        """
    )
    internal = cr.fetchone()
    if not (resident and portal and internal):
        return
    resident_id, portal_id, user_id = resident[0], portal[0], internal[0]
    cr.execute("DELETE FROM res_groups_implied_rel WHERE gid = %s", (resident_id,))
    cr.execute(
        "INSERT INTO res_groups_implied_rel (gid, hid) VALUES (%s, %s)",
        (resident_id, user_id),
    )
    cr.execute("SELECT uid FROM res_groups_users_rel WHERE gid = %s", (resident_id,))
    uids = [row[0] for row in cr.fetchall()]
    if not uids:
        return
    cr.execute(
        "DELETE FROM res_groups_users_rel WHERE gid = %s AND uid = ANY(%s)",
        (portal_id, uids),
    )
    cr.execute("SELECT uid FROM res_groups_users_rel WHERE gid = %s", (user_id,))
    already = {row[0] for row in cr.fetchall()}
    missing = [uid for uid in uids if uid not in already]
    for uid in missing:
        cr.execute(
            "INSERT INTO res_groups_users_rel (uid, gid) VALUES (%s, %s)",
            (uid, user_id),
        )
    cr.execute(
        "UPDATE res_users SET share = false WHERE id = ANY(%s)",
        (uids,),
    )
