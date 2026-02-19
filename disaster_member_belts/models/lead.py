# -*- coding: utf-8 -*-
"""
lead.py
-------
Prospect / Trial pipeline — replaces the Spark "Leads & Trial Maximizer".

Stages
------
  new        – Just signed up / walked in / web form
  contacted  – Staff reached out (call / text / email)
  appointment– Intro appointment booked
  trial      – Actively on a trial membership
  converted  – Converted to paid contract  (partner.member_stage → active)
  lost       – Did not convert

Workflow
--------
  action_contact()      → new → contacted
  action_set_appointment() → contacted → appointment
  action_start_trial()  → any → trial  (creates trial contract if plan given)
  action_convert()      → trial → converted + activates member_stage
  action_mark_lost()    → any → lost
"""

from odoo import api, fields, models


class DojoLead(models.Model):
    _name = 'disaster.lead'
    _description = 'Dojo Prospect / Trial Lead'
    _order = 'create_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------
    name = fields.Char(
        string='Full Name', required=True, tracking=True,
    )
    phone = fields.Char(string='Phone', tracking=True)
    email = fields.Char(string='Email', tracking=True)
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Contact',
        help='Linked after conversion, or set manually.',
        tracking=True,
        ondelete='set null',
    )

    # ------------------------------------------------------------------
    # Pipeline stage
    # ------------------------------------------------------------------
    stage = fields.Selection(
        selection=[
            ('new',         'New Lead'),
            ('contacted',   'Contacted'),
            ('appointment', 'Appointment'),
            ('trial',       'Trial'),
            ('converted',   'Converted ✓'),
            ('lost',        'Lost'),
        ],
        string='Stage',
        default='new',
        tracking=True,
        index=True,
    )

    # ------------------------------------------------------------------
    # Source / campaign
    # ------------------------------------------------------------------
    source = fields.Selection(
        selection=[
            ('walk_in',   'Walk-In'),
            ('website',   'Website'),
            ('referral',  'Referral'),
            ('social',    'Social Media'),
            ('event',     'Event'),
            ('phone',     'Phone'),
            ('other',     'Other'),
        ],
        string='Source',
        default='walk_in',
        tracking=True,
    )
    referred_by_id = fields.Many2one(
        comodel_name='res.partner',
        string='Referred By',
        domain="[('is_member', '=', True)]",
        ondelete='set null',
    )

    # ------------------------------------------------------------------
    # Trial details
    # ------------------------------------------------------------------
    trial_plan_id = fields.Many2one(
        comodel_name='disaster.membership.plan',
        string='Trial Plan',
        ondelete='set null',
    )
    trial_start_date = fields.Date(string='Trial Start')
    trial_end_date   = fields.Date(string='Trial End')
    trial_contract_id = fields.Many2one(
        comodel_name='disaster.member.contract',
        string='Trial Contract',
        readonly=True,
    )

    # Appointment date
    appointment_date = fields.Datetime(
        string='Appointment Date', tracking=True,
    )

    # Assigned staff
    assigned_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Assigned To',
        default=lambda self: self.env.user,
        tracking=True,
    )

    notes = fields.Text(string='Notes')
    lost_reason = fields.Char(string='Lost Reason')

    # ------------------------------------------------------------------
    # Computed badges
    # ------------------------------------------------------------------
    days_in_stage = fields.Integer(
        string='Days in Stage',
        compute='_compute_days_in_stage',
    )

    @api.depends('write_date')
    def _compute_days_in_stage(self):
        today = fields.Date.today()
        for rec in self:
            wd = rec.write_date.date() if rec.write_date else today
            rec.days_in_stage = (today - wd).days

    # ------------------------------------------------------------------
    # Stage actions
    # ------------------------------------------------------------------
    def action_contact(self):
        for rec in self:
            rec.stage = 'contacted'
            rec.activity_schedule(
                activity_type_xml_id='mail.mail_activity_data_todo',
                summary='Follow up with lead',
                user_id=rec.assigned_user_id.id or self.env.uid,
            )

    def action_set_appointment(self):
        for rec in self:
            rec.stage = 'appointment'

    def action_start_trial(self):
        """Move lead to trial stage; create trial contract if plan set."""
        for rec in self:
            rec.stage = 'trial'
            rec.trial_start_date = rec.trial_start_date or fields.Date.today()

            # Ensure there is a linked partner
            if not rec.partner_id:
                partner = self.env['res.partner'].create({
                    'name':     rec.name,
                    'phone':    rec.phone,
                    'email':    rec.email,
                    'is_member': True,
                    'member_stage': 'trial',
                    'referred_by_id': rec.referred_by_id.id if rec.referred_by_id else False,
                })
                rec.partner_id = partner
            else:
                rec.partner_id.is_member = True
                rec.partner_id.member_stage = 'trial'

            # Create trial contract
            if rec.trial_plan_id and not rec.trial_contract_id:
                contract = self.env['disaster.member.contract'].create({
                    'partner_id': rec.partner_id.id,
                    'plan_id':    rec.trial_plan_id.id,
                    'state':      'trial',
                    'date_start': rec.trial_start_date,
                    'trial_end_date': rec.trial_end_date,
                })
                rec.trial_contract_id = contract
                rec.partner_id.message_post(
                    body=f'🎽 Trial started from Lead: <b>{rec.name}</b>',
                )

    def action_convert(self):
        """Convert trial lead → active member."""
        for rec in self:
            if not rec.partner_id:
                rec.action_start_trial()
            rec.stage = 'converted'
            rec.partner_id.member_stage = 'active'
            if rec.trial_contract_id:
                rec.trial_contract_id.action_activate()
            rec.partner_id.message_post(
                body='🥋 Lead converted to active member!',
            )

    def action_mark_lost(self):
        for rec in self:
            rec.stage = 'lost'

    # ------------------------------------------------------------------
    # On-create: log referral on partner's chatter
    # ------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.referred_by_id:
                rec.referred_by_id.message_post(
                    body=f'📣 Referral lead created: <b>{rec.name}</b>',
                )
        return records
