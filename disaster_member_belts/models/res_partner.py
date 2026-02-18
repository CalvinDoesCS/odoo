# -*- coding: utf-8 -*-
"""
res_partner.py
--------------
Extends res.partner with:

  is_member         – flag marking this contact as a dojo member
  is_instructor     – flag marking this contact as an instructor
  member_stage      – lifecycle: lead → trial → active → inactive
  belt_rank         – selection field following the standard belt progression
  attendance_count  – auto-incremented via disaster.class.attendance records
  ready_for_test    – computed boolean; True when attendance_count meets or
                      exceeds the threshold defined in disaster.belt.rank.config
  contract_ids      – all membership contracts for this partner
  active_contract_id– the current active/trial contract
  member_barcode    – barcode / badge ID for kiosk check-in (unique)
  kiosk_pin         – numeric PIN (4-6 digits) for kiosk check-in
"""

import re
from random import choice
from string import digits
from odoo import api, fields, models
from odoo.exceptions import ValidationError


BELT_SELECTION = [
    ('white',  'White'),
    ('yellow', 'Yellow'),
    ('orange', 'Orange'),
    ('green',  'Green'),
    ('blue',   'Blue'),
    ('purple', 'Purple'),
    ('brown',  'Brown'),
    ('red',    'Red'),
    ('black',  'Black'),
]

