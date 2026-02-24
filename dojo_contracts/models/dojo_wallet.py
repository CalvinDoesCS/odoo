# -*- coding: utf-8 -*-
"""
dojo_wallet.py
--------------
Per-member wallet (monetary balance) and store-credit balance, plus an
immutable double-entry ledger of wallet transactions.

Models
------
  dojo.wallet     – one per member; stores current balance + credit_balance
  dojo.wallet.tx  – ledger rows (append-only; unlink() raises)
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class DojoWallet(models.Model):
    _name = 'dojo.wallet'
    _description = 'Member Wallet'
    _inherit = ['mail.thread']
    _rec_name = 'partner_id'

    partner_id = fields.Many2one(
        'res.partner', string='Member', required=True,
        domain="[('is_member','=',True)]",
        ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(
        'res.company', string='Dojo',
        required=True, default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    balance = fields.Monetary(
        string='Cash Balance', currency_field='currency_id',
        tracking=True,
    )
    credit_balance = fields.Float(
        string='Store Credits',
        digits=(10, 2),
        tracking=True,
        help='Dojo store credits redeemable against purchases.',
    )

    tx_ids = fields.One2many('dojo.wallet.tx', 'wallet_id', string='Transactions')
    tx_count = fields.Integer(string='Transactions', compute='_compute_tx_count')

    _sql_constraints = [
        ('unique_partner_company',
         'UNIQUE(partner_id, company_id)',
         'Each member can only have one wallet per company.'),
    ]

    @api.depends('tx_ids')
    def _compute_tx_count(self):
        for rec in self:
            rec.tx_count = len(rec.tx_ids)

    def action_view_transactions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Wallet Transactions – %s') % self.partner_id.name,
            'res_model': 'dojo.wallet.tx',
            'view_mode': 'list,form',
            'domain': [('wallet_id', '=', self.id)],
            'context': {'default_wallet_id': self.id},
        }

    # ── Ledger helpers ──────────────────────────────────────────────
    def _post_tx(self, tx_type, amount=0.0, credits=0.0, description='', ref_model=None, ref_id=None):
        """Create a transaction row and update running balances."""
        self.ensure_one()
        self.env['dojo.wallet.tx'].create({
            'wallet_id': self.id,
            'tx_type': tx_type,
            'amount': amount,
            'credits': credits,
            'description': description,
            'ref_model': ref_model or '',
            'ref_id': ref_id or 0,
        })
        # Update balances
        if amount:
            self.balance += amount
        if credits:
            self.credit_balance += credits

    def add_balance(self, amount, description='Top-up', ref_model=None, ref_id=None):
        self._post_tx('earn', amount=amount, description=description,
                      ref_model=ref_model, ref_id=ref_id)

    def deduct_balance(self, amount, description='Purchase', ref_model=None, ref_id=None):
        if self.balance < amount:
            raise ValidationError(_('Insufficient wallet balance.'))
        self._post_tx('spend', amount=-amount, description=description,
                      ref_model=ref_model, ref_id=ref_id)

    def add_credits(self, credits, description='Credits earned', ref_model=None, ref_id=None):
        self._post_tx('earn', credits=credits, description=description,
                      ref_model=ref_model, ref_id=ref_id)

    def redeem_credits(self, credits, description='Credits redeemed', ref_model=None, ref_id=None):
        if self.credit_balance < credits:
            raise ValidationError(_('Insufficient store credits.'))
        self._post_tx('spend', credits=-credits, description=description,
                      ref_model=ref_model, ref_id=ref_id)

    @api.model
    def get_or_create_wallet(self, partner_id, company_id=None):
        """Idempotent wallet fetch / creation."""
        company_id = company_id or self.env.company.id
        wallet = self.search([('partner_id', '=', partner_id), ('company_id', '=', company_id)], limit=1)
        if not wallet:
            wallet = self.create({'partner_id': partner_id, 'company_id': company_id})
        return wallet


class DojoWalletTx(models.Model):
    _name = 'dojo.wallet.tx'
    _description = 'Wallet Transaction'
    _order = 'create_date desc, id desc'

    wallet_id = fields.Many2one(
        'dojo.wallet', string='Wallet', required=True,
        ondelete='cascade', index=True,
    )
    partner_id = fields.Many2one(
        related='wallet_id.partner_id', store=True, string='Member',
    )
    tx_type = fields.Selection([
        ('earn',   'Earn / Top-up'),
        ('spend',  'Spend'),
        ('adjust', 'Manual Adjustment'),
        ('refund', 'Refund'),
    ], string='Type', required=True, default='earn')

    amount = fields.Monetary(
        string='Cash Amount',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='wallet_id.currency_id', store=True,
    )
    credits = fields.Float(string='Credits', digits=(10, 2))
    description = fields.Char(string='Description')
    ref_model = fields.Char(string='Source Model')
    ref_id = fields.Integer(string='Source Record ID')

    def unlink(self):
        raise UserError(_('Wallet ledger entries cannot be deleted to preserve audit integrity.'))
