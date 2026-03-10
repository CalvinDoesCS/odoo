from odoo import models


class DojoMember(models.Model):
    _inherit = "dojo.member"

    def action_print_badge(self):
        """Open the badge print page for this member (instructors/admins only).

        The route itself also enforces group access, so this is a double-guard.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/dojo/marketing/member/{self.id}/badge",
            "target": "new",
        }

    def action_member_badge_qr_print(self):
        """Open the member's own badge print page (for portal / self-service).

        Opens the print wrapper at /my/dojo/badge/print which requires auth=user.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": "/my/dojo/badge/print",
            "target": "new",
        }