# Ordered list of rank keys – used by the Promote wizard to find the next rank.
BELT_ORDER = [r[0] for r in BELT_SELECTION]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # ------------------------------------------------------------------
    # Member identity flags
    # ------------------------------------------------------------------
    is_member = fields.Boolean(
        string='Is Member',
        default=False,
        tracking=True,
        help='Tick to mark this contact as a dojo member.',
    )
    is_instructor = fields.Boolean(
        string='Is Instructor',
        default=False,
        tracking=True,
    )
    instructor_specializations = fields.Char(
        string='Specializations',
        help='e.g. Karate, BJJ, Kids Classes',
    )
    instructor_bio = fields.Text(
        string='Instructor Bio',
    )
    instructor_belt_rank = fields.Selection(
        selection=BELT_SELECTION,
        string="Instructor's Belt Rank",
    )
    # Members supervised / assigned to this instructor
    assigned_member_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='disaster_instructor_member_rel',
        column1='instructor_id',
        column2='member_id',
        string='Assigned Students',
        domain="[('is_member', '=', True)]",
    )
    assigned_member_count = fields.Integer(
        string='Assigned Students',
        compute='_compute_instructor_stats',
    )
    # Courses led by this instructor
    led_course_ids = fields.One2many(
        comodel_name='disaster.course',
        inverse_name='instructor_id',
        string='Courses Led',
    )
    led_course_count = fields.Integer(
        string='Courses Led',
        compute='_compute_instructor_stats',
    )
    # Sessions taught by this instructor
    session_instructor_ids = fields.One2many(
        comodel_name='disaster.class.session',
        inverse_name='instructor_id',
        string='Sessions Taught',
    )
    sessions_taught_count = fields.Integer(
        string='Sessions Taught',
        compute='_compute_instructor_stats',
    )
    member_stage = fields.Selection(
        selection=[
            ('lead',     'Lead / Prospect'),
            ('trial',    'Trial'),
            ('active',   'Active Member'),
            ('inactive', 'Inactive'),
        ],
        string='Member Stage',
        default='lead',
        tracking=True,
        index=True,
    )
    join_date = fields.Date(
        string='Join Date',
        tracking=True,
    )

    # ------------------------------------------------------------------
    # Kiosk identification – barcode / PIN
    # ------------------------------------------------------------------
    member_barcode = fields.Char(
        string='Badge / Barcode ID',
        copy=False,
        index=True,
        help='Scan this barcode on the kiosk to check in. '
             'Generate one from the Attendance/Point-of-Sale badge view.',
    )
    kiosk_pin = fields.Char(
        string='Kiosk PIN',
        copy=False,
        help='4-digit PIN the member uses to check in at the kiosk.',
    )

    emergency_contact = fields.Char(string='Emergency Contact')
    emergency_phone = fields.Char(string='Emergency Phone')
    date_of_birth = fields.Date(string='Date of Birth')
    age = fields.Integer(string='Age', compute='_compute_age')

    # ------------------------------------------------------------------
    # Contract fields
    # ------------------------------------------------------------------
    member_contract_ids = fields.One2many(
        comodel_name='disaster.member.contract',
        inverse_name='partner_id',
        string='Member Contracts',
    )
    active_contract_id = fields.Many2one(
        comodel_name='disaster.member.contract',
        string='Active Contract',
        compute='_compute_active_contract',
        store=True,
    )
    contract_count = fields.Integer(
        string='Contracts',
        compute='_compute_contract_count',
    )
    plan_id = fields.Many2one(
        comodel_name='disaster.membership.plan',
        string='Membership Plan',
        related='active_contract_id.plan_id',
        store=True,
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Belt-rank fields
    # ------------------------------------------------------------------
    belt_rank = fields.Selection(
        selection=BELT_SELECTION,
        string='Belt Rank',
        default='white',
        tracking=True,
        help='Current belt rank of this member.',
    )

    attendance_count = fields.Integer(
        string='Attendance Count',
        default=0,
        tracking=True,
        help='Auto-incremented each time a class attendance record is created.',
    )

    attendance_ids = fields.One2many(
        comodel_name='disaster.class.attendance',
        inverse_name='partner_id',
        string='Attendance Records',
    )

    ready_for_test = fields.Boolean(
        string='Ready for Test',
        compute='_compute_ready_for_test',
        store=True,
        help='True when the member has attended enough sessions to be tested '
             'for promotion to the next rank.  Thresholds are configurable in '
             'Configuration → Belt Rank Thresholds.',
    )

    next_belt_rank = fields.Char(
        string='Next Belt Rank',
        compute='_compute_next_belt_rank',
    )

    # ------------------------------------------------------------------
    # Computed fields
    # ------------------------------------------------------------------
    def _compute_instructor_stats(self):
        for p in self:
            p.assigned_member_count = len(p.assigned_member_ids)
            p.led_course_count = len(p.led_course_ids)
            p.sessions_taught_count = len(p.session_instructor_ids)

    @api.depends('belt_rank', 'attendance_count')
    def _compute_ready_for_test(self):
        Config = self.env['disaster.belt.rank.config']
        for partner in self:
            if not partner.belt_rank:
                partner.ready_for_test = False
                continue
            config = Config.search(
                [('rank', '=', partner.belt_rank)], limit=1
            )
            threshold = config.min_attendance if config else 10
            partner.ready_for_test = partner.attendance_count >= threshold

    @api.depends('belt_rank')
    def _compute_next_belt_rank(self):
        for partner in self:
            if partner.belt_rank and partner.belt_rank in BELT_ORDER:
                idx = BELT_ORDER.index(partner.belt_rank)
                if idx < len(BELT_ORDER) - 1:
                    next_key = BELT_ORDER[idx + 1]
                    partner.next_belt_rank = dict(BELT_SELECTION).get(next_key, '')
                else:
                    partner.next_belt_rank = 'Already at highest rank'
            else:
                partner.next_belt_rank = ''

    @api.depends('date_of_birth')
    def _compute_age(self):
        from datetime import date
        today = date.today()
        for partner in self:
            if partner.date_of_birth:
                dob = partner.date_of_birth
                partner.age = today.year - dob.year - (
                    (today.month, today.day) < (dob.month, dob.day)
                )
            else:
                partner.age = 0

    @api.depends('member_contract_ids.state')
    def _compute_active_contract(self):
        for partner in self:
            active = partner.member_contract_ids.filtered(
                lambda c: c.state in ('trial', 'active')
            ).sorted('date_start', reverse=True)[:1]
            partner.active_contract_id = active

    def _compute_contract_count(self):
        for partner in self:
            partner.contract_count = len(partner.member_contract_ids)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('kiosk_pin')
    def _check_kiosk_pin(self):
        for partner in self:
            if partner.kiosk_pin:
                if not partner.kiosk_pin.isdigit() or len(partner.kiosk_pin) != 4:
                    raise ValidationError(
                        'Kiosk PIN must be exactly 4 digits (numbers only).'
                    )

    @api.constrains('member_barcode')
    def _check_member_barcode(self):
        for partner in self:
            if partner.member_barcode:
                dup = self.search([
                    ('member_barcode', '=', partner.member_barcode),
                    ('id', '!=', partner.id),
                ], limit=1)
                if dup:
                    raise ValidationError(
                        f'Badge/Barcode "{partner.member_barcode}" is already '
                        f'assigned to {dup.name}.'
                    )

    # ------------------------------------------------------------------
    # Barcode generation & badge printing
    # ------------------------------------------------------------------
    def action_generate_member_barcode(self):
        """Generate a random 12-digit barcode for this member (EAN-13-style prefix 041)."""
        for partner in self:
            while True:
                code = '041' + ''.join(choice(digits) for _ in range(9))
                if not self.search([('member_barcode', '=', code)], limit=1):
                    partner.member_barcode = code
                    break

    def action_print_member_badge(self):
        """Return the member badge PDF report action for this partner.
        config=False skips the document-layout configurator that would
        otherwise intercept the action and show an invoice-style setup page.
        """
        self.ensure_one()
        return self.env.ref(
            'disaster_member_belts.action_report_member_badge'
        ).report_action(self, config=False)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_view_attendance(self):
        """Open the list of class attendance records for this member."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Attendance – {self.name}',
            'res_model': 'disaster.class.attendance',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_view_contracts(self):
        """Open contracts for this member."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Contracts – {self.name}',
            'res_model': 'disaster.member.contract',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def action_open_promote_wizard(self):
        """Open the promotion confirmation wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Promote Belt Rank',
            'res_model': 'disaster.promote.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_current_rank': self.belt_rank,
            },
        }

    def action_view_assigned_students(self):
        """Instructor: open list of assigned students."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Students – {self.name}',
            'res_model': 'res.partner',
            'view_mode': 'list,kanban,form',
            'domain': [('id', 'in', self.assigned_member_ids.ids)],
        }

    def action_view_led_courses(self):
        """Instructor: open list of courses they lead."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Courses – {self.name}',
            'res_model': 'disaster.course',
            'view_mode': 'list,form',
            'domain': [('instructor_id', '=', self.id)],
            'context': {'default_instructor_id': self.id},
        }

    def action_view_sessions_taught(self):
        """Instructor: open list of sessions where they were instructor."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sessions Taught – {self.name}',
            'res_model': 'disaster.class.session',
            'view_mode': 'list,form',
            'domain': [('instructor_id', '=', self.id)],
        }

    def action_view_enrolled_courses(self):
        """Member: open courses they are enrolled in."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Courses – {self.name}',
            'res_model': 'disaster.course',
            'view_mode': 'list,form',
            'domain': [('enrolled_member_ids', 'in', [self.id])],
        }
