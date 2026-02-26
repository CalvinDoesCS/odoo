from odoo import fields, models


class DojoMemberSubscription(models.Model):
    _name = "dojo.member.subscription"
    _description = "Dojo Member Subscription"

    member_id = fields.Many2one("dojo.member", required=True, index=True)
    household_id = fields.Many2one(
        "dojo.household", related="member_id.household_id", store=True, readonly=True
    )
    plan_id = fields.Many2one("dojo.subscription.plan", required=True, index=True)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
    start_date = fields.Date(required=True, default=fields.Date.context_today)
    end_date = fields.Date()
    next_billing_date = fields.Date()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("paused", "Paused"),
            ("cancelled", "Cancelled"),
            ("expired", "Expired"),
        ],
        default="draft",
        required=True,
    )
    last_invoice_id = fields.Many2one("account.move", string="Last Invoice")
    billing_reference = fields.Char(help="External billing system reference.")
    note = fields.Text()
