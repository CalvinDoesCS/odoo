# -*- coding: utf-8 -*-
"""
dojo_sale.py
------------
Front-desk retail / point-of-sale for gear, equipment, and one-time fees.

Uses `product.product` (already installed) for items.
Creates an `account.move` (customer invoice) on confirmation.

Models
------
  disaster.dojo.sale       — sale order header
  disaster.dojo.sale.line  — order line
"""

from odoo import api, fields, models


class DojoSale(models.Model):
    _name = 'disaster.dojo.sale'
    _description = 'Dojo Front-Desk Sale'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread']
    _rec_name = 'reference'

    reference = fields.Char(
        string='Reference',
        readonly=True,
        copy=False,
        default='New',
    )
    date = fields.Datetime(
        string='Sale Date',
        default=fields.Datetime.now,
        required=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Customer',
        required=True,
        tracking=True,
    )
    cashier_id = fields.Many2one(
        comodel_name='res.users',
        string='Cashier',
        default=lambda self: self.env.user,
    )
    line_ids = fields.One2many(
        comodel_name='disaster.dojo.sale.line',
        inverse_name='sale_id',
        string='Items',
    )
    total = fields.Monetary(
        string='Total',
        compute='_compute_total',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    state = fields.Selection(
        selection=[
            ('draft',     'Draft'),
            ('confirmed', 'Confirmed'),
            ('invoiced',  'Invoiced'),
            ('paid',      'Paid'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )
    account_move_id = fields.Many2one(
        comodel_name='account.move',
        string='Invoice',
        readonly=True,
        ondelete='set null',
    )
    notes = fields.Text(string='Notes')

    @api.depends('line_ids.subtotal')
    def _compute_total(self):
        for rec in self:
            rec.total = sum(rec.line_ids.mapped('subtotal'))

    # ------------------------------------------------------------------
    # Sequence on create
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('reference', 'New') == 'New':
                vals['reference'] = self.env['ir.sequence'].next_by_code(
                    'disaster.dojo.sale'
                ) or 'POS/0001'
        return super().create(vals_list)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_confirm(self):
        for rec in self:
            rec.state = 'confirmed'

    def action_create_invoice(self):
        """Generate or open the linked invoice."""
        journal = self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)],
            limit=1,
        )
        for rec in self:
            if rec.account_move_id:
                return rec._open_invoice_action()
            lines = []
            for line in rec.line_ids:
                lines.append((0, 0, {
                    'name':       line.product_id.name if line.product_id else line.description,
                    'quantity':   line.qty,
                    'price_unit': line.unit_price,
                }))
            move = self.env['account.move'].create({
                'move_type':  'out_invoice',
                'partner_id': rec.partner_id.id,
                'journal_id': journal.id if journal else False,
                'invoice_line_ids': lines,
            })
            rec.account_move_id = move
            rec.state = 'invoiced'
        return self._open_invoice_action()

    def _open_invoice_action(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.account_move_id.id,
            'view_mode': 'form',
        }

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'

    def action_mark_paid(self):
        """Manually mark this sale as paid."""
        for rec in self:
            if rec.state not in ('cancelled',):
                rec.state = 'paid'

    def action_sync_payment_from_accounting(self):
        """Manually sync payment state from linked account.move."""
        self._sync_payment_states()

    def _sync_payment_states(self):
        """
        Check linked account.move payment_state and auto-mark sale as paid.
        """
        for rec in self:
            if rec.account_move_id and rec.state not in ('paid', 'cancelled'):
                pay_state = rec.account_move_id.payment_state
                if pay_state in ('paid', 'in_payment', 'reversed'):
                    rec.state = 'paid'


class DojoSaleLine(models.Model):
    _name = 'disaster.dojo.sale.line'
    _description = 'Dojo Sale Line'

    sale_id = fields.Many2one(
        comodel_name='disaster.dojo.sale',
        string='Sale',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        ondelete='restrict',
    )
    description = fields.Char(
        string='Description',
        compute='_compute_description',
        store=True,
        readonly=False,
    )
    qty = fields.Float(string='Qty', default=1.0, required=True)
    unit_price = fields.Monetary(
        string='Unit Price',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='sale_id.currency_id',
        store=True,
    )
    subtotal = fields.Monetary(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
        currency_field='currency_id',
    )

    @api.depends('product_id')
    def _compute_description(self):
        for line in self:
            if line.product_id:
                line.description = line.product_id.name
            elif not line.description:
                line.description = ''

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.unit_price = self.product_id.lst_price
            self.description = self.product_id.name

    @api.depends('qty', 'unit_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty * line.unit_price
