from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    subscription_id = fields.Many2one(
        "dojo.member.subscription",
        string="Dojo Subscription",
        index=True,
        ondelete="set null",
        help="Dojo membership subscription that generated this invoice.",
    )
