from odoo import api, fields, models


class DojoMember(models.Model):
    _inherit = "dojo.member"

    subscription_ids = fields.One2many(
        "dojo.member.subscription", "member_id", string="Subscriptions"
    )
    subscription_count = fields.Integer(
        compute="_compute_subscription_count", store=True
    )
    active_subscription_id = fields.Many2one(
        "dojo.member.subscription",
        compute="_compute_active_subscription",
        string="Active Plan",
        store=True,
    )

    @api.depends("subscription_ids")
    def _compute_subscription_count(self):
        for member in self:
            member.subscription_count = len(member.subscription_ids)

    @api.depends("subscription_ids.state")
    def _compute_active_subscription(self):
        for member in self:
            active = member.subscription_ids.filtered(
                lambda s: s.state == "active"
            )[:1]
            member.active_subscription_id = active

    def action_view_member_subscriptions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Subscriptions",
            "res_model": "dojo.member.subscription",
            "view_mode": "list,form",
            "domain": [("member_id", "=", self.id)],
            "context": {"default_member_id": self.id},
        }
