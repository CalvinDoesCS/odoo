# -*- coding: utf-8 -*-
"""
kiosk.py
--------
Public-facing kiosk routes for dojo check-in.
No login required — designed for a dedicated touchscreen tablet.

Routes
------
GET  /dojo/kiosk                 – main kiosk screen
GET  /dojo/kiosk/<int:session>   – kiosk locked to one session
POST /dojo/kiosk/search          – JSON: search members by name
POST /dojo/kiosk/checkin         – JSON: check a member into a session
GET  /dojo/kiosk/exit            – PIN-protected exit back to backend
"""

import json
import logging
from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)

KIOSK_PIN_PARAM = 'disaster_member_belts.kiosk_exit_pin'
KIOSK_PIN_DEFAULT = '1234'


class DojoKiosk(http.Controller):

    def _get_kiosk_pin(self):
        return request.env['ir.config_parameter'].sudo().get_param(
            KIOSK_PIN_PARAM, KIOSK_PIN_DEFAULT
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

    # ------------------------------------------------------------------
    # Main kiosk screen
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

        # Create attendance record
        request.env['disaster.class.attendance'].sudo().create({
            'session_id': session.id,
            'partner_id': partner.id,
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
