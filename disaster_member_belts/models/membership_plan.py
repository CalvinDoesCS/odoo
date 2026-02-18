# -*- coding: utf-8 -*-
"""
membership_plan.py
------------------
Describes a membership program offering (e.g. "Kids Monthly", "Adult Unlimited").
Used as a template when creating member contracts.
"""

from odoo import fields, models


BILLING_CYCLE = [
    ('weekly',    'Weekly'),
    ('monthly',   'Monthly'),
    ('quarterly', 'Quarterly'),
    ('annual',    'Annual'),
    ('one_time',  'One Time'),
]


class DisasterMembershipPlan(models.Model):
    _name = 'disaster.membership.plan'
    _description = 'Membership Plan'
    _order = 'sequence, name'
    _inherit = ['mail.thread']

    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Plan Name',
        required=True,
        tracking=True,
    )
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)

    # Pricing
    billing_cycle = fields.Selection(
        selection=BILLING_CYCLE,
        string='Billing Cycle',
        default='monthly',
        required=True,
        tracking=True,
    )
    price = fields.Monetary(
        string='Price',
        currency_field='currency_id',
        tracking=True,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    setup_fee = fields.Monetary(
        string='Setup / Enrolment Fee',
        currency_field='currency_id',
    )

    # Classes included
    classes_per_week = fields.Integer(
        string='Classes per Week',
        default=0,
        help='0 = unlimited',
    )
    contract_duration_months = fields.Integer(
        string='Min Contract (months)',
        default=1,
        help='Minimum commitment period in months. 0 = no minimum.',
    )

    # Belt program
    belt_program = fields.Boolean(
        string='Includes Belt Program',
        default=True,
        help='Tick if this plan includes grading / belt promotions.',
    )
    target_belt_ranks = fields.Many2many(
        comodel_name='disaster.belt.rank.config',
        string='Applicable Belt Ranks',
        help='Leave empty to allow all ranks.',
    )

    # Stats
    contract_count = fields.Integer(
        string='Active Contracts',
        compute='_compute_contract_count',
    )

    def _compute_contract_count(self):
        Contract = self.env['disaster.member.contract']
        for plan in self:
            plan.contract_count = Contract.search_count([
                ('plan_id', '=', plan.id),
                ('state', 'in', ['trial', 'active']),
            ])

    def action_view_contracts(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Contracts – {self.name}',
            'res_model': 'disaster.member.contract',
            'view_mode': 'list,form',
            'domain': [('plan_id', '=', self.id)],
            'context': {'default_plan_id': self.id},
        }
