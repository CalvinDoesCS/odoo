from odoo import models


class DojoMember(models.Model):
    _inherit = "dojo.member"

    def action_contact_guardian(self):
        """Open the Send Message wizard pre-loaded with this member."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Contact Guardian",
            "res_model": "dojo.send.message.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_member_ids": [(6, 0, [self.id])]},
        }
