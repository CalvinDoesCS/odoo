import logging
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


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
    invoice_ids = fields.One2many("account.move", "subscription_id", string="Invoices")
    invoice_count = fields.Integer(compute="_compute_invoice_count", store=True)
    billing_reference = fields.Char(help="External billing system reference.")
    note = fields.Text()

    # ── Computed ──────────────────────────────────────────────────────────
    @api.depends("invoice_ids")
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    # ── Helpers ───────────────────────────────────────────────────────────
    def _billing_partner(self):
        """Return the res.partner to invoice for this subscription."""
        self.ensure_one()
        household = self.household_id
        if household and household.billing_partner_id:
            return household.billing_partner_id
        member = self.member_id
        if member.partner_id:
            return member.partner_id
        return self.env["res.partner"].browse()

    def _next_date_from(self, from_date):
        """Return the billing date one period after from_date."""
        period = self.plan_id.billing_period
        if period == "weekly":
            return from_date + relativedelta(weeks=1)
        elif period == "yearly":
            return from_date + relativedelta(years=1)
        return from_date + relativedelta(months=1)

    # ── Invoice generation ────────────────────────────────────────────────
    def action_generate_invoice(self):
        """Create and post an Odoo invoice for this subscription billing cycle."""
        self.ensure_one()
        plan = self.plan_id
        billing_partner = self._billing_partner()
        if not billing_partner:
            raise UserError(
                _("No billing partner found for subscription of %s.", self.member_id.name)
            )

        today = fields.Date.today()
        period_label = {"weekly": "Weekly", "monthly": "Monthly", "yearly": "Annual"}.get(
            plan.billing_period, plan.billing_period.capitalize()
        )
        invoice = self.env["account.move"].sudo().create({
            "move_type": "out_invoice",
            "partner_id": billing_partner.id,
            "invoice_date": today,
            "invoice_date_due": today + relativedelta(days=7),
            "subscription_id": self.id,
            "company_id": (self.company_id or self.env.company).id,
            "invoice_line_ids": [(0, 0, {
                "name": "{} – {} Membership".format(plan.name, period_label),
                "quantity": 1.0,
                "price_unit": plan.price,
            })],
        })
        invoice.action_post()
        self.last_invoice_id = invoice
        # Advance next billing date by one period
        base = self.next_billing_date or today
        self.next_billing_date = self._next_date_from(base)
        return invoice

    def action_view_invoices(self):
        """Smart button: open invoices linked to this subscription."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Invoices",
            "res_model": "account.move",
            "view_mode": "list,form",
            "domain": [("subscription_id", "=", self.id)],
            "context": {
                "default_subscription_id": self.id,
                "default_move_type": "out_invoice",
            },
        }

    # ── Daily cron ────────────────────────────────────────────────────────
    @api.model
    def _cron_generate_invoices(self):
        """Generate invoices for all active subscriptions due today or earlier."""
        today = fields.Date.today()
        due = self.search([
            ("state", "=", "active"),
            ("next_billing_date", "!=", False),
            ("next_billing_date", "<=", today),
        ])
        for sub in due:
            try:
                sub.action_generate_invoice()
            except Exception as exc:
                _logger.error(
                    "Dojo billing: failed to invoice subscription %s: %s", sub.id, exc
                )
