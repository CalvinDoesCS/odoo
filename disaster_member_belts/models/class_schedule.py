# -*- coding: utf-8 -*-
"""
class_schedule.py
-----------------
Recurring class schedule template.
One record = "Monday 6:00 PM Beginner Karate with Sensei Jones".
A daily cron (generate_scheduled_sessions) walks all active schedules and
creates the corresponding disaster.class.session records for today if they
don't already exist.
"""

from datetime import timedelta
from odoo import api, fields, models

DAY_OF_WEEK = [
    ('0', 'Monday'),
    ('1', 'Tuesday'),
    ('2', 'Wednesday'),
    ('3', 'Thursday'),
    ('4', 'Friday'),
    ('5', 'Saturday'),
    ('6', 'Sunday'),
]

CLASS_TYPES = [
    ('beginner',     'Beginner'),
    ('intermediate', 'Intermediate'),
    ('advanced',     'Advanced'),
    ('all_levels',   'All Levels'),
    ('sparring',     'Sparring'),
    ('weapons',      'Weapons'),
    ('kids',         'Kids'),
    ('private',      'Private Lesson'),
]


class DisasterClassSchedule(models.Model):
    _name = 'disaster.class.schedule'
    _description = 'Recurring Class Schedule'
    _order = 'day_of_week, time_start'
    _inherit = ['mail.thread']

    name = fields.Char(
        string='Schedule Name',
        required=True,
        tracking=True,
        help='e.g. "Beginner Monday 6pm"',
    )
    active = fields.Boolean(default=True, tracking=True)

    day_of_week = fields.Selection(
        selection=DAY_OF_WEEK,
        string='Day of Week',
        required=True,
        tracking=True,
    )
    time_start = fields.Float(
        string='Start Time',
        required=True,
        default=18.0,
        help='24-hour decimal (18.5 = 6:30 PM)',
    )
    duration = fields.Float(
        string='Duration (hrs)',
        default=1.0,
        help='Length of the class in hours.',
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
        string='Default Instructor',
        domain="[('is_instructor', '=', True)]",
        tracking=True,
    )
    capacity = fields.Integer(string='Capacity', default=20)
    location = fields.Char(string='Location / Room', default='Main Dojo')

    # Effective date range
    date_from = fields.Date(
        string='Active From',
        default=fields.Date.today,
        required=True,
    )
    date_to = fields.Date(
        string='Active Until',
        help='Leave empty for indefinite.',
    )

    # Linked to course (optional)
    course_id = fields.Many2one(
        comodel_name='disaster.course',
        string='Course',
        ondelete='set null',
    )

    # ---- Computed stats ----------------------------------------
    session_ids = fields.One2many(
        comodel_name='disaster.class.session',
        inverse_name='schedule_id',
        string='Generated Sessions',
    )
    session_count = fields.Integer(
        string='Sessions Generated',
        compute='_compute_session_count',
    )

    time_start_display = fields.Char(
        string='Time',
        compute='_compute_time_display',
    )

    def _compute_session_count(self):
        for rec in self:
            rec.session_count = len(rec.session_ids)

    @api.depends('time_start')
    def _compute_time_display(self):
        for rec in self:
            h = int(rec.time_start)
            m = int(round((rec.time_start - h) * 60))
            ampm = 'AM' if h < 12 else 'PM'
            h12 = h % 12 or 12
            rec.time_start_display = f'{h12}:{m:02d} {ampm}'

    # ---- Actions -----------------------------------------------
    def action_view_sessions(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sessions – {self.name}',
            'res_model': 'disaster.class.session',
            'view_mode': 'list,form',
            'domain': [('schedule_id', '=', self.id)],
            'context': {'default_schedule_id': self.id},
        }

    def action_generate_sessions_manual(self):
        """Manually trigger session generation for the next 7 days."""
        self.ensure_one()
        self._generate_sessions_for_date_range(
            fields.Date.today(),
            fields.Date.today() + timedelta(days=7),
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sessions Generated',
                'message': f'Sessions for the next 7 days have been created for "{self.name}".',
                'type': 'success',
            },
        }

    # ---- Cron entry point -------------------------------------
    @api.model
    def cron_generate_sessions(self):
        """Called daily: generate sessions for the next 2 days."""
        today = fields.Date.today()
        lookahead = today + timedelta(days=2)
        schedules = self.search([
            ('active', '=', True),
            ('date_from', '<=', lookahead),
            '|', ('date_to', '=', False), ('date_to', '>=', today),
        ])
        schedules._generate_sessions_for_date_range(today, lookahead)

    def _generate_sessions_for_date_range(self, date_from, date_to):
        """Create class sessions for every occurrence in [date_from, date_to]."""
        from datetime import datetime, timezone
        Session = self.env['disaster.class.session']

        current = date_from
        while current <= date_to:
            for schedule in self:
                if str(current.weekday()) != schedule.day_of_week:
                    continue
                # Check active range
                if current < schedule.date_from:
                    continue
                if schedule.date_to and current > schedule.date_to:
                    continue

                # Build datetimes (naive UTC-like – Odoo stores Datetime as UTC)
                h = int(schedule.time_start)
                m = int(round((schedule.time_start - h) * 60))
                start_dt = datetime(current.year, current.month, current.day, h, m, 0)
                end_dt = start_dt + timedelta(hours=schedule.duration)

                # Skip if already generated
                existing = Session.search([
                    ('schedule_id', '=', schedule.id),
                    ('date_start', '=', fields.Datetime.to_string(start_dt)),
                ], limit=1)
                if existing:
                    continue

                Session.create({
                    'name': schedule.name,
                    'schedule_id': schedule.id,
                    'class_type': schedule.class_type,
                    'instructor_id': schedule.instructor_id.id or False,
                    'date_start': fields.Datetime.to_string(start_dt),
                    'date_end': fields.Datetime.to_string(end_dt),
                    'capacity': schedule.capacity,
                    'location': schedule.location,
                })
            current += timedelta(days=1)
