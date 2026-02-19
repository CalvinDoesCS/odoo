# -*- coding: utf-8 -*-
"""
kiosk.py
--------
Public-facing kiosk routes for dojo check-in.
No login required — designed for a dedicated touchscreen tablet.

Student routes
--------------
GET  /dojo/kiosk                        – main student check-in screen
POST /dojo/kiosk/lookup                 – JSON: barcode / PIN lookup
POST /dojo/kiosk/search                 – JSON: name search
POST /dojo/kiosk/member_info            – JSON: member's today sessions + history
POST /dojo/kiosk/checkin                – JSON: check a member into a session
GET  /dojo/kiosk/exit                   – PIN-protected exit back to backend

Instructor mode routes
----------------------
GET  /dojo/kiosk/instructor             – instructor dashboard (PIN-gated on client)
POST /dojo/kiosk/instructor/auth        – JSON: verify instructor PIN
POST /dojo/kiosk/instructor/session_action – JSON: start / end / cancel session
POST /dojo/kiosk/instructor/attendees   – JSON: live attendance list for a session
POST /dojo/kiosk/instructor/manual_checkin – JSON: staff manually checks in a student
"""

import logging
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)

KIOSK_PIN_PARAM        = 'disaster_member_belts.kiosk_exit_pin'
KIOSK_PIN_DEFAULT      = '1234'
INSTRUCTOR_PIN_PARAM   = 'disaster_member_belts.kiosk_instructor_pin'
INSTRUCTOR_PIN_DEFAULT = '9999'

# Belt rank order — used for eligibility comparisons.
# Index 0 = lowest, index 8 = highest.
BELT_ORDER = ['white', 'yellow', 'orange', 'green', 'blue', 'purple', 'brown', 'red', 'black']


