from odoo import api, fields, models
from datetime import date, timedelta


class DojoMemberDashboard(models.Model):
    """Extends dojo.member with a belt rank stub and enrollment One2many for the
    instructor dashboard.  Replace current_belt_stub with Many2one('dojo.belt.rank')
    once dojo_belt_progression ships."""

    _inherit = 'dojo.member'

    # Reverse One2many from dojo.class.enrollment so we can filter members
    # by instructor in domain expressions like:
    # [('enrollment_ids.session_id.instructor_profile_id.user_id', '=', uid)]
    enrollment_ids = fields.One2many(
        'dojo.class.enrollment',
        'member_id',
        string='Class Enrollments',
    )

    # TODO: replace with Many2one('dojo.belt.rank') when dojo_belt_progression ships
    current_belt_stub = fields.Char(
        string='Belt Rank',
        compute='_compute_belt_stub',
        help='Placeholder — full belt progression coming in dojo_belt_progression module.',
    )

    def _compute_belt_stub(self):
        for rec in self:
            rec.current_belt_stub = '—'


class DojoInstructorProfile(models.Model):
    """Extends dojo.instructor.profile with live KPI computed fields for the
    instructor dashboard.  All fields are non-stored so they recompute on every
    read (acceptable for a dashboard context)."""

    _inherit = 'dojo.instructor.profile'

    # ── Relations for dashboard embedding ────────────────────────────────
    session_ids = fields.One2many(
        'dojo.class.session', 'instructor_profile_id', string='Sessions',
    )

    session_today_ids = fields.Many2many(
        'dojo.class.session',
        compute='_compute_session_today_ids',
        string="Today's Classes",
    )

    upcoming_session_ids = fields.Many2many(
        'dojo.class.session',
        'instructor_profile_upcoming_rel',
        compute='_compute_upcoming_session_ids',
        string='Upcoming Classes',
    )

    task_ids = fields.Many2many(
        'project.task',
        compute='_compute_task_ids',
        string='My Todos',
    )

    @api.depends('session_ids.start_datetime')
    def _compute_session_today_ids(self):
        today = date.today()
        today_start = fields.Datetime.to_datetime(str(today) + ' 00:00:00')
        today_end = fields.Datetime.to_datetime(str(today) + ' 23:59:59')
        for profile in self:
            profile.session_today_ids = self.env['dojo.class.session'].search([
                ('instructor_profile_id', '=', profile.id),
                ('start_datetime', '>=', today_start),
                ('start_datetime', '<=', today_end),
            ])

    @api.depends('session_ids.start_datetime')
    def _compute_upcoming_session_ids(self):
        today = date.today()
        tomorrow_start = fields.Datetime.to_datetime(
            str(today + timedelta(days=1)) + ' 00:00:00'
        )
        two_weeks_end = fields.Datetime.to_datetime(
            str(today + timedelta(days=14)) + ' 23:59:59'
        )
        for profile in self:
            profile.upcoming_session_ids = self.env['dojo.class.session'].search([
                ('instructor_profile_id', '=', profile.id),
                ('start_datetime', '>=', tomorrow_start),
                ('start_datetime', '<=', two_weeks_end),
            ])

    @api.depends('user_id')
    def _compute_task_ids(self):
        for profile in self:
            if profile.user_id:
                profile.task_ids = self.env['project.task'].search([
                    ('user_ids', 'in', profile.user_id.ids),
                    ('stage_id.fold', '=', False),
                ])
            else:
                profile.task_ids = self.env['project.task']

    # ── Today's sessions ──────────────────────────────────────────────────
    sessions_today_count = fields.Integer(
        string='Sessions Today',
        compute='_compute_instructor_kpis',
    )

    # ── Active students across all open/done sessions ─────────────────────
    students_total_count = fields.Integer(
        string='Total Students',
        compute='_compute_instructor_kpis',
    )

    # ── Fill rate (last 30 days) ──────────────────────────────────────────
    avg_fill_rate = fields.Float(
        string='Avg Fill Rate (%)',
        compute='_compute_instructor_kpis',
        digits=(5, 1),
    )

    # ── Attendance rate (last 30 days) ────────────────────────────────────
    attendance_rate = fields.Float(
        string='Attendance Rate (%)',
        compute='_compute_instructor_kpis',
        digits=(5, 1),
    )

    # Belt rank stub – replaced when dojo_belt_progression ships
    # TODO: update to a real Many2one('dojo.belt.rank') in phase 5
    current_belt_stub = fields.Char(
        string='Belt Rank',
        compute='_compute_belt_stub',
        help='Placeholder until the dojo_belt_progression module is installed.',
    )

    @api.depends('user_id')
    def _compute_belt_stub(self):
        for rec in self:
            rec.current_belt_stub = '—'

    @api.model
    def get_my_profile_data(self):
        """Returns KPI data for the currently logged-in instructor.
        Uses self.env.uid (always correct server-side) so no client-side
        UID lookup is needed."""
        profile = self.search([('user_id', '=', self.env.uid)], limit=1)
        if not profile:
            return False
        return {
            'id': profile.id,
            'name': profile.name,
            'user_id': profile.user_id.id,
            'sessions_today_count': profile.sessions_today_count,
            'students_total_count': profile.students_total_count,
            'avg_fill_rate': profile.avg_fill_rate,
            'attendance_rate': profile.attendance_rate,
        }

    @api.depends('user_id')
    def _compute_instructor_kpis(self):
        """Computes KPI values for each instructor profile.
        Uses ``@api.depends('user_id')`` so the cache is invalidated when
        the profile's user changes; dashboard views will always re-fetch."""
        Session = self.env['dojo.class.session']
        Enrollment = self.env['dojo.class.enrollment']
        AttendanceLog = self.env['dojo.attendance.log']

        today = date.today()
        today_start = fields.Datetime.to_datetime(str(today) + ' 00:00:00')
        today_end = fields.Datetime.to_datetime(str(today) + ' 23:59:59')
        thirty_days_ago = fields.Datetime.to_datetime(
            str(today - timedelta(days=30)) + ' 00:00:00'
        )

        for profile in self:
            # Today's sessions
            today_sessions = Session.search([
                ('instructor_profile_id', '=', profile.id),
                ('start_datetime', '>=', today_start),
                ('start_datetime', '<=', today_end),
            ])
            profile.sessions_today_count = len(today_sessions)

            # Total distinct registered students across all active sessions
            all_sessions = Session.search([
                ('instructor_profile_id', '=', profile.id),
                ('state', 'in', ['open', 'done']),
            ])
            if all_sessions:
                enrolled_members = Enrollment.search([
                    ('session_id', 'in', all_sessions.ids),
                    ('status', '=', 'registered'),
                ]).mapped('member_id')
                profile.students_total_count = len(enrolled_members)
            else:
                profile.students_total_count = 0

            # Fill rate over last 30 days
            recent_sessions = Session.search([
                ('instructor_profile_id', '=', profile.id),
                ('start_datetime', '>=', thirty_days_ago),
                ('state', 'in', ['open', 'done']),
            ])
            if recent_sessions:
                total_capacity = sum(
                    s.capacity for s in recent_sessions if s.capacity > 0
                )
                total_taken = sum(s.seats_taken for s in recent_sessions)
                profile.avg_fill_rate = (
                    (total_taken / total_capacity * 100) if total_capacity else 0.0
                )
            else:
                profile.avg_fill_rate = 0.0

            # Attendance rate over last 30 days
            if recent_sessions:
                logs = AttendanceLog.search([
                    ('session_id', 'in', recent_sessions.ids),
                ])
                if logs:
                    present = len(logs.filtered(lambda l: l.status == 'present'))
                    profile.attendance_rate = present / len(logs) * 100
                else:
                    profile.attendance_rate = 0.0
            else:
                profile.attendance_rate = 0.0

    # ── Admin dashboard data ──────────────────────────────────────────────

    @api.model
    def get_admin_dashboard_data(self):
        """Returns comprehensive dashboard data for admins:
        - Global KPI summary
        - Per-instructor KPIs
        - Dropped/cancelled students (last 60 days)
        - Recent sessions with fill/attendance breakdown
        """
        Session = self.env['dojo.class.session']
        Enrollment = self.env['dojo.class.enrollment']
        AttendanceLog = self.env['dojo.attendance.log']

        today = date.today()
        today_start = fields.Datetime.to_datetime(str(today) + ' 00:00:00')
        today_end = fields.Datetime.to_datetime(str(today) + ' 23:59:59')
        thirty_days_ago = fields.Datetime.to_datetime(
            str(today - timedelta(days=30)) + ' 00:00:00'
        )
        sixty_days_ago = fields.Datetime.to_datetime(
            str(today - timedelta(days=60)) + ' 00:00:00'
        )

        # ── Global KPIs ───────────────────────────────────────────────────
        all_profiles = self.search([])
        active_members = self.env['dojo.member'].search_count([
            ('role', 'in', ['student', 'both']),
            ('membership_state', 'in', ['trial', 'active']),
        ])
        sessions_today = Session.search_count([
            ('start_datetime', '>=', today_start),
            ('start_datetime', '<=', today_end),
        ])

        # Overall fill rate (last 30 days)
        recent_sessions = Session.search([
            ('start_datetime', '>=', thirty_days_ago),
            ('state', 'in', ['open', 'done']),
        ])
        total_capacity = sum(s.capacity for s in recent_sessions if s.capacity > 0)
        total_taken = sum(s.seats_taken for s in recent_sessions)
        overall_fill_rate = (total_taken / total_capacity * 100) if total_capacity else 0.0

        # Overall attendance rate (last 30 days)
        recent_logs = AttendanceLog.search([
            ('session_id', 'in', recent_sessions.ids),
        ]) if recent_sessions else self.env['dojo.attendance.log']
        present_count = len(recent_logs.filtered(lambda l: l.status == 'present'))
        overall_attendance_rate = (
            present_count / len(recent_logs) * 100
        ) if recent_logs else 0.0

        # Dropped students count (last 60 days)
        total_dropped_60d = Enrollment.search_count([
            ('status', '=', 'cancelled'),
            ('session_id.start_datetime', '>=', sixty_days_ago),
        ])

        summary = {
            'total_instructors': len(all_profiles),
            'total_active_students': active_members,
            'sessions_today': sessions_today,
            'overall_fill_rate': round(overall_fill_rate, 1),
            'overall_attendance_rate': round(overall_attendance_rate, 1),
            'total_dropped_60d': total_dropped_60d,
        }

        # ── Per-instructor KPIs ───────────────────────────────────────────
        instructors = []
        for p in all_profiles:
            instructors.append({
                'id': p.id,
                'name': p.name,
                'sessions_today': p.sessions_today_count,
                'students_count': p.students_total_count,
                'fill_rate': round(p.avg_fill_rate, 1),
                'attendance_rate': round(p.attendance_rate, 1),
            })
        instructors.sort(key=lambda x: x['students_count'], reverse=True)

        # ── Dropped / cancelled students (last 60 days) ───────────────────
        dropped_enrollments = Enrollment.search([
            ('status', '=', 'cancelled'),
            ('session_id.start_datetime', '>=', sixty_days_ago),
        ], order='session_id desc', limit=50)

        dropped_students = []
        for e in dropped_enrollments:
            dropped_students.append({
                'member_id': e.member_id.id,
                'member_name': e.member_id.name or '—',
                'class_name': (
                    e.session_id.template_id.name if e.session_id.template_id else '—'
                ),
                'instructor_name': (
                    e.session_id.instructor_profile_id.name
                    if e.session_id.instructor_profile_id else '—'
                ),
                'session_date': (
                    fields.Datetime.to_string(e.session_id.start_datetime)[:10]
                    if e.session_id.start_datetime else '—'
                ),
                'membership_state': e.member_id.membership_state or '—',
            })

        # ── Recent sessions (last 30 days, done/open, up to 40) ──────────
        recent_session_recs = Session.search([
            ('start_datetime', '>=', thirty_days_ago),
            ('state', 'in', ['open', 'done']),
        ], order='start_datetime desc', limit=40)

        recent_sessions_data = []
        for s in recent_session_recs:
            sess_logs = AttendanceLog.search([('session_id', '=', s.id)])
            present = len(sess_logs.filtered(lambda l: l.status == 'present'))
            total_log = len(sess_logs)
            fill = round((s.seats_taken / s.capacity * 100), 1) if s.capacity else 0.0
            att = round((present / total_log * 100), 1) if total_log else None
            recent_sessions_data.append({
                'id': s.id,
                'class_name': s.template_id.name if s.template_id else '—',
                'instructor_name': (
                    s.instructor_profile_id.name if s.instructor_profile_id else '—'
                ),
                'date': (
                    fields.Datetime.to_string(s.start_datetime)[:10]
                    if s.start_datetime else '—'
                ),
                'capacity': s.capacity,
                'enrolled': s.seats_taken,
                'present': present,
                'absent': total_log - present,
                'fill_rate': fill,
                'attendance_rate': att,
                'state': s.state,
            })

        return {
            'summary': summary,
            'instructors': instructors,
            'dropped_students': dropped_students,
            'recent_sessions': recent_sessions_data,
        }
