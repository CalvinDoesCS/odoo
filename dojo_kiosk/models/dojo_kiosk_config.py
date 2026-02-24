# -*- coding: utf-8 -*-
"""
dojo_kiosk_config.py
--------------------
Kiosk configuration model + all JSON-RPC methods called by the OWL app.

Two kiosk views are served:
  • Student / Member view  – badge barcode scan + name search → check-in
  • Staff / Instructor view – PIN-protected launcher with management tiles

All data methods use sudo() so they work regardless of the session user's
access rights (kiosk runs as the currently logged-in Odoo user which may be
an instructor-role account).
"""

import logging
from datetime import date, datetime, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

BELT_COLORS = {
    'white':  '#f8f9fa',
    'yellow': '#ffc107',
    'orange': '#fd7e14',
    'green':  '#28a745',
    'blue':   '#007bff',
    'purple': '#6f42c1',
    'brown':  '#795548',
    'red':    '#dc3545',
    'black':  '#212529',
}


class DojoKioskConfig(models.Model):
    _name = 'dojo.kiosk.config'
    _description = 'Dojo Kiosk Configuration'
    _inherit = ['mail.thread']

    name = fields.Char(string='Kiosk Name', required=True, default='Front Desk Kiosk')
    company_id = fields.Many2one(
        'res.company', string='Dojo', default=lambda self: self.env.company,
    )
    active = fields.Boolean(default=True)

    # ── Display settings ─────────────────────────────────────────────────────
    idle_timeout_sec = fields.Integer(
        string='Idle Timeout (seconds)', default=45,
        help='Return to welcome screen after this many seconds of inactivity.',
    )
    welcome_message = fields.Char(
        string='Welcome Message',
        default='Welcome to the Dojo! Scan your badge or search your name to check in.',
    )
    success_message = fields.Char(
        string='Success Message', default='You\'re checked in! Have a great class!',
    )
    show_belt_rank = fields.Boolean(string='Show Belt Rank on Check-In', default=True)
    show_attendance_count = fields.Boolean(string='Show Class Count on Check-In', default=True)
    allow_walk_in = fields.Boolean(
        string='Allow Walk-in (no prior booking required)', default=True,
    )

    # ── Staff panel ───────────────────────────────────────────────────────────
    staff_pin = fields.Char(
        string='Staff PIN', default='1234',
        help='PIN instructors enter to access the staff management panel.',
    )

    # ── Session override ──────────────────────────────────────────────────────
    default_session_id = fields.Many2one(
        'disaster.class.session', string='Default Session (override)',
        domain="[('state', 'in', ['scheduled', 'in_progress'])]",
        help='Force check-ins to this session. Leave blank to auto-detect today\'s session.',
    )

    # =========================================================================
    # Helper: get today's sessions
    # =========================================================================
    def _get_today_sessions(self):
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = datetime.combine(date.today(), datetime.max.time())
        sessions = self.env['disaster.class.session'].sudo().search([
            ('date_start', '>=', str(today_start)),
            ('date_start', '<=', str(today_end)),
            ('state', 'not in', ['cancelled', 'done']),
        ], order='date_start asc')
        return sessions

    def _session_dict(self, session):
        """Serialize a session to a kiosk-safe dict."""
        return {
            'id': session.id,
            'name': session.name or '',
            'time': session.date_start.strftime('%I:%M %p') if session.date_start else '',
            'instructor': session.instructor_id.name if session.instructor_id else '',
            'state': session.state or '',
            'capacity': session.capacity or 0,
            'booked_count': session.booked_count if hasattr(session, 'booked_count') else 0,
            'attendance_count': len(session.attendance_ids) if hasattr(session, 'attendance_ids') else 0,
            'course': session.course_id.name if session.course_id else '',
        }

    def _partner_dict(self, partner, config=None):
        """Serialize a member partner to a kiosk-safe dict."""
        belt = partner.belt_rank or 'white'
        return {
            'id': partner.id,
            'name': partner.name or '',
            'belt_rank': belt if (config.show_belt_rank if config else True) else '',
            'belt_color': BELT_COLORS.get(belt, '#ccc'),
            'attendance_count': partner.attendance_count if (config.show_attendance_count if config else True) else 0,
            'avatar_url': f'/web/image/res.partner/{partner.id}/image_128',
            'member_stage': partner.member_stage or '',
        }

    # =========================================================================
    # API: Student view data
    # =========================================================================
    @api.model
    def kiosk_get_welcome_data(self):
        """Return config + today's sessions for the student welcome screen."""
        config = self.search([], limit=1)
        sessions = self._get_today_sessions()
        return {
            'welcome_message': config.welcome_message if config else 'Welcome!',
            'idle_timeout_sec': config.idle_timeout_sec if config else 45,
            'sessions': [self._session_dict(s) for s in sessions],
            'config_id': config.id if config else False,
        }

    @api.model
    def kiosk_search_members(self, query, limit=12):
        """Search members by name for the name-search check-in flow."""
        if not query or len(query.strip()) < 2:
            return []
        members = self.env['res.partner'].sudo().search([
            ('is_member', '=', True),
            ('member_stage', 'in', ['active', 'trial']),
            ('name', 'ilike', query.strip()),
        ], limit=limit, order='name asc')
        config = self.search([], limit=1)
        return [self._partner_dict(p, config) for p in members]

    @api.model
    def kiosk_checkin_barcode(self, barcode, session_id=None):
        """
        Check in a member using their badge barcode.
        Returns a result dict for the kiosk success/error screen.
        """
        config = self.search([], limit=1)
        partner = self.env['res.partner'].sudo().search([
            ('member_barcode', '=', str(barcode).strip()),
            ('is_member', '=', True),
        ], limit=1)
        if not partner:
            return {'success': False, 'error': 'Badge not recognised. Please see a staff member.'}
        return self._do_checkin(partner, session_id, config)

    @api.model
    def kiosk_checkin_partner(self, partner_id, session_id=None):
        """
        Check in a member by partner ID (from name-search selection).
        """
        config = self.search([], limit=1)
        partner = self.env['res.partner'].sudo().browse(int(partner_id))
        if not partner.exists() or not partner.is_member:
            return {'success': False, 'error': 'Member not found.'}
        return self._do_checkin(partner, session_id, config)

    def _do_checkin(self, partner, session_id, config):
        """Core check-in logic shared by barcode and partner-id flows."""
        # Resolve which session to check into
        if not session_id:
            if config and config.default_session_id:
                session_id = config.default_session_id.id
            else:
                # Auto-pick: first in-progress session today, else first scheduled
                today_sessions = self._get_today_sessions()
                in_progress = today_sessions.filtered(lambda s: s.state == 'in_progress')
                target = in_progress[:1] or today_sessions[:1]
                session_id = target.id if target else None

        if not session_id:
            # No session at all — just acknowledge check-in without roster
            _logger.info("[dojo_kiosk] Walk-in check-in for %s (no session)", partner.name)
            return {
                'success': True,
                'partner': self._partner_dict(partner, config),
                'session_name': 'General Check-In',
                'message': config.success_message if config else 'Welcome!',
                'already_in': False,
            }

        session = self.env['disaster.class.session'].sudo().browse(int(session_id))
        if not session.exists():
            return {'success': False, 'error': 'Session not found.'}

        # Check if already attended
        existing_attendance = self.env['disaster.class.attendance'].sudo().search([
            ('session_id', '=', session.id),
            ('partner_id', '=', partner.id),
        ], limit=1)
        if existing_attendance:
            return {
                'success': True,
                'already_in': True,
                'partner': self._partner_dict(partner, config),
                'session_name': session.name or '',
                'message': f'Already checked in to {session.name}!',
            }

        # Create attendance record
        self.env['disaster.class.attendance'].sudo().create({
            'session_id': session.id,
            'partner_id': partner.id,
            'check_in': fields.Datetime.now(),
        })

        # Also update roster entry if present
        roster_entry = self.env['dojo.session.roster'].sudo().search([
            ('session_id', '=', session.id),
            ('member_id', '=', partner.id),
            ('state', 'in', ['booked', 'waitlisted']),
        ], limit=1)
        if roster_entry:
            roster_entry.write({'state': 'attended', 'checkin_dt': fields.Datetime.now()})
        elif config and config.allow_walk_in:
            # Walk-in: add to roster as attended
            try:
                self.env['dojo.session.roster'].sudo().create({
                    'session_id': session.id,
                    'member_id': partner.id,
                    'state': 'attended',
                    'source': 'kiosk',
                    'checkin_dt': fields.Datetime.now(),
                })
            except Exception:
                pass  # roster entry optional

        # Mark session in_progress if still scheduled
        if session.state == 'scheduled':
            session.write({'state': 'in_progress'})

        _logger.info("[dojo_kiosk] Checked in %s to session %s", partner.name, session.name)
        return {
            'success': True,
            'already_in': False,
            'partner': self._partner_dict(partner, config),
            'session_name': session.name or '',
            'message': config.success_message if config else 'Checked In!',
        }

    # =========================================================================
    # API: Staff panel
    # =========================================================================
    @api.model
    def kiosk_verify_staff_pin(self, pin):
        """Verify the staff PIN. Returns {ok: True/False}."""
        config = self.search([], limit=1)
        expected = str(config.staff_pin) if config and config.staff_pin else '1234'
        return {'ok': str(pin) == expected}

    @api.model
    def kiosk_get_staff_data(self):
        """Return today's sessions + recent check-ins for the staff panel."""
        sessions = self._get_today_sessions()
        session_list = [self._session_dict(s) for s in sessions]

        # Recent check-ins (last 20 across all today's sessions)
        today_start = datetime.combine(date.today(), datetime.min.time())
        recent = self.env['disaster.class.attendance'].sudo().search([
            ('create_date', '>=', str(today_start)),
        ], order='create_date desc', limit=20)
        recent_list = []
        for r in recent:
            recent_list.append({
                'member_name': r.partner_id.name if r.partner_id else '',
                'session_name': r.session_id.name if r.session_id else '',
                'time': r.check_in.strftime('%I:%M %p') if r.check_in else '',
                'belt_rank': r.partner_id.belt_rank if r.partner_id else '',
                'belt_color': BELT_COLORS.get(r.partner_id.belt_rank or '', '#ccc'),
            })

        # Stats
        active_count = self.env['res.partner'].sudo().search_count([
            ('is_member', '=', True), ('member_stage', '=', 'active'),
        ])
        trial_count = self.env['res.partner'].sudo().search_count([
            ('is_member', '=', True), ('member_stage', '=', 'trial'),
        ])
        checkins_today = self.env['disaster.class.attendance'].sudo().search_count([
            ('create_date', '>=', str(today_start)),
        ])

        return {
            'sessions': session_list,
            'recent_checkins': recent_list,
            'stats': {
                'active_members': active_count,
                'trial_members': trial_count,
                'checkins_today': checkins_today,
            },
        }

    # =========================================================================
    # API: Roster view (new main screen)
    # =========================================================================

    @api.model
    def kiosk_get_roster_data(self):
        """Return today's sessions with each member's check-in status."""
        sessions = self._get_today_sessions()
        result = []
        for session in sessions:
            members = []
            try:
                with self.env.cr.savepoint():
                    roster = self.env['dojo.session.roster'].sudo().search([
                        ('session_id', '=', session.id),
                    ])
                    for entry in roster:
                        partner = entry.member_id
                        attendance = self.env['disaster.class.attendance'].sudo().search([
                            ('session_id', '=', session.id),
                            ('partner_id', '=', partner.id),
                        ], limit=1)
                        members.append({
                            'id': partner.id,
                            'name': partner.name or '',
                            'avatar_url': f'/web/image/res.partner/{partner.id}/image_128',
                            'belt_rank': partner.belt_rank or '',
                            'belt_color': BELT_COLORS.get(partner.belt_rank or '', '#888'),
                            'is_checked_in': bool(attendance),
                            'attendance_id': attendance.id if attendance else False,
                            'roster_id': entry.id,
                            'roster_state': entry.state or 'booked',
                        })
            except Exception:
                pass

            s = self._session_dict(session)
            # Add end time
            try:
                s['time_end'] = session.date_end.strftime('%I:%M %p') if session.date_end else ''
            except Exception:
                s['time_end'] = ''
            s['members'] = members
            result.append(s)
        return result

    @api.model
    def kiosk_get_member_detail(self, partner_id):
        """Return full member detail for the instructor popup."""
        partner = self.env['res.partner'].sudo().browse(int(partner_id))
        if not partner.exists():
            return {'error': 'Member not found'}

        belt = partner.belt_rank or 'white'
        issues = []

        # Check contract/membership issues
        try:
            with self.env.cr.savepoint():
                contract = self.env['disaster.member.contract'].sudo().search([
                    ('partner_id', '=', partner.id),
                ], order='id desc', limit=1)
                if contract:
                    today = date.today()
                    if hasattr(contract, 'date_end') and contract.date_end and contract.date_end < today:
                        issues.append('Membership Expired')
                    if hasattr(contract, 'state') and contract.state == 'on_hold':
                        issues.append('Membership On Hold')
        except Exception:
            pass

        # Today's sessions this member is on
        today_sessions = []
        today_start = datetime.combine(date.today(), datetime.min.time())
        try:
            with self.env.cr.savepoint():
                roster_entries = self.env['dojo.session.roster'].sudo().search([
                    ('member_id', '=', partner.id),
                ])
                for entry in roster_entries:
                    sess = entry.session_id
                    if not sess.date_start or sess.date_start.date() != date.today():
                        continue
                    attendance = self.env['disaster.class.attendance'].sudo().search([
                        ('session_id', '=', sess.id),
                        ('partner_id', '=', partner.id),
                    ], limit=1)
                    try:
                        time_range = sess.date_start.strftime('%I:%M %p')
                        if sess.date_end:
                            time_range += ' - ' + sess.date_end.strftime('%I:%M %p')
                    except Exception:
                        time_range = ''
                    today_sessions.append({
                        'session_id': sess.id,
                        'session_name': sess.name or '',
                        'time': time_range,
                        'roster_id': entry.id,
                        'is_checked_in': bool(attendance),
                        'attendance_id': attendance.id if attendance else False,
                        'check_in_time': attendance.check_in.strftime('%I:%M %p') if attendance and attendance.check_in else '',
                    })
        except Exception:
            pass

        # Course enrollments
        courses = []
        try:
            with self.env.cr.savepoint():
                enrollments = self.env['disaster.course'].sudo().search([
                    ('member_ids', 'in', [partner.id]),
                ])
                for course in enrollments:
                    att_count = self.env['disaster.class.attendance'].sudo().search_count([
                        ('partner_id', '=', partner.id),
                        ('session_id.course_id', '=', course.id),
                    ])
                    courses.append({
                        'name': course.name or '',
                        'attendance': att_count,
                    })
        except Exception:
            pass

        return {
            'id': partner.id,
            'name': partner.name or '',
            'avatar_url': f'/web/image/res.partner/{partner.id}/image_128',
            'belt_rank': belt,
            'belt_color': BELT_COLORS.get(belt, '#888'),
            'attendance_count': partner.attendance_count if hasattr(partner, 'attendance_count') else 0,
            'member_stage': partner.member_stage or '',
            'issues': issues,
            'today_sessions': today_sessions,
            'courses': courses,
        }

    @api.model
    def kiosk_add_to_roster(self, partner_id, session_id):
        """Add a member to a session roster."""
        try:
            existing = self.env['dojo.session.roster'].sudo().search([
                ('session_id', '=', int(session_id)),
                ('member_id', '=', int(partner_id)),
            ], limit=1)
            if existing:
                return {'ok': True, 'already_exists': True}
            self.env['dojo.session.roster'].sudo().create({
                'session_id': int(session_id),
                'member_id': int(partner_id),
                'source': 'kiosk',
            })
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @api.model
    def kiosk_remove_from_roster(self, roster_id):
        """Remove a member from a session roster."""
        try:
            entry = self.env['dojo.session.roster'].sudo().browse(int(roster_id))
            if entry.exists():
                entry.unlink()
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    @api.model
    def kiosk_checkout(self, attendance_id):
        """Mark a check-in record as checked out (set check_out to now)."""
        try:
            att = self.env['disaster.class.attendance'].sudo().browse(int(attendance_id))
            if att.exists() and not att.check_out:
                att.write({'check_out': fields.Datetime.now()})
            return {'ok': True}
        except Exception as e:
            return {'ok': False, 'error': str(e)}
