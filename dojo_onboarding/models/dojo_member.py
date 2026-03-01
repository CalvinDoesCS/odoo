from odoo import api, fields, models


class DojoMember(models.Model):
    _inherit = "dojo.member"

    onboarding_record_ids = fields.One2many(
        "dojo.onboarding.record", "member_id", string="Onboarding Records"
    )
    onboarding_count = fields.Integer(
        compute="_compute_onboarding_count", store=True
    )

    @api.depends("onboarding_record_ids")
    def _compute_onboarding_count(self):
        for member in self:
            member.onboarding_count = len(member.onboarding_record_ids)

    def action_view_onboarding_records(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Onboarding Records",
            "res_model": "dojo.onboarding.record",
            "view_mode": "list,form",
            "domain": [("member_id", "=", self.id)],
            "context": {"default_member_id": self.id},
        }
