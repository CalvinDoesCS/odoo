# -*- coding: utf-8 -*-
"""
mobile_api.py
-------------
JSON REST controllers for the Dojo mobile application.

All endpoints are under /api/dojo/v1/

Authentication:
  Pass the API token in the header:   X-Dojo-Token: <token>
  OR in the JSON body:                {"token": "<token>", ...}

All responses follow the envelope:
  {"ok": true, "data": {...}}   — success
  {"ok": false, "error": "..."} — failure
"""

import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

API_BASE = '/api/dojo/v1'


def _token_auth():
    """Extract partner from request token. Returns partner or None."""
    token = (
        request.httprequest.headers.get('X-Dojo-Token')
        or (request.get_json_data() or {}).get('token')
    )
    if not token:
        return None
    try:
        partner = request.env['dojo.api.token'].sudo().authenticate_token(token)
        return partner
    except Exception:
        return None


def _ok(data):
    return request.make_json_response({'ok': True, 'data': data})


def _err(msg, code=400):
    return request.make_json_response({'ok': False, 'error': msg}, status=code)


# ─────────────────────────────────────────────────────────────────────────────
class DojoMobileAPI(http.Controller):

    # ── Auth ─────────────────────────────────────────────────────────────────
    @http.route(f'{API_BASE}/login', type='json', auth='public', methods=['POST'], csrf=False)
    def login(self, **kwargs):
        """
        Exchange Odoo credentials for an API token.
        Body: {"db": "...", "login": "...", "password": "..."}
        """
        body = request.get_json_data() or {}
        db = body.get('db') or request.db
        login = body.get('login', '')
        password = body.get('password', '')

        uid = request.session.authenticate(db, login, password)
        if not uid:
            return _err('Invalid credentials', 401)

        user = request.env['res.users'].sudo().browse(uid)
        partner = user.partner_id

        # Create or reuse token
        token_name = body.get('device_name', 'Mobile App')
        existing = request.env['dojo.api.token'].sudo().search([
            ('partner_id', '=', partner.id),
            ('name', '=', token_name),
            ('active', '=', True),
        ], limit=1)
        if not existing:
            existing = request.env['dojo.api.token'].sudo().create({
                'name': token_name,
                'partner_id': partner.id,
            })

        return _ok({'token': existing.token, 'partner_id': partner.id, 'name': partner.name})

    # ── Member Profile ───────────────────────────────────────────────────────
    @http.route(f'{API_BASE}/member/profile', type='json', auth='public', methods=['GET', 'POST'], csrf=False)
    def member_profile(self, **kwargs):
        partner = _token_auth()
        if not partner:
            return _err('Unauthorized', 401)

        return _ok({
            'id': partner.id,
            'name': partner.name,
            'email': partner.email or '',
            'phone': partner.phone or '',
            'mobile': partner.mobile or '',
            'member_number': partner.dojo_member_number or '',
            'belt_rank': partner.belt_rank or '',
            'member_stage': partner.member_stage or '',
            'attendance_count': partner.attendance_count or 0,
            'ready_for_test': partner.ready_for_test,
            'avatar_url': f'/web/image/res.partner/{partner.id}/image_128',
        })

    @http.route(f'{API_BASE}/member/profile/update', type='json', auth='public', methods=['POST'], csrf=False)
    def member_profile_update(self, **kwargs):
        partner = _token_auth()
        if not partner:
            return _err('Unauthorized', 401)
        body = request.get_json_data() or {}
        allowed = {'phone', 'mobile', 'dojo_medical_notes'}
        vals = {k: v for k, v in body.items() if k in allowed}
        if vals:
            partner.sudo().write(vals)
        return _ok({'updated': list(vals.keys())})

    # ── Wallet ───────────────────────────────────────────────────────────────
    @http.route(f'{API_BASE}/wallet', type='json', auth='public', methods=['GET', 'POST'], csrf=False)
    def wallet_balance(self, **kwargs):
        partner = _token_auth()
        if not partner:
            return _err('Unauthorized', 401)

        wallet = request.env['dojo.wallet'].sudo().get_or_create_wallet(partner.id)
        txs = request.env['dojo.wallet.tx'].sudo().search(
            [('wallet_id', '=', wallet.id)], order='create_date desc', limit=20
        )
        return _ok({
            'balance': wallet.balance,
            'credit_balance': wallet.credit_balance,
            'currency': wallet.currency_id.name,
            'transactions': [{
                'id': t.id,
                'type': t.tx_type,
                'amount': t.amount,
                'credits': t.credits,
                'description': t.description or '',
                'date': t.create_date.isoformat() if t.create_date else '',
            } for t in txs],
        })

    # ── Sessions (Schedule) ──────────────────────────────────────────────────
    @http.route(f'{API_BASE}/sessions', type='json', auth='public', methods=['GET', 'POST'], csrf=False)
    def sessions_list(self, **kwargs):
        partner = _token_auth()
        if not partner:
            return _err('Unauthorized', 401)

        body = request.get_json_data() or {}
        limit = int(body.get('limit', 20))
        offset = int(body.get('offset', 0))

        sessions = request.env['disaster.class.session'].sudo().search(
            [('state', 'not in', ['cancelled'])], order='session_date asc', limit=limit, offset=offset
        )
        result = []
        for s in sessions:
            booked = request.env['dojo.session.roster'].sudo().search_count([
                ('session_id', '=', s.id), ('member_id', '=', partner.id),
                ('state', 'in', ['booked', 'waitlisted']),
            ])
            result.append({
                'id': s.id,
                'name': s.name,
                'date': str(s.session_date) if s.session_date else '',
                'start_time': s.start_time if hasattr(s, 'start_time') else '',
                'capacity': s.capacity if hasattr(s, 'capacity') else 0,
                'capacity_remaining': s.capacity_remaining if hasattr(s, 'capacity_remaining') else 0,
                'is_full': s.is_full if hasattr(s, 'is_full') else False,
                'i_am_booked': bool(booked),
            })
        return _ok({'sessions': result})

    @http.route(f'{API_BASE}/sessions/book', type='json', auth='public', methods=['POST'], csrf=False)
    def session_book(self, **kwargs):
        partner = _token_auth()
        if not partner:
            return _err('Unauthorized', 401)

        body = request.get_json_data() or {}
        session_id = body.get('session_id')
        if not session_id:
            return _err('session_id required')

        session = request.env['disaster.class.session'].sudo().browse(int(session_id))
        if not session.exists():
            return _err('Session not found', 404)

        existing = request.env['dojo.session.roster'].sudo().search([
            ('session_id', '=', session.id),
            ('member_id', '=', partner.id),
            ('state', 'in', ['booked', 'waitlisted']),
        ], limit=1)
        if existing:
            return _err('Already booked or waitlisted for this session')

        roster = request.env['dojo.session.roster'].sudo().create({
            'session_id': session.id,
            'member_id': partner.id,
            'source': 'member_app',
        })
        return _ok({'roster_id': roster.id, 'state': roster.state})

    @http.route(f'{API_BASE}/sessions/cancel', type='json', auth='public', methods=['POST'], csrf=False)
    def session_cancel(self, **kwargs):
        partner = _token_auth()
        if not partner:
            return _err('Unauthorized', 401)

        body = request.get_json_data() or {}
        session_id = body.get('session_id')
        if not session_id:
            return _err('session_id required')

        roster = request.env['dojo.session.roster'].sudo().search([
            ('session_id', '=', int(session_id)),
            ('member_id', '=', partner.id),
            ('state', 'in', ['booked', 'waitlisted']),
        ], limit=1)
        if not roster:
            return _err('No active booking found', 404)
        roster.action_cancel()
        return _ok({'cancelled': True})

    # ── Check-in by PIN ───────────────────────────────────────────────────────
    @http.route(f'{API_BASE}/checkin/pin', type='json', auth='public', methods=['POST'], csrf=False)
    def checkin_by_pin(self, **kwargs):
        """Kiosk-style PIN check-in. Does not require a member token."""
        body = request.get_json_data() or {}
        pin = str(body.get('pin', ''))
        session_id = body.get('session_id')

        if not pin or not session_id:
            return _err('pin and session_id required')

        partner = request.env['res.partner'].sudo().search([
            ('kiosk_pin', '=', pin),
            ('is_member', '=', True),
        ], limit=1)
        if not partner:
            return _err('Member not found', 404)

        roster = request.env['dojo.session.roster'].sudo().search([
            ('session_id', '=', int(session_id)),
            ('member_id', '=', partner.id),
            ('state', 'in', ['booked', 'waitlisted']),
        ], limit=1)
        if not roster:
            # Auto-create roster on walk-in
            roster = request.env['dojo.session.roster'].sudo().create({
                'session_id': int(session_id),
                'member_id': partner.id,
                'source': 'kiosk',
            })
        roster.action_check_in()
        return _ok({
            'member_name': partner.name,
            'belt_rank': partner.belt_rank or '',
            'attendance_count': partner.attendance_count or 0,
        })

    # ── Announcements ────────────────────────────────────────────────────────
    @http.route(f'{API_BASE}/announcements', type='json', auth='public', methods=['GET', 'POST'], csrf=False)
    def announcements(self, **kwargs):
        partner = _token_auth()
        if not partner:
            return _err('Unauthorized', 401)

        body = request.get_json_data() or {}
        limit = int(body.get('limit', 10))

        now = http.request.env['ir.fields.Date'].today()
        announcements = request.env['disaster.announcement'].sudo().search(
            [
                '|', ('dojo_expire_dt', '=', False), ('dojo_expire_dt', '>=', now),
                ('dojo_dispatched', '=', True),
            ],
            order='dojo_publish_dt desc, id desc', limit=limit,
        )
        return _ok({'announcements': [{
            'id': a.id,
            'title': a.name if hasattr(a, 'name') else str(a.id),
            'body': a.body_text if hasattr(a, 'body_text') else '',
            'publish_dt': a.dojo_publish_dt.isoformat() if a.dojo_publish_dt else '',
            'expire_dt': a.dojo_expire_dt.isoformat() if a.dojo_expire_dt else '',
        } for a in announcements]})

    # ── Curriculum ───────────────────────────────────────────────────────────
    @http.route(f'{API_BASE}/curriculum', type='json', auth='public', methods=['GET', 'POST'], csrf=False)
    def curriculum(self, **kwargs):
        partner = _token_auth()
        if not partner:
            return _err('Unauthorized', 401)

        body = request.get_json_data() or {}
        belt_rank = body.get('belt_rank') or partner.belt_rank

        rank_config = request.env['disaster.belt.rank.config'].sudo().search(
            [('belt_rank', '=', belt_rank)], limit=1
        )
        if not rank_config:
            return _ok({'belt_rank': belt_rank, 'curriculum': []})

        items = []
        for rc in rank_config.dojo_curriculum_ids.sorted('sequence'):
            c = rc.content_id
            if c.visibility == 'private':
                continue
            items.append({
                'id': c.id,
                'title': c.name,
                'type': c.content_type,
                'url': c.url or '',
                'required': rc.required_for_promotion,
                'tags': [t.name for t in c.tag_ids],
            })
        return _ok({'belt_rank': belt_rank, 'curriculum': items})

    # ── Rank History ─────────────────────────────────────────────────────────
    @http.route(f'{API_BASE}/member/rank_history', type='json', auth='public', methods=['GET', 'POST'], csrf=False)
    def rank_history(self, **kwargs):
        partner = _token_auth()
        if not partner:
            return _err('Unauthorized', 401)

        history = request.env['dojo.rank.history'].sudo().search(
            [('member_id', '=', partner.id)], order='awarded_dt desc'
        )
        return _ok({'history': [{
            'id': h.id,
            'belt_rank': h.belt_rank_id.name if h.belt_rank_id else '',
            'previous': h.previous_belt_rank_id.name if h.previous_belt_rank_id else '',
            'awarded_dt': str(h.awarded_dt) if h.awarded_dt else '',
            'awarded_by': h.awarded_by_id.name if h.awarded_by_id else '',
        } for h in history]})

    # ── Register Push Device ─────────────────────────────────────────────────
    @http.route(f'{API_BASE}/push/register', type='json', auth='public', methods=['POST'], csrf=False)
    def push_register(self, **kwargs):
        partner = _token_auth()
        if not partner:
            return _err('Unauthorized', 401)

        body = request.get_json_data() or {}
        platform = body.get('platform', 'android')
        token = body.get('push_token', '')
        if not token:
            return _err('push_token required')

        device = request.env['dojo.push.device'].sudo().register_device(
            partner_id=partner.id,
            token=token,
            platform=platform,
            app_version=body.get('app_version', ''),
        )
        return _ok({'device_id': device.id})
