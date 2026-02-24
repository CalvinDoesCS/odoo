# -*- coding: utf-8 -*-
"""
member_contract_ext.py
----------------------
Extends disaster.member.contract with:
  - on_hold / past_due states (added via _selection_state_add if available;
    here we use a computed field + flags since extending Selection in Odoo
    requires overriding the whole field — we add extra tracking fields instead)
  - dojo_hold_reason     – free-text reason for the hold
  - dojo_hold_until      – date the hold expires
  - dojo_past_due_since  – date the contract first went past-due
  - dojo_billing_day     – day-of-month for recurring billing (1–28)
  - dojo_payment_ref     – external payment token / subscription reference
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MemberContractExt(models.Model):
    _inherit = 'disaster.member.contract'

    # ── Hold / Pause ────────────────────────────────────────────────
    dojo_on_hold = fields.Boolean(
        string='On Hold', default=False, tracking=True,
    )
    dojo_hold_reason = fields.Char(
        string='Hold Reason', tracking=True,
    )
    dojo_hold_until = fields.Date(
        string='Hold Until', tracking=True,
        help='Auto-resume the contract on this date (via cron).',
    )

    # ── Delinquency ─────────────────────────────────────────────────
    dojo_past_due = fields.Boolean(
        string='Past Due', default=False, tracking=True,
    )
    dojo_past_due_since = fields.Date(
        string='Past Due Since', tracking=True,
    )
    dojo_dunning_count = fields.Integer(
        string='Dunning Attempts', default=0,
        help='Number of automated payment retry / notice attempts.',
    )
    dojo_next_dunning_date = fields.Date(string='Next Dunning Date')

    # ── Billing config ──────────────────────────────────────────────
    dojo_billing_day = fields.Integer(
        string='Billing Day', default=1,
        help='Day of the month on which recurring billing runs (1–28).',
    )
    dojo_payment_ref = fields.Char(
        string='Payment Reference',
        help='External token ID (e.g. Stripe subscription / payment method id).',
    )

    # ── Wallet link ─────────────────────────────────────────────────
    dojo_wallet_id = fields.Many2one(
        'dojo.wallet', string='Wallet',
        compute='_compute_wallet_id', store=False,
    )

    @api.depends('partner_id')
    def _compute_wallet_id(self):
        Wallet = self.env['dojo.wallet']
        for rec in self:
            rec.dojo_wallet_id = Wallet.search(
                [('partner_id', '=', rec.partner_id.id)], limit=1
            )

    # ── Validation ──────────────────────────────────────────────────
    @api.constrains('dojo_billing_day')
    def _check_billing_day(self):
        for rec in self:
            if not (1 <= rec.dojo_billing_day <= 28):
                raise ValidationError(_('Billing day must be between 1 and 28.'))

    # ── Hold actions ────────────────────────────────────────────────
    def action_put_on_hold(self):
        self.write({'dojo_on_hold': True})
        for rec in self:
            rec.message_post(body=_('Contract placed on hold. Reason: %s') % (rec.dojo_hold_reason or '—'))

    def action_resume_from_hold(self):
        self.write({'dojo_on_hold': False, 'dojo_hold_until': False})
        for rec in self:
            rec.message_post(body=_('Contract resumed from hold.'))

    # ── Delinquency actions ─────────────────────────────────────────
    def action_mark_past_due(self):
        self.write({
            'dojo_past_due': True,
            'dojo_past_due_since': self.dojo_past_due_since or fields.Date.today(),
        })

    def action_clear_past_due(self):
        self.write({
            'dojo_past_due': False,
            'dojo_past_due_since': False,
            'dojo_dunning_count': 0,
            'dojo_next_dunning_date': False,
        })

    # ── Cron: auto-resume holds ─────────────────────────────────────
    @api.model
    def cron_auto_resume_holds(self):
        """Resume contracts whose hold_until date has passed."""
        expired_holds = self.search([
            ('dojo_on_hold', '=', True),
            ('dojo_hold_until', '!=', False),
            ('dojo_hold_until', '<=', fields.Date.today()),
        ])
        expired_holds.action_resume_from_hold()