class DojoKiosk(http.Controller):

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------
    def _get_kiosk_pin(self):
        return request.env['ir.config_parameter'].sudo().get_param(
            KIOSK_PIN_PARAM, KIOSK_PIN_DEFAULT
        )

    def _get_instructor_pin(self):
        return request.env['ir.config_parameter'].sudo().get_param(
            INSTRUCTOR_PIN_PARAM, INSTRUCTOR_PIN_DEFAULT
        )

    def _get_active_sessions(self):
        """Return today's scheduled/in-progress sessions."""
        today_start = fields.Datetime.now().replace(hour=0, minute=0, second=0)
        today_end   = fields.Datetime.now().replace(hour=23, minute=59, second=59)
        return request.env['disaster.class.session'].sudo().search([
            ('state', 'in', ['scheduled', 'in_progress']),
            ('date_start', '>=', today_start),
            ('date_start', '<=', today_end),
        ], order='date_start asc')

    def _get_all_today_sessions(self):
        """Return ALL of today's sessions (including done/cancelled) for instructor view."""
        today_start = fields.Datetime.now().replace(hour=0, minute=0, second=0)
        today_end   = fields.Datetime.now().replace(hour=23, minute=59, second=59)
        return request.env['disaster.class.session'].sudo().search([
            ('date_start', '>=', today_start),
            ('date_start', '<=', today_end),
        ], order='date_start asc')

    def _session_eligibility(self, s, partner):
        """
        Returns (eligible: bool, reason: str) for a given session + member.
        Checks:
          1. Course minimum belt rank
          2. Enrollment requirement (when open_enrollment=False)
        Both checks are skipped when the session has no linked course.
        """
        course = s.course_id
        if not course:
            return True, ''

        member_belt = partner.belt_rank or 'white'

        # Belt rank check
        if course.min_belt_rank:
            min_idx = BELT_ORDER.index(course.min_belt_rank) if course.min_belt_rank in BELT_ORDER else 0
            mbr_idx = BELT_ORDER.index(member_belt) if member_belt in BELT_ORDER else 0
            if mbr_idx < min_idx:
                label = course.min_belt_rank.capitalize()
                return False, f'Requires {label} belt'

        # Enrollment check
        if not course.open_enrollment and course.enrolled_member_ids:
            if partner not in course.enrolled_member_ids:
                return False, 'Enrollment required'

        return True, ''

    def _session_to_dict(self, s, partner=None):
        eligible = True
        reason   = ''
        if partner:
            eligible, reason = self._session_eligibility(s, partner)
        return {
            'id':        s.id,
            'name':      s.name,
            'type':      s.class_type or '',
            'time':      fields.Datetime.context_timestamp(
                             s, s.date_start).strftime('%I:%M %p') if s.date_start else '',
            'state':     s.state,
            'capacity':  s.capacity,
            'count':     s.attendance_count,
            'instructor': s.instructor_id.name if s.instructor_id else '',
            'location':  s.location or '',
            'course':    s.course_id.name if s.course_id else '',
            'eligible':  eligible,
            'reason':    reason,
        }

    # ------------------------------------------------------------------
    # Main student check-in screen
    # ------------------------------------------------------------------
    @http.route(['/dojo/kiosk', '/dojo/kiosk/<int:session_id>'],
                type='http', auth='public', website=True, sitemap=False)
    def kiosk_main(self, session_id=None, **kwargs):
        sessions = self._get_active_sessions()

        selected_session = None
        if session_id:
            selected_session = request.env['disaster.class.session'].sudo().browse(session_id)
            if not selected_session.exists():
                selected_session = None
        if not selected_session and sessions:
            selected_session = sessions[0]

        return request.render('disaster_member_belts.kiosk_main', {
            'sessions': sessions,
            'selected_session': selected_session,
        })

    # ------------------------------------------------------------------
    # JSON: barcode / PIN lookup  (new)
    # ------------------------------------------------------------------
    @http.route('/dojo/kiosk/lookup', type='jsonrpc', auth='public', website=True,
                sitemap=False, methods=['POST'])
    def kiosk_lookup(self, mode='barcode', value='', **kwargs):
        """
        Look up a member by barcode or PIN.
        mode  : 'barcode' | 'pin'
        value : the raw barcode string or PIN digits
        Returns the same member dict that /dojo/kiosk/search uses.
        """
        value = (value or '').strip()
        if not value:
            return {'error': 'empty'}

        if mode == 'barcode':
            partner = request.env['res.partner'].sudo().search([
                ('is_member', '=', True),
                ('member_barcode', '=', value),
            ], limit=1)
        elif mode == 'pin':
            partner = request.env['res.partner'].sudo().search([
                ('is_member', '=', True),
                ('kiosk_pin', '=', value),
            ], limit=1)
        else:
            return {'error': 'invalid_mode'}

        if not partner:
            return {'error': 'not_found'}

        return {
            'member': {
                'id':         partner.id,
                'name':       partner.name,
                'belt_rank':  partner.belt_rank or 'white',
                'stage':      partner.member_stage or '',
                'avatar_url': f'/web/image/res.partner/{partner.id}/avatar_128',
            }
        }

    # ------------------------------------------------------------------
    # JSON: member name search
    # ------------------------------------------------------------------
    @http.route('/dojo/kiosk/search', type='jsonrpc', auth='public', website=True,
                sitemap=False, methods=['POST'])
    def kiosk_search(self, query='', **kwargs):
        if not query or len(query) < 2:
            return {'members': []}

        members = request.env['res.partner'].sudo().search([
            ('is_member', '=', True),
            ('name', 'ilike', query),
        ], limit=8)

        result = []
        for m in members:
            # Build avatar URL
            avatar_url = f'/web/image/res.partner/{m.id}/avatar_128'
            result.append({
                'id':         m.id,
                'name':       m.name,
                'belt_rank':  m.belt_rank or 'white',
                'stage':      m.member_stage or '',
                'avatar_url': avatar_url,
            })
        return {'members': result}

    # ------------------------------------------------------------------
    # JSON: check-in
    # ------------------------------------------------------------------
    @http.route('/dojo/kiosk/checkin', type='jsonrpc', auth='public', website=True,
                sitemap=False, methods=['POST'])
    def kiosk_checkin(self, partner_id=None, session_id=None, **kwargs):
        if not partner_id or not session_id:
            return {'error': 'missing_params'}

        session = request.env['disaster.class.session'].sudo().browse(int(session_id))
        partner = request.env['res.partner'].sudo().browse(int(partner_id))

        if not session.exists() or session.state == 'cancelled':
            return {'error': 'session_unavailable'}
        if not partner.exists() or not partner.is_member:
            return {'error': 'not_a_member'}

        # Already checked in?
        existing = request.env['disaster.class.attendance'].sudo().search([
            ('session_id', '=', session.id),
            ('partner_id', '=', partner.id),
        ], limit=1)

        if existing:
            return {
                'status':    'already_in',
                'name':      partner.name,
                'belt_rank': partner.belt_rank or 'white',
                'avatar_url': f'/web/image/res.partner/{partner.id}/avatar_128',
            }

        # ── Course eligibility checks ────────────────────────────────
        eligible, reason = self._session_eligibility(session, partner)
        if not eligible:
            course = session.course_id
            member_belt = partner.belt_rank or 'white'
            error_code  = 'belt_rank_too_low' if 'belt' in reason.lower() else 'not_enrolled'
            return {
                'error':         error_code,
                'name':          partner.name,
                'belt_rank':     member_belt,
                'avatar_url':    f'/web/image/res.partner/{partner.id}/avatar_128',
                'reason':        reason,
                'course_name':   course.name if course else '',
                'required_belt': course.min_belt_rank if course else '',
            }

        # Create attendance record
        request.env['disaster.class.attendance'].sudo().create({
            'session_id': session.id,
            'partner_id': partner.id,
            'belt_rank_at_checkin': partner.belt_rank or False,
        })

        # Mark session in-progress if still scheduled
        if session.state == 'scheduled':
            session.state = 'in_progress'

        return {
            'status':     'ok',
            'name':       partner.name,
            'belt_rank':  partner.belt_rank or 'white',
            'avatar_url': f'/web/image/res.partner/{partner.id}/avatar_128',
        }

    # ------------------------------------------------------------------
    # JSON: member info — today's sessions + recent history
    # ------------------------------------------------------------------
    @http.route('/dojo/kiosk/member_info', type='jsonrpc', auth='public', website=True,
                sitemap=False, methods=['POST'])
    def kiosk_member_info(self, partner_id=None, **kwargs):
        """
        Returns:
        - today's available sessions for the student to choose
        - their last 8 attendance records (class history)
        """
        if not partner_id:
            return {'error': 'missing_params'}

        partner = request.env['res.partner'].sudo().browse(int(partner_id))
        if not partner.exists() or not partner.is_member:
            return {'error': 'not_a_member'}

        # Today's active sessions — include per-member eligibility
        sessions = self._get_active_sessions()
        session_list = [self._session_to_dict(s, partner) for s in sessions]

        # Recent class history (last 8)
        history_recs = request.env['disaster.class.attendance'].sudo().search([
            ('partner_id', '=', partner.id),
        ], order='check_in desc', limit=8)

        history = []
        for h in history_recs:
            s = h.session_id
            history.append({
                'date':  fields.Datetime.context_timestamp(
                             h, h.check_in).strftime('%b %d')  if h.check_in else '',
                'class': s.name if s else '',
                'type':  s.class_type or '' if s else '',
            })

        return {
            'sessions': session_list,
            'history':  history,
        }

    # ======================================================================
    # INSTRUCTOR MODE
    # ======================================================================

    # ------------------------------------------------------------------
    # GET: Instructor dashboard page
    # ------------------------------------------------------------------
    @http.route('/dojo/kiosk/instructor', type='http', auth='public', website=True,
                sitemap=False)
    def kiosk_instructor(self, **kwargs):
        sessions = self._get_all_today_sessions()
        return request.render('disaster_member_belts.kiosk_instructor', {
            'sessions': sessions,
        })

    # ------------------------------------------------------------------
    # JSON: verify instructor PIN
    # ------------------------------------------------------------------
    @http.route('/dojo/kiosk/instructor/auth', type='jsonrpc', auth='public', website=True,
                sitemap=False, methods=['POST'])
    def kiosk_instructor_auth(self, pin='', **kwargs):
        correct = self._get_instructor_pin()
        if str(pin).strip() == str(correct).strip():
            return {'ok': True}
        return {'ok': False, 'error': 'wrong_pin'}

    # ------------------------------------------------------------------
    # JSON: start / end / cancel a session
    # ------------------------------------------------------------------
    @http.route('/dojo/kiosk/instructor/session_action', type='jsonrpc', auth='public',
                website=True, sitemap=False, methods=['POST'])
    def kiosk_instructor_session_action(self, session_id=None, action=None, **kwargs):
        """
        action: 'start' | 'end' | 'cancel'
        """
        if not session_id or not action:
            return {'error': 'missing_params'}

        session = request.env['disaster.class.session'].sudo().browse(int(session_id))
        if not session.exists():
            return {'error': 'not_found'}

        transitions = {
            'start':  ('scheduled',   'in_progress'),
            'end':    ('in_progress', 'done'),
            'cancel': (None,          'cancelled'),
        }
        if action not in transitions:
            return {'error': 'invalid_action'}

        required_state, new_state = transitions[action]
        if required_state and session.state != required_state:
            return {'error': f'session_not_{required_state}', 'current': session.state}

        session.state = new_state
        return {'ok': True, 'state': session.state, 'session': self._session_to_dict(session)}

    # ------------------------------------------------------------------
    # JSON: live attendance list for a session
    # ------------------------------------------------------------------
    @http.route('/dojo/kiosk/instructor/attendees', type='jsonrpc', auth='public',
                website=True, sitemap=False, methods=['POST'])
    def kiosk_instructor_attendees(self, session_id=None, **kwargs):
        if not session_id:
            return {'error': 'missing_params'}

        session = request.env['disaster.class.session'].sudo().browse(int(session_id))
        if not session.exists():
            return {'error': 'not_found'}

        attendees = []
        for att in session.attendance_ids.sorted(key=lambda a: a.check_in):
            p = att.partner_id
            attendees.append({
                'id':         p.id,
                'name':       p.name,
                'belt_rank':  att.belt_rank_at_checkin or p.belt_rank or 'white',
                'avatar_url': f'/web/image/res.partner/{p.id}/avatar_128',
                'check_in':   fields.Datetime.context_timestamp(
                                  att, att.check_in).strftime('%I:%M %p') if att.check_in else '',
            })

        return {
            'session': self._session_to_dict(session),
            'attendees': attendees,
            'count': len(attendees),
        }

    # ------------------------------------------------------------------
    # JSON: instructor manually checks in a student
    # ------------------------------------------------------------------
    @http.route('/dojo/kiosk/instructor/manual_checkin', type='jsonrpc', auth='public',
                website=True, sitemap=False, methods=['POST'])
    def kiosk_instructor_manual_checkin(self, session_id=None, partner_id=None, **kwargs):
        if not session_id or not partner_id:
            return {'error': 'missing_params'}

        session = request.env['disaster.class.session'].sudo().browse(int(session_id))
        partner = request.env['res.partner'].sudo().browse(int(partner_id))

        if not session.exists() or session.state == 'cancelled':
            return {'error': 'session_unavailable'}
        if not partner.exists() or not partner.is_member:
            return {'error': 'not_a_member'}

        existing = request.env['disaster.class.attendance'].sudo().search([
            ('session_id', '=', session.id),
            ('partner_id', '=', partner.id),
        ], limit=1)

        if existing:
            return {'status': 'already_in', 'name': partner.name}

        request.env['disaster.class.attendance'].sudo().create({
            'session_id': session.id,
            'partner_id': partner.id,
            'belt_rank_at_checkin': partner.belt_rank or False,
        })

        if session.state == 'scheduled':
            session.state = 'in_progress'

        return {
            'status':     'ok',
            'name':       partner.name,
            'belt_rank':  partner.belt_rank or 'white',
            'avatar_url': f'/web/image/res.partner/{partner.id}/avatar_128',
        }

    # ------------------------------------------------------------------
    # JSON: search members (used by instructor's add-student panel)
    # ------------------------------------------------------------------
    @http.route('/dojo/kiosk/instructor/search_member', type='jsonrpc', auth='public',
                website=True, sitemap=False, methods=['POST'])
    def kiosk_instructor_search_member(self, query='', **kwargs):
        if not query or len(query) < 2:
            return {'members': []}

        members = request.env['res.partner'].sudo().search([
            ('is_member', '=', True),
            ('name', 'ilike', query),
        ], limit=10)

        return {
            'members': [{
                'id':         m.id,
                'name':       m.name,
                'belt_rank':  m.belt_rank or 'white',
                'avatar_url': f'/web/image/res.partner/{m.id}/avatar_128',
            } for m in members]
        }

    # ------------------------------------------------------------------
    # PIN-protected exit back to backend
    # ------------------------------------------------------------------
    @http.route('/dojo/kiosk/exit', type='http', auth='public', website=True,
                sitemap=False, methods=['GET', 'POST'])
    def kiosk_exit(self, pin='', **kwargs):
        if request.httprequest.method == 'POST':
            correct = self._get_kiosk_pin()
            if pin == correct:
                return request.redirect('/odoo')
            return request.render('disaster_member_belts.kiosk_exit_pin', {
                'error': True,
            })
        return request.render('disaster_member_belts.kiosk_exit_pin', {
            'error': False,
        })
