from odoo import fields, models


class DojoSubscriptionPlan(models.Model):
    _name = "dojo.subscription.plan"
    _description = "Dojo Subscription Plan"

    name = fields.Char(required=True)
    code = fields.Char()
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id, required=True
    )
    price = fields.Monetary(currency_field="currency_id", required=True)
    billing_period = fields.Selection(
        [
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("yearly", "Yearly"),
        ],
        default="monthly",
        required=True,
    )
    sessions_per_period = fields.Integer(default=0)
    unlimited_sessions = fields.Boolean(default=True)
    description = fields.Text()
