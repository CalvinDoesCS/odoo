# -*- coding: utf-8 -*-
"""
belt_test.py
------------
Belt-test / Graduation event.

Workflow
--------
  action_open()    → draft → open
  action_close()   → open → done  (auto-promotes members in passed_ids)
  action_cancel()  → any → cancelled

Auto-invite
-----------
  action_invite_ready_members() — populates invited_member_ids from
  all members where ready_for_test == True AND current belt == belt_rank_testing
  (i.e., they are eligible for the NEXT rank).
"""

from odoo import api, fields, models


class DojoBeltTest(models.Model):
    _name = 'disaster.belt.test'
    _description = 'Dojo Belt Promotion Test'
    _order = 'test_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Test Name', required=True,
        default=lambda self: 'Belt Test',
        tracking=True,
    )
    test_date = fields.Datetime(
        string='Test Date', required=True, tracking=True,
    )
    location = fields.Char(string='Location')
    instructor_id = fields.Many2one(
        comodel_name='res.partner',
        string='Presiding Instructor',
        domain="[('is_instructor', '=', True)]",
        tracking=True,
    )

    # Belt rank being AWARDED (i.e., tested-for rank)
    belt_rank_awarded = fields.Selection(
        selection=[
            ('yellow', 'Yellow'),
            ('orange', 'Orange'),
            ('green', 'Green'),
            ('blue', 'Blue'),
            ('purple', 'Purple'),
            ('brown', 'Brown'),
            ('red', 'Red'),
            ('black', 'Black'),
        ],
        string='Belt Rank Awarded',
        required=True,
        tracking=True,
    )

    test_fee = fields.Monetary(
        string='Test Fee',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )

    state = fields.Selection(
        selection=[
            ('draft',      'Planned'),
            ('open',       'Open / In Progress'),
            ('done',       'Completed'),
            ('cancelled',  'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
    )

    # Participants
    invited_member_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='disaster_belt_test_invited_rel',
        column1='test_id',
        column2='partner_id',
        string='Invited Members',
        domain="[('is_member', '=', True)]",
    )
    passed_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='disaster_belt_test_passed_rel',
        column1='test_id',
        column2='partner_id',
        string='Passed',
        domain="[('is_member', '=', True)]",
    )
    failed_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='disaster_belt_test_failed_rel',
        column1='test_id',
        column2='partner_id',
        string='Did Not Pass',
        domain="[('is_member', '=', True)]",
    )

    notes = fields.Text(string='Notes / Requirements')

    # Fee invoices generated for this test
    invoice_ids = fields.Many2many(
        comodel_name='account.move',
        relation='disaster_belt_test_invoice_rel',
        column1='test_id',
        column2='move_id',
        string='Fee Invoices',
        readonly=True,
    )
    invoice_count = fields.Integer(
        string='Invoices',
        compute='_compute_invoice_count',
    )

    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)

    # Computed counters
    invited_count = fields.Integer(
        string='Invited', compute='_compute_counts',
    )
    passed_count = fields.Integer(
        string='Passed', compute='_compute_counts',
    )
    failed_count = fields.Integer(
        string='Failed', compute='_compute_counts',
    )

    @api.depends('invited_member_ids', 'passed_ids', 'failed_ids')
    def _compute_counts(self):
        for rec in self:
            rec.invited_count = len(rec.invited_member_ids)
            rec.passed_count  = len(rec.passed_ids)
            rec.failed_count  = len(rec.failed_ids)

    # ------------------------------------------------------------------
    # Stage actions
    # ------------------------------------------------------------------
    def action_open(self):
        self.write({'state': 'open'})

    def action_close(self):
        """Complete the test: promote all members in passed_ids."""
        for rec in self:
            rec.state = 'done'
            for member in rec.passed_ids:
                member.belt_rank = rec.belt_rank_awarded
                member.message_post(
                    body=f'🥋 Promoted to <b>{rec.belt_rank_awarded}</b> belt at test: {rec.name}',
                )
            # Generate test-fee invoices if fee > 0
            if rec.test_fee and rec.test_fee > 0:
                rec._create_test_fee_invoices()

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    # ------------------------------------------------------------------
    # Auto-invite
    # ------------------------------------------------------------------
    def action_invite_ready_members(self):
        """
        Auto-populate invited list: members whose current belt rank
        is one rank below belt_rank_awarded and are flagged ready_for_test.
        """
        _BELT_ORDER = [
            'white', 'yellow', 'orange', 'green',
            'blue', 'purple', 'brown', 'red', 'black',
        ]
        for rec in self:
            if not rec.belt_rank_awarded:
                continue
            idx = _BELT_ORDER.index(rec.belt_rank_awarded)
            current_rank = _BELT_ORDER[idx - 1] if idx > 0 else _BELT_ORDER[0]
            eligible = self.env['res.partner'].search([
                ('is_member',      '=', True),
                ('belt_rank',      '=', current_rank),
                ('ready_for_test', '=', True),
            ])
            rec.invited_member_ids = [(6, 0, eligible.ids)]

    # ------------------------------------------------------------------
    # Fee invoices
    # ------------------------------------------------------------------
    def _create_test_fee_invoices(self):
        journal = self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)],
            limit=1,
        )
        moves = self.env['account.move']
        for member in self.passed_ids | self.failed_ids:
            move = self.env['account.move'].create({
                'move_type':       'out_invoice',
                'partner_id':      member.id,
                'invoice_date_due': self.test_date.date() if self.test_date else fields.Date.today(),
                'journal_id':      journal.id if journal else False,
                'invoice_line_ids': [(0, 0, {
                    'name':       f'Belt Test Fee — {self.name} ({self.belt_rank_awarded})',
                    'quantity':   1.0,
                    'price_unit': self.test_fee,
                })],
            })
            moves |= move
        if moves:
            self.invoice_ids = [(4, m.id) for m in moves]

    def action_view_invoices(self):
        """Open fee invoices for this belt test."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Invoices – {self.name}',
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
        }
