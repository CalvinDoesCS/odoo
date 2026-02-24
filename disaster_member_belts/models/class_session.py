# -*- coding: utf-8 -*-
"""
class_session.py
----------------
Represents a scheduled training class (e.g. Monday 6pm Beginner Karate).
Members check in against a session, auto-incrementing their attendance_count.
"""

from odoo import api, fields, models


CLASS_TYPES = [
    ('beginner',    'Beginner'),
    ('intermediate','Intermediate'),
    ('advanced',    'Advanced'),
    ('all_levels',  'All Levels'),
    ('sparring',    'Sparring'),
    ('weapons',     'Weapons'),
    ('kids',        'Kids'),
    ('private',     'Private Lesson'),
]


class DisasterClassSession(models.Model):
    _name = 'disaster.class.session'
    _description = 'Training Class Session'
    _order = 'date_start desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Class Name',
        required=True,
        tracking=True,
    )
    class_type = fields.Selection(
        selection=CLASS_TYPES,
        string='Class Type',
        default='all_levels',
        required=True,
        tracking=True,
    )
    instructor_id = fields.Many2one(
        comodel_name='res.partner',
        string='Instructor',
        domain="[('is_instructor', '=', True)]",
        tracking=True,
    )
    schedule_id = fields.Many2one(
        comodel_name='disaster.class.schedule',
        string='From Schedule',
        ondelete='set null',
        readonly=True,
        help='Populated automatically when this session is generated from a recurring schedule.',
    )
    course_id = fields.Many2one(
        comodel_name='disaster.course',
        string='Course',
        store=True,
        related='schedule_id.course_id',
        readonly=False,
        index=True,
        help='The course this session belongs to. Auto-set from the schedule; '
             'can be overridden for ad-hoc sessions.',
    )
    date_start = fields.Datetime(
        string='Start Time',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
    )
    date_end = fields.Datetime(
        string='End Time',
        tracking=True,
    )
    duration = fields.Float(
        string='Duration (hrs)',
        compute='_compute_duration',
        store=True,
    )
    capacity = fields.Integer(
        string='Capacity',
        default=20,
    )
    location = fields.Char(
        string='Location / Dojo',
        default='Main Dojo',
    )
    state = fields.Selection(
        selection=[
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='scheduled',
        tracking=True,
    )
    attendance_ids = fields.One2many(
        comodel_name='disaster.class.attendance',
        inverse_name='session_id',
        string='Attendances',
    )
    attendance_count = fields.Integer(
        string='# Checked In',
        compute='_compute_attendance_count',
        store=True,
    )
    notes = fields.Text(string='Notes')

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        for rec in self:
            if rec.date_start and rec.date_end:
                delta = rec.date_end - rec.date_start
                rec.duration = delta.total_seconds() / 3600.0
            else:
                rec.duration = 0.0

    @api.depends('attendance_ids')
    def _compute_attendance_count(self):
        for rec in self:
            rec.attendance_count = len(rec.attendance_ids)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_view_attendances(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Attendances – {self.name}',
            'res_model': 'disaster.class.attendance',
            'view_mode': 'list,form',
            'domain': [('session_id', '=', self.id)],
            'context': {'default_session_id': self.id},
        }

    def action_check_in_member(self):
        """Quick check-in a member from the session form (opens wizard)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Check In Member',
            'res_model': 'disaster.checkin.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_session_id': self.id},
        }

    def action_open_attendance_roster(self):
        """Open the Attendance Roster wizard pre-loaded for this session."""
        self.ensure_one()
        # Sync dojo.session.roster first so Take Roster reflects all expected members
        try:
            self.action_sync_roster()
        except Exception:
            pass  # dojo_attendance may not be installed; roster still loads via other sources
        # Create the wizard and pre-populate it with enrolled students
        wizard = self.env['disaster.attendance.roster'].create({
            'session_id': self.id,
        })
        # Load roster lines immediately
        wizard.action_load_students()
        return {
            'type': 'ir.actions.act_window',
            'name': f'📋 Attendance Roster – {self.name}',
            'res_model': 'disaster.attendance.roster',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
            'context': {
                'default_session_id': self.id,
                'dialog_size': 'extra-large',
            },
        }
