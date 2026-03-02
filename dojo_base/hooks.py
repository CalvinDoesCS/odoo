"""
post_init_hook for dojo_base.

After install, automatically grants the built-in 'admin' user the Dojo Admin
group so the Admin Dashboard menu is visible without manual configuration.
"""


def post_init_hook(env):
    """Add the admin user to the Dojo Admin group on first install."""
    admin_user = env["res.users"].search([("login", "=", "admin")], limit=1)
    if not admin_user:
        return
    group_admin = env.ref("dojo_base.group_dojo_admin", raise_if_not_found=False)
    if not group_admin:
        return
    if group_admin not in admin_user.group_ids:
        admin_user.write({"group_ids": [(4, group_admin.id)]})
