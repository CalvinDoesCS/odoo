# -*- coding: utf-8 -*-
"""
billing_invoice.py
------------------
Recurring billing engine — generates Odoo account.move invoices for active
member contracts on their scheduled billing date.

Each `disaster.billing.invoice` is a lightweight wrapper around
`account.move` so that the Dojo Billing menu surfaces only dojo-relevant
invoices without polluting the full Accounting module.

Cron (defined in data/cron_data.xml) calls
  disaster.billing.invoice._cron_generate_recurring()   — daily
"""

from odoo import api, fields, models


class DojoBillingInvoice(models.Model):
    _name = 'disaster.billing.invoice'
    _description = 'Dojo Billing Invoice'
    _order = 'date_due asc'
    _inherit = ['mail.thread']
    _rec_name = 'display_name'

    # ------------------------------------------------------------------
    # Links
    # ------------------------------------------------------------------
    contract_id = fields.Many2one(
        comodel_name='disaster.member.contract',
        string='Contract',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Member',
        related='contract_id.partner_id',
        store=True,
        readonly=True,
    )
    account_move_id = fields.Many2one(
        comodel_name='account.move',
        string='Invoice',
        readonly=True,
        ondelete='set null',
    )

    # ------------------------------------------------------------------
    # Billing fields
    # ------------------------------------------------------------------
    amount = fields.Monetary(
        string='Amount',
        currency_field='currency_id',
        required=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='contract_id.currency_id',
        store=True,
    )
    date_due = fields.Date(string='Due Date', required=True, tracking=True)
    date_paid = fields.Date(string='Paid On', readonly=True)

    state = fields.Selection(
        selection=[
            ('draft',    'Draft'),
            ('sent',     'Sent'),
            ('paid',     'Paid'),
            ('overdue',  'Overdue'),
            ('cancelled','Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )

    notes = fields.Text(string='Notes')

    # ------------------------------------------------------------------
    # Computed display
    # ------------------------------------------------------------------
    display_name = fields.Char(
        string='Reference',
        compute='_compute_display_name',
        store=True,
    )

    @api.depends('partner_id', 'date_due')
    def _compute_display_name(self):
        for rec in self:
            partner = rec.partner_id.name or '?'
            due = str(rec.date_due) if rec.date_due else '?'
            rec.display_name = f'INV/{partner}/{due}'

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_generate_invoice(self):
        """Create an account.move (customer invoice) for this billing record."""
        for rec in self:
            if rec.account_move_id:
                continue
            # Identify income account: use default or partner receivable
            journal = self.env['account.journal'].search(
                [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)],
                limit=1,
            )
            move_vals = {
                'move_type':       'out_invoice',
                'partner_id':      rec.partner_id.id,
                'invoice_date_due': rec.date_due,
                'journal_id':      journal.id if journal else False,
                'invoice_line_ids': [(0, 0, {
                    'name':        f'Membership — {rec.contract_id.plan_id.name if rec.contract_id.plan_id else "Plan"}',
                    'quantity':    1.0,
                    'price_unit':  rec.amount,
                })],
            }
            move = self.env['account.move'].create(move_vals)
            rec.account_move_id = move
            rec.state = 'sent'

    def action_mark_paid(self):
        for rec in self:
            rec.state = 'paid'
            rec.date_paid = fields.Date.today()
            # Advance next billing date on contract
            if rec.contract_id:
                rec.contract_id._advance_billing_date()

    def action_sync_payment_from_accounting(self):
        """Manually sync payment state from linked account.move."""
        self._sync_payment_states()

    def _sync_payment_states(self):
        """
        Check linked account.move payment_state and auto-mark as paid.
        Called by cron and by manual button.
        """
        for rec in self:
            if rec.account_move_id and rec.state not in ('paid', 'cancelled'):
                pay_state = rec.account_move_id.payment_state
                if pay_state in ('paid', 'in_payment', 'reversed'):
                    rec.state = 'paid'
                    if not rec.date_paid:
                        rec.date_paid = fields.Date.today()
                    if rec.contract_id:
                        rec.contract_id._advance_billing_date()

    def action_mark_overdue(self):
        for rec in self:
            if rec.state not in ('paid', 'cancelled'):
                rec.state = 'overdue'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_generate_recurring(self):
        """
        Called daily by cron.
        For every active contract whose next_billing_date <= today,
        create a DojoBillingInvoice (and the matching account.move).
        """
        today = fields.Date.today()
        contracts = self.env['disaster.member.contract'].search([
            ('state', '=', 'active'),
            ('next_billing_date', '<=', today),
        ])
        for contract in contracts:
            # Avoid duplicate drafts for the same due date
            existing = self.search([
                ('contract_id', '=', contract.id),
                ('date_due', '=', contract.next_billing_date),
            ], limit=1)
            if not existing:
                billing = self.create({
                    'contract_id': contract.id,
                    'amount':      contract.price,
                    'date_due':    contract.next_billing_date,
                    'state':       'draft',
                })
                billing.action_generate_invoice()

    @api.model
    def _cron_mark_overdue(self):
        """Mark invoices whose due date has passed and are still unpaid."""
        today = fields.Date.today()
        overdue = self.search([
            ('state', 'in', ('draft', 'sent')),
            ('date_due', '<', today),
        ])
        overdue.write({'state': 'overdue'})
        # Auto-sync payment state from linked account.move records
        pending = self.search([
            ('state', 'not in', ('paid', 'cancelled')),
            ('account_move_id', '!=', False),
        ])
        pending._sync_payment_states()
