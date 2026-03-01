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
    price = fields.Monetary(currency_field="currency_id", required=True, string='Recurring Price')
    initial_fee = fields.Monetary(
        currency_field="currency_id",
        default=0.0,
        string='Initial / Setup Fee',
        help='One-time fee charged when the subscription starts. Leave at 0 if none.',
    )
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

    # ── Course / session constraints ──────────────────────────────────────
    allowed_template_ids = fields.Many2many(
        'dojo.class.template',
        'dojo_sub_plan_template_rel',
        'plan_id',
        'template_id',
        string='Allowed Courses',
        help=(
            'Which courses (class templates) members with this plan may enrol in. '
            'Leave empty to allow all courses — only session-cap rules will apply.'
        ),
    )
    max_sessions_per_week = fields.Integer(
        string='Max Sessions / Week',
        default=0,
        help='Maximum number of sessions a member can attend per calendar week under this plan. 0 = unlimited.',
    )
