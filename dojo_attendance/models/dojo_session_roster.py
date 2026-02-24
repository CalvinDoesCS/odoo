# -*- coding: utf-8 -*-
"""
dojo_session_roster.py
----------------------
Per-session booking / waitlist record.

A roster entry captures whether a member has:
  booked       – reserved a spot before the session
  waitlisted   – on the waitlist (session at capacity)
  attended     – actually showed up (checked in)
  no_show      – was booked but did not attend
  cancelled    – booking was cancelled by member or staff

Auto-promotion from waitlist to booked happens when a booked member
cancels and the session is not yet full.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


ROSTER_STATE = [
    ('booked',      'Booked'),
    ('waitlisted',  'Waitlisted'),
    ('attended',    'Attended'),
    ('no_show',     'No Show'),
    ('cancelled',   'Cancelled'),
]

BOOKING_SOURCE = [
    ('member_app', 'Member App'),
    ('kiosk',      'Kiosk'),
    ('staff',      'Staff / Back-office'),
    ('manual',     'Manual'),
]


class DojoSessionRoster(models.Model):
    _name = 'dojo.session.roster'
    _description = 'Session Roster / Booking'
    _order = 'session_id, state, create_date'
    _rec_name = 'member_id'

    session_id = fields.Many2one(
        'disaster.class.session', string='Session',
        required=True, ondelete='cascade', index=True,
    )
    member_id = fields.Many2one(
        'res.partner', string='Member',
        required=True, ondelete='cascade', index=True,
        domain="[('is_member','=',True)]",
    )
    state = fields.Selection(
        ROSTER_STATE, string='Status',
        default='booked', required=True, tracking=True,
    )
    source = fields.Selection(
        BOOKING_SOURCE, string='Booking Source',
        default='staff', required=True,
    )
    booked_at = fields.Datetime(
        string='Booked At', default=fields.Datetime.now, readonly=True,
    )
    checkin_dt = fields.Datetime(string='Check-In Time')
    checkout_dt = fields.Datetime(string='Check-Out Time')
    notes = fields.Char(string='Notes')

    # Denormalised
    session_date = fields.Datetime(
        related='session_id.date_start', store=True, string='Session Date',
    )
    company_id = fields.Many2one(
        'res.company', string='Company',
        default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ('unique_member_session',
         'UNIQUE(session_id, member_id)',
         'This member already has a roster entry for this session.'),
    ]

    # ── Booking logic ────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        """Enforce capacity; auto-waitlist if session is full."""
        for vals in vals_list:
            if vals.get('state', 'booked') == 'booked':
                session = self.env['disaster.class.session'].browse(vals['session_id'])
                booked_count = self.search_count([
                    ('session_id', '=', session.id),
                    ('state', '=', 'booked'),
                ])
                if session.capacity and booked_count >= session.capacity:
                    vals['state'] = 'waitlisted'
        return super().create(vals_list)

    # ── State transitions ────────────────────────────────────────────
    def action_check_in(self):
        for rec in self:
            if rec.state not in ('booked', 'waitlisted'):
                raise UserError(_('Only booked/waitlisted members can be checked in.'))
            rec.write({'state': 'attended', 'checkin_dt': fields.Datetime.now()})
            # Increment partner attendance count
            rec.member_id.sudo().attendance_count += 1
            # Also create a disaster.class.attendance record for back-compat
            self.env['disaster.class.attendance'].sudo().create({
                'session_id': rec.session_id.id,
                'partner_id': rec.member_id.id,
                'check_in': rec.checkin_dt,
            })

    def action_check_out(self):
        for rec in self:
            if rec.state != 'attended':
                raise UserError(_('Member must be checked in to check out.'))
            rec.write({'checkout_dt': fields.Datetime.now()})

    def action_mark_no_show(self):
        self.write({'state': 'no_show'})
        for rec in self:
            rec._notify_guardian_no_show()

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'
            rec._auto_promote_waitlist()

    # ── Waitlist promotion ───────────────────────────────────────────
    def _auto_promote_waitlist(self):
        """When a booking is cancelled, promote next waitlisted member."""
        session = self.session_id
        booked_count = self.search_count([
            ('session_id', '=', session.id),
            ('state', '=', 'booked'),
        ])
        if session.capacity and booked_count < session.capacity:
            next_waitlisted = self.search([
                ('session_id', '=', session.id),
                ('state', '=', 'waitlisted'),
            ], order='create_date asc', limit=1)
            if next_waitlisted:
                next_waitlisted.state = 'booked'
                next_waitlisted.member_id.message_post(
                    body=_('Your waitlist booking for %s has been confirmed!') % session.name
                )

    # ── Guardian notification ────────────────────────────────────────
    def _notify_guardian_no_show(self):
        """Send absence notification to guardian if configured."""
        for rec in self:
            member = rec.member_id
            guardian = member.guardian_id
            if not guardian:
                return
            if member.notify_absence_email and guardian.email:
                self.env['mail.mail'].sudo().create({
                    'subject': _('Absence Notice: %s') % member.name,
                    'body_html': _(
                        '<p>Dear %s,</p>'
                        '<p>We wanted to let you know that <strong>%s</strong> '
                        'was marked as a no-show for the class on <em>%s</em>.</p>'
                        '<p>Please contact us if you have any questions.</p>'
                    ) % (
                        guardian.name,
                        member.name,
                        rec.session_date and rec.session_date.strftime('%A, %B %d at %I:%M %p') or '—',
                    ),
                    'email_to': guardian.email,
                    'auto_delete': True,
                }).send()
