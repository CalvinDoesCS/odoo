# -*- coding: utf-8 -*-
"""
course.py
---------
A Course / Program that members enroll in.
e.g. "Kids Karate – White to Yellow", "Adult BJJ Fundamentals", "Competition Team".

Each course can have:
  - A lead instructor
  - Required belt rank range
  - Enrolled members (via many2many)
  - Linked schedules (the weekly timetable)
  - Automation thresholds (days absent → alert)
"""

from odoo import api, fields, models

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


class DisasterCourse(models.Model):
    _name = 'disaster.course'
    _description = 'Course / Program'
    _order = 'sequence, name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    sequence = fields.Integer(default=10)
    name = fields.Char(
        string='Course Name',
        required=True,
        tracking=True,
    )
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True, tracking=True)
    color = fields.Integer(string='Color', default=0)

    # ---- Instructor ----------------------------------------
    instructor_id = fields.Many2one(
        comodel_name='res.partner',
        string='Lead Instructor',
        domain="[('is_instructor', '=', True)]",
        tracking=True,
    )
    co_instructor_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='disaster_course_co_instructor_rel',
        column1='course_id',
        column2='partner_id',
        string='Co-Instructors',
        domain="[('is_instructor', '=', True)]",
    )

    # ---- Belt eligibility -----------------------------------
    min_belt_rank = fields.Selection(
        selection=BELT_SELECTION,
        string='Min Belt Rank',
        default='white',
    )
    max_belt_rank = fields.Selection(
        selection=BELT_SELECTION,
        string='Max Belt Rank',
    )

    # ---- Schedule links ------------------------------------
    schedule_ids = fields.One2many(
        comodel_name='disaster.class.schedule',
        inverse_name='course_id',
        string='Class Schedules',
    )
    schedule_count = fields.Integer(
        string='Schedules',
        compute='_compute_schedule_count',
    )

    # ---- Enrolled members ----------------------------------
    enrolled_member_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='disaster_course_member_rel',
        column1='course_id',
        column2='partner_id',
        string='Enrolled Students',
        domain="[('is_member', '=', True)]",
    )
    enrolled_count = fields.Integer(
        string='Enrolled',
        compute='_compute_enrolled_count',
        store=True,
    )

    # Member contracts linked to this course
    contract_ids = fields.One2many(
        comodel_name='disaster.member.contract',
        inverse_name='course_id',
        string='Member Contracts',
    )
    contract_count = fields.Integer(
        string='Contracts',
        compute='_compute_contract_count',
    )

    @api.depends('contract_ids')
    def _compute_contract_count(self):
        for course in self:
            course.contract_count = len(course.contract_ids)

    # ---- Enrollment & eligibility ---------------------------
    open_enrollment = fields.Boolean(
        string='Open Enrollment',
        default=True,
        help='If enabled, any member whose belt rank meets the requirement can '
             'check in to sessions of this course without being explicitly '
             'enrolled.\n\n'
             'If disabled, only members listed in Enrolled Students can check in.',
    )

    # ---- Automation settings --------------------------------
    absent_alert_days = fields.Integer(
        string='Absent Alert (days)',
        default=7,
        help='Create an activity on the instructor when a student has not '
             'attended for this many days. 0 = disabled.',
    )

    # ---- Computed ------------------------------------------
    def _compute_schedule_count(self):
        for c in self:
            c.schedule_count = len(c.schedule_ids)

    @api.depends('enrolled_member_ids')
    def _compute_enrolled_count(self):
        for c in self:
            c.enrolled_count = len(c.enrolled_member_ids)

    # ---- Actions -------------------------------------------
    def action_view_schedules(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Schedules – {self.name}',
            'res_model': 'disaster.class.schedule',
            'view_mode': 'list,form',
            'domain': [('course_id', '=', self.id)],
            'context': {'default_course_id': self.id},
        }

    def action_view_enrolled(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Students – {self.name}',
            'res_model': 'res.partner',
            'view_mode': 'list,kanban,form',
            'domain': [('id', 'in', self.enrolled_member_ids.ids)],
        }

    # ---- Cron: absent student alert ------------------------
    @api.model
    def cron_absent_student_alert(self):
        """
        For each course with absent_alert_days > 0:
        Find enrolled students whose last check-in was more than
        absent_alert_days ago and create a To-Do activity for the instructor.
        """
        from datetime import datetime, timedelta as td
        Attendance = self.env['disaster.class.attendance']
        Activity = self.env['mail.activity']
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not activity_type:
            return

        courses = self.search([
            ('active', '=', True),
            ('absent_alert_days', '>', 0),
            ('instructor_id', '!=', False),
        ])
        for course in courses:
            cutoff = fields.Datetime.now() - td(days=course.absent_alert_days)
            for member in course.enrolled_member_ids:
                last = Attendance.search([
                    ('partner_id', '=', member.id),
                ], order='check_in desc', limit=1)

                if not last or last.check_in < cutoff:
                    # Only create if no open activity already exists
                    existing = Activity.search([
                        ('res_model', '=', 'res.partner'),
                        ('res_id', '=', member.id),
                        ('activity_type_id', '=', activity_type.id),
                        ('note', 'ilike', 'absent'),
                    ], limit=1)
                    if existing:
                        continue

                    days_absent = (fields.Datetime.now() - last.check_in).days if last else course.absent_alert_days
                    Activity.create({
                        'res_model_id': self.env['ir.model']._get('res.partner').id,
                        'res_id': member.id,
                        'activity_type_id': activity_type.id,
                        'summary': f'Student absent {days_absent} days – {course.name}',
                        'note': f'{member.name} has not attended {course.name} in {days_absent} days. '
                                f'Please follow up.',
                        'date_deadline': fields.Date.today(),
                        'user_id': course.instructor_id.user_ids[:1].id
                                   if course.instructor_id.user_ids else self.env.uid,
                    })
