# -*- coding: utf-8 -*-
"""
member_contract.py
------------------
Per-member contract tied to a membership plan.
Tracks: trial → active → expired / cancelled lifecycle.
Generates reminder activities for renewals.
"""

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from odoo.exceptions import UserError


class DisasterMemberContract(models.Model):
    _name = 'disaster.member.contract'
    _description = 'Member Contract / Subscription'
    _order = 'date_start desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'

    display_name = fields.Char(
        string='Contract',
        compute='_compute_display_name',
        store=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Member',
        required=True,
        index=True,
        ondelete='cascade',
        tracking=True,
    )
    plan_id = fields.Many2one(
        comodel_name='disaster.membership.plan',
        string='Membership Plan',
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft',     'Draft'),
            ('trial',     'Trial'),
            ('active',    'Active'),
            ('expired',   'Expired'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        tracking=True,
        index=True,
    )

    # Dates
    date_start = fields.Date(
        string='Start Date',
        default=fields.Date.today,
        required=True,
        tracking=True,
    )
    trial_end_date = fields.Date(
        string='Trial End Date',
        tracking=True,
    )
    date_end = fields.Date(
        string='Contract End Date',
        tracking=True,
    )
    next_billing_date = fields.Date(
        string='Next Billing Date',
        tracking=True,
    )

    # Financials (copied from plan, editable per contract)
    price = fields.Monetary(
        string='Monthly Price',
        currency_field='currency_id',
        tracking=True,
    )
    setup_fee = fields.Monetary(
        string='Setup Fee',
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='plan_id.currency_id',
        store=True,
    )
    billing_cycle = fields.Selection(
        related='plan_id.billing_cycle',
        store=True,
    )

    # Belt program
    belt_program = fields.Boolean(
        related='plan_id.belt_program',
        store=True,
    )

    # ---- Instructor & Course assignment --------------------
    assigned_instructor_id = fields.Many2one(
        comodel_name='res.partner',
        string='Assigned Instructor',
        domain="[('is_instructor', '=', True)]",
        tracking=True,
        help='Primary instructor responsible for this member under this contract.',
    )
    course_id = fields.Many2one(
        comodel_name='disaster.course',
        string='Enrolled Course',
        tracking=True,
        ondelete='set null',
    )

    notes = fields.Text(string='Notes')
    cancellation_reason = fields.Text(string='Cancellation Reason')

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    @api.depends('partner_id', 'plan_id')
    def _compute_display_name(self):
        for rec in self:
            partner = rec.partner_id.name or ''
            plan = rec.plan_id.name or ''
            rec.display_name = f'{partner} – {plan}' if partner and plan else partner or plan

    # ------------------------------------------------------------------
    # Onchange
    # ------------------------------------------------------------------
    @api.onchange('plan_id')
    def _onchange_plan_id(self):
        if self.plan_id:
            self.price = self.plan_id.price
            self.setup_fee = self.plan_id.setup_fee
            if self.plan_id.contract_duration_months and self.date_start:
                self.date_end = self.date_start + relativedelta(
                    months=self.plan_id.contract_duration_months
                )

    @api.onchange('date_start')
    def _onchange_date_start(self):
        if self.date_start and self.plan_id and self.plan_id.contract_duration_months:
            self.date_end = self.date_start + relativedelta(
                months=self.plan_id.contract_duration_months
            )

    # ------------------------------------------------------------------
    # Lifecycle actions
    # ------------------------------------------------------------------
    def action_start_trial(self):
        for rec in self:
            rec.write({
                'state': 'trial',
                'trial_end_date': fields.Date.today() + relativedelta(days=30),
            })
            rec.partner_id.member_stage = 'trial'

    def action_activate(self):
        for rec in self:
            rec.write({
                'state': 'active',
                'next_billing_date': fields.Date.today() + relativedelta(months=1),
            })
            rec.partner_id.member_stage = 'active'
            rec.partner_id.is_member = True

            # Auto-enroll in course if set
            if rec.course_id:
                rec.course_id.enrolled_member_ids = [(4, rec.partner_id.id)]

            # Auto-assign instructor if course has one and none set on contract
            if rec.course_id and rec.course_id.instructor_id and not rec.assigned_instructor_id:
                rec.assigned_instructor_id = rec.course_id.instructor_id

            # Welcome chatter message
            rec.partner_id.message_post(
                body=f"🎉 Welcome! Contract <b>{rec.display_name}</b> has been activated. "
                     f"Plan: {rec.plan_id.name}."
                     + (f" Course: {rec.course_id.name}." if rec.course_id else "")
                     + (f" Instructor: {rec.assigned_instructor_id.name}." if rec.assigned_instructor_id else ""),
                message_type='comment',
                subtype_xmlid='mail.mt_note',
            )

    def action_cancel(self):
        for rec in self:
            rec.write({'state': 'cancelled'})
            rec.partner_id.member_stage = 'inactive'

    def action_expire(self):
        for rec in self:
            rec.write({'state': 'expired'})
            rec.partner_id.member_stage = 'inactive'

    # ------------------------------------------------------------------
    # Scheduled action helper (called by cron)
    # ------------------------------------------------------------------
    @api.model
    def _cron_check_expiries(self):
        """Flag contracts that have passed their end date and send reminders."""
        today = fields.Date.today()

        # Expire overdue active contracts
        overdue = self.search([
            ('state', '=', 'active'),
            ('date_end', '<', today),
        ])
        overdue.action_expire()

        # Send 7-day renewal reminder
        reminder_date = today + relativedelta(days=7)
        expiring_soon = self.search([
            ('state', '=', 'active'),
            ('date_end', '=', reminder_date),
        ])
        for contract in expiring_soon:
            contract.activity_schedule(
                'mail.mail_activity_data_todo',
                date_deadline=today,
                note=f'Contract for {contract.partner_id.name} expires in 7 days. '
                     f'Please arrange renewal.',
                user_id=self.env.uid,
            )

        # Convert expired trials
        expired_trials = self.search([
            ('state', '=', 'trial'),
            ('trial_end_date', '<', today),
        ])
        for t in expired_trials:
            t.partner_id.member_stage = 'inactive'
