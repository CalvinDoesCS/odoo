# -*- coding: utf-8 -*-
"""
portal.py
---------
Member-facing portal routes:

  /my/dojo           – Dashboard: belt rank, attendance, contract summary
  /my/dojo/classes   – Upcoming classes + booking / check-in
  /my/dojo/progress  – Full attendance history + belt timeline
  /my/dojo/contract  – Membership plan + billing details
  /my/dojo/checkin/<session_id> – POST: self check-in from portal
  /my/dojo/book/<session_id>    – POST: book / cancel booking (future)
"""

from odoo import http, _
from odoo.http import request
from odoo.exceptions import AccessError
import logging

_logger = logging.getLogger(__name__)

BELT_ORDER = ['white', 'yellow', 'orange', 'green', 'blue', 'purple', 'brown', 'red', 'black']
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


def _get_member_partner():
    """Return the res.partner for the current portal user, or raise AccessError."""
    if request.env.user._is_public():
        raise AccessError(_('Please log in to access the member portal.'))
    partner = request.env.user.partner_id
    if not partner.is_member:
        raise AccessError(_('This portal is for dojo members only.'))
    return partner.sudo()


class DojoMemberPortal(http.Controller):

    # ------------------------------------------------------------------
    # Dashboard
    # ------------------------------------------------------------------
    @http.route('/my/dojo', type='http', auth='user', website=True)
    def portal_dashboard(self, **kwargs):
        partner = _get_member_partner()

        # Belt progress
        current_rank = partner.belt_rank or 'white'
        rank_idx = BELT_ORDER.index(current_rank) if current_rank in BELT_ORDER else 0
        config = request.env['disaster.belt.rank.config'].sudo().search(
            [('rank', '=', current_rank)], limit=1
        )
        threshold = config.min_attendance if config else 10
        progress_pct = min(100, int((partner.attendance_count / threshold) * 100)) if threshold else 100

        # Recent attendance (last 10)
        recent_attendance = request.env['disaster.class.attendance'].sudo().search(
            [('partner_id', '=', partner.id)],
            order='check_in desc', limit=10
        )

        # Upcoming classes (next 7 days, not cancelled)
        upcoming_sessions = request.env['disaster.class.session'].sudo().search(
            [('state', 'in', ['scheduled', 'in_progress'])],
            order='date_start asc', limit=10
        )

        # Active contract
        contract = partner.active_contract_id

        values = {
            'partner': partner,
            'current_rank': current_rank,
            'rank_idx': rank_idx,
            'belt_order': BELT_ORDER,
            'belt_colors': BELT_COLORS,
            'threshold': threshold,
            'progress_pct': progress_pct,
            'attendance_count': partner.attendance_count,
            'ready_for_test': partner.ready_for_test,
            'next_belt_rank': partner.next_belt_rank,
            'recent_attendance': recent_attendance,
            'upcoming_sessions': upcoming_sessions,
            'contract': contract,
            'page_name': 'dojo_dashboard',
        }
        return request.render('disaster_member_belts.portal_member_dashboard', values)

    # ------------------------------------------------------------------
    # Class schedule & check-in
    # ------------------------------------------------------------------
    @http.route('/my/dojo/classes', type='http', auth='user', website=True)
    def portal_classes(self, **kwargs):
        partner = _get_member_partner()

        sessions = request.env['disaster.class.session'].sudo().search(
            [('state', 'in', ['scheduled', 'in_progress'])],
            order='date_start asc'
        )

        # Which sessions is this member already checked into?
        checked_in_ids = request.env['disaster.class.attendance'].sudo().search([
            ('partner_id', '=', partner.id),
            ('session_id', 'in', sessions.ids),
        ]).mapped('session_id').ids

        values = {
            'partner': partner,
            'sessions': sessions,
            'checked_in_ids': checked_in_ids,
            'belt_colors': BELT_COLORS,
            'belt_order': BELT_ORDER,
            'page_name': 'dojo_classes',
        }
        return request.render('disaster_member_belts.portal_member_classes', values)

    # ------------------------------------------------------------------
    # Self check-in POST
    # ------------------------------------------------------------------
    @http.route('/my/dojo/checkin/<int:session_id>', type='http', auth='user',
                website=True, methods=['POST'])
    def portal_checkin(self, session_id, **kwargs):
        partner = _get_member_partner()
        session = request.env['disaster.class.session'].sudo().browse(session_id)

        if not session.exists() or session.state == 'cancelled':
            return request.redirect('/my/dojo/classes?error=session_unavailable')

        # Check not already checked in
        existing = request.env['disaster.class.attendance'].sudo().search([
            ('partner_id', '=', partner.id),
            ('session_id', '=', session_id),
        ], limit=1)

        if not existing:
            request.env['disaster.class.attendance'].sudo().create({
                'session_id': session_id,
                'partner_id': partner.id,
            })
            if session.state == 'scheduled':
                session.state = 'in_progress'

        return request.redirect('/my/dojo/classes?success=checked_in')

    # ------------------------------------------------------------------
    # Progress / attendance history
    # ------------------------------------------------------------------
    @http.route('/my/dojo/progress', type='http', auth='user', website=True)
    def portal_progress(self, **kwargs):
        partner = _get_member_partner()

        all_attendance = request.env['disaster.class.attendance'].sudo().search(
            [('partner_id', '=', partner.id)],
            order='check_in desc'
        )

        # Build belt timeline from chatter messages
        belt_history = request.env['mail.message'].sudo().search([
            ('res_id', '=', partner.id),
            ('model', '=', 'res.partner'),
            ('body', 'ilike', 'belt_rank'),
            ('message_type', '=', 'notification'),
        ], order='date desc', limit=20)

        current_rank = partner.belt_rank or 'white'
        rank_idx = BELT_ORDER.index(current_rank) if current_rank in BELT_ORDER else 0
        config = request.env['disaster.belt.rank.config'].sudo().search(
            [('rank', '=', current_rank)], limit=1
        )
        threshold = config.min_attendance if config else 10
        progress_pct = min(100, int((partner.attendance_count / threshold) * 100)) if threshold else 100

        values = {
            'partner': partner,
            'all_attendance': all_attendance,
            'belt_history': belt_history,
            'current_rank': current_rank,
            'rank_idx': rank_idx,
            'belt_order': BELT_ORDER,
            'belt_colors': BELT_COLORS,
            'threshold': threshold,
            'progress_pct': progress_pct,
            'attendance_count': partner.attendance_count,
            'ready_for_test': partner.ready_for_test,
            'next_belt_rank': partner.next_belt_rank,
            'page_name': 'dojo_progress',
        }
        return request.render('disaster_member_belts.portal_member_progress', values)

    # ------------------------------------------------------------------
    # Contract / membership
    # ------------------------------------------------------------------
    @http.route('/my/dojo/contract', type='http', auth='user', website=True)
    def portal_contract(self, **kwargs):
        partner = _get_member_partner()

        contracts = request.env['disaster.member.contract'].sudo().search(
            [('partner_id', '=', partner.id)],
            order='date_start desc'
        )

        values = {
            'partner': partner,
            'contracts': contracts,
            'active_contract': partner.active_contract_id,
            'belt_colors': BELT_COLORS,
            'belt_order': BELT_ORDER,
            'page_name': 'dojo_contract',
        }
        return request.render('disaster_member_belts.portal_member_contract', values)
