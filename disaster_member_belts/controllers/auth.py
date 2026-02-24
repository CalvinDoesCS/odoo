# -*- coding: utf-8 -*-
"""
auth.py
-------
Overrides Odoo's post-login redirect so that:

  - Portal users who are dojo members  → /my/dojo  (their member dashboard)
  - All other users                    → default Odoo behaviour (unchanged)
"""

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home


class DojoAuthController(Home):

    def _login_redirect(self, uid, redirect=None):
        """
        Called by web_login() immediately after a successful authentication.

        If a redirect URL was explicitly passed (e.g. from a 'redirect' query
        param), honour it unchanged.  Otherwise, send dojo members straight
        to their portal dashboard.
        """
        # If the caller already specified a destination, don't override it
        if redirect:
            return super()._login_redirect(uid, redirect=redirect)

        # Check whether this UID belongs to a portal user who is a dojo member
        try:
            user = request.env['res.users'].sudo().browse(uid)
            if user.exists() and user.share and user.partner_id.is_member:
                return '/my/dojo'
        except Exception:
            pass  # fall through to default on any error

        return super()._login_redirect(uid, redirect=redirect)
