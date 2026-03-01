from odoo import fields, http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError, ValidationError
import json
from datetime import datetime, timedelta


class DojoMemberPortal(CustomerPortal):
    """Portal controller for Dojo member-facing pages under /my."""

    # ── Portal home: inject dojo doc counts ──────────────────────────────
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        env = request.env

        if 'dojo_schedule_count' in counters:
            # Use sudo() – open sessions are public info, and portal users
            # without the dojo-specific group would get an AccessError otherwise.
            values['dojo_schedule_count'] = env['dojo.class.session'].sudo().search_count([
                ('state', '=', 'open'),
                ('start_datetime', '>=', fields.Datetime.now()),
            ])

        if 'dojo_attendance_count' in counters:
            household_member_ids = self._get_household_member_ids()
            try:
                values['dojo_attendance_count'] = env['dojo.attendance.log'].search_count([
                    ('member_id', 'in', household_member_ids),
                ]) if household_member_ids else 0
            except Exception:
                values['dojo_attendance_count'] = 0

        if 'dojo_invoice_count' in counters:
            invoice_ids = self._get_household_invoice_ids()
            values['dojo_invoice_count'] = len(invoice_ids)

        return values

    # ── Helpers ───────────────────────────────────────────────────────────
    def _get_current_member(self):
        """Return the dojo.member record for the current portal user, or None."""
        partner = request.env.user.partner_id
        member = request.env['dojo.member'].sudo().search(
            [('partner_id', '=', partner.id)], limit=1
        )
        return member or None

    def _get_household_member_ids(self):
        """Return list of member IDs that belong to the current user's household."""
        member = self._get_current_member()
        if not member:
            return []
        if member.household_id:
            return member.household_id.member_ids.ids
        return [member.id]

    def _get_household_invoice_ids(self):
        """Return all account.move IDs for invoices tied to household subscriptions."""
        member_ids = self._get_household_member_ids()
        if not member_ids:
            return []
        subscriptions = request.env['dojo.member.subscription'].sudo().search([
            ('member_id', 'in', member_ids),
        ])
        # Collect all historical invoices via the One2many, not just last_invoice_id
        all_invoices = subscriptions.mapped('invoice_ids')
        return all_invoices.ids

    def _get_belt_context(self, member):
        """Return current_rank, next_rank, and rank_pct (0-100) for the dashboard."""
        if not member:
            return {'current_rank': None, 'next_rank': None, 'rank_pct': 0}
        current_rank = getattr(member, 'current_rank_id', None) or None
        if not current_rank:
            return {'current_rank': None, 'next_rank': None, 'rank_pct': 0}
        all_ranks = request.env['dojo.belt.rank'].sudo().search(
            [('company_id', '=', member.company_id.id)], order='sequence asc'
        )
        rank_ids = all_ranks.ids
        try:
            idx = rank_ids.index(current_rank.id)
        except ValueError:
            idx = 0
        total = len(rank_ids)
        next_rank = all_ranks[idx + 1] if idx + 1 < total else None
        rank_pct = int(((idx + 1) / total) * 100) if total else 0
        return {'current_rank': current_rank, 'next_rank': next_rank, 'rank_pct': rank_pct}

    # ── /my/dojo  (unified portal page) ─────────────────────────────────
    @http.route('/my/dojo', type='http', auth='user')
    def portal_dojo_home(self, tab='schedule', saved=None, **kwargs):
        member = self._get_current_member()
        if not member:
            return request.render('dojo_members_portal.portal_no_member', {})
        env = request.env
        is_parent = member.role in ('parent', 'both')
        household_member_ids = self._get_household_member_ids()

        attendance_count = env['dojo.attendance.log'].sudo().search_count([
            ('member_id', 'in', household_member_ids),
        ])
        upcoming_count = env['dojo.class.enrollment'].sudo().search_count([
            ('member_id', 'in', household_member_ids),
            ('status', '=', 'registered'),
            ('session_id.start_datetime', '>=', fields.Datetime.now()),
            ('session_id.state', 'in', ['open', 'draft']),
        ])
        household_members = env['dojo.member'].sudo().browse(household_member_ids)
        members_json = json.dumps([{'id': m.id, 'name': m.name, 'role': m.role or ''} for m in household_members])

        return request.render('dojo_members_portal.portal_dojo_home', {
            'member': member,
            'is_parent': is_parent,
            'initial_tab': tab,
            'page_name': 'dojo_home',
            'attendance_count': attendance_count,
            'upcoming_count': upcoming_count,
            'household_saved': saved == '1',
            'members_json': members_json,
            **self._get_belt_context(member),
        })

    # ── /my/dojo/schedule – redirect to unified page ───────────────────
    @http.route('/my/dojo/schedule', type='http', auth='user')
    def portal_my_schedule(self, **kwargs):
        return request.redirect('/my/dojo?tab=schedule')

    # ── /my/dojo/enrollments – redirect to unified page ─────────────────
    @http.route('/my/dojo/enrollments', type='http', auth='user')
    def portal_my_enrollments(self, **kwargs):
        return request.redirect('/my/dojo?tab=enrollments')

    # ── /my/dojo/attendance – redirect to unified page ──────────────────
    @http.route('/my/dojo/attendance', type='http', auth='user')
    def portal_my_attendance(self, **kwargs):
        return request.redirect('/my/dojo?tab=attendance')

    # ── JSON data endpoints for the OWL activities component ──────────────
    @http.route('/my/dojo/json/schedule', type='http', auth='user')
    def portal_json_schedule(self, **kwargs):
        member = self._get_current_member()
        is_parent = member.role in ('parent', 'both') if member else True
        household_member_ids = self._get_household_member_ids()

        # Build a map of member_id -> set of enrolled template_ids
        household_members = request.env['dojo.member'].sudo().browse(household_member_ids)
        member_templates = {}
        all_template_ids = set()
        for m in household_members:
            tmpl_ids = set(m.enrolled_template_ids.ids)
            member_templates[m.id] = tmpl_ids
            all_template_ids.update(tmpl_ids)

        if not all_template_ids:
            return request.make_response(
                json.dumps({'sessions': [], 'can_enroll': is_parent}),
                headers=[('Content-Type', 'application/json')],
            )

        domain = [
            ('state', '=', 'open'),
            ('start_datetime', '>=', fields.Datetime.now()),
            ('template_id', 'in', list(all_template_ids)),
        ]
        sessions = request.env['dojo.class.session'].sudo().search(
            domain, order='start_datetime asc', limit=100
        )
        data = []
        for s in sessions:
            # Find which household members are eligible (enrolled in this template's course)
            eligible_member_ids = [
                mid for mid, tmpl_ids in member_templates.items()
                if s.template_id.id in tmpl_ids
            ]
            data.append({
                'id': s.id,
                'name': s.template_id.name or '',
                'template_id': s.template_id.id,
                'start_datetime': fields.Datetime.to_string(s.start_datetime) if s.start_datetime else None,
                'end_datetime': fields.Datetime.to_string(s.end_datetime) if s.end_datetime else None,
                'instructor': s.instructor_profile_id.name if s.instructor_profile_id else None,
                'level': s.template_id.level or 'all',
                'duration_minutes': s.template_id.duration_minutes or 0,
                'seats_taken': s.seats_taken or 0,
                'capacity': s.capacity or 0,
                'state': s.state,
                'description': s.template_id.description or '',
                'eligible_member_ids': eligible_member_ids,
            })
        return request.make_response(
            json.dumps({'sessions': data, 'can_enroll': is_parent}),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route('/my/dojo/json/enrollments', type='http', auth='user')
    def portal_json_enrollments(self, **kwargs):
        member_ids = self._get_household_member_ids()
        enrollments = request.env['dojo.class.enrollment'].sudo().search(
            [('member_id', 'in', member_ids)],
            limit=200,
        )
        # Sort by session start_datetime descending in Python to avoid cross-model order
        enrollments = sorted(
            enrollments,
            key=lambda e: e.session_id.start_datetime or fields.Datetime.now(),
            reverse=True,
        )[:100]
        data = []
        for e in enrollments:
            data.append({
                'id': e.id,
                'member_name': e.member_id.name or '',
                'session_name': e.session_id.template_id.name or '',
                'start_datetime': fields.Datetime.to_string(e.session_id.start_datetime)
                    if e.session_id.start_datetime else None,
                'instructor': e.session_id.instructor_profile_id.name
                    if e.session_id.instructor_profile_id else None,
                'status': e.status or '',
                'attendance_state': e.attendance_state or '',
            })
        return request.make_response(
            json.dumps({'enrollments': data}),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route('/my/dojo/json/attendance', type='http', auth='user')
    def portal_json_attendance(self, **kwargs):
        member_ids = self._get_household_member_ids()
        logs = request.env['dojo.attendance.log'].sudo().search(
            [('member_id', 'in', member_ids)],
            order='checkin_datetime desc',
            limit=100,
        )
        data = []
        for log in logs:
            data.append({
                'id': log.id,
                'member_name': log.member_id.name or '',
                'session_name': log.session_id.name if log.session_id else '',
                'checkin_datetime': fields.Datetime.to_string(log.checkin_datetime)
                    if log.checkin_datetime else None,
                'status': log.status or 'present',
                'note': log.note or '',
            })
        return request.make_response(
            json.dumps({'logs': data}),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route('/my/dojo/json/household', type='http', auth='user')
    def portal_json_household(self, **kwargs):
        member = self._get_current_member()
        if not member:
            return request.make_response(
                json.dumps({'error': 'No member found'}),
                headers=[('Content-Type', 'application/json')],
            )
        is_parent = member.role in ('parent', 'both')
        household = member.sudo().household_id
        hm_records = request.env['dojo.member'].sudo().browse(
            self._get_household_member_ids()
        )
        members_data = []
        for m in hm_records:
            contacts = []
            for ec in m.emergency_contact_ids:
                contacts.append({
                    'id': ec.id,
                    'name': ec.name or '',
                    'relationship': ec.relationship or '',
                    'phone': ec.phone or '',
                    'email': ec.email or '',
                    'is_primary': bool(ec.is_primary),
                })
            sub = m.active_subscription_id
            plan_data = None
            if sub and sub.plan_id:
                plan = sub.plan_id
                plan_data = {
                    'name': plan.name or '',
                    'state': sub.state or '',
                    'billing_period': plan.billing_period or '',
                    'price': plan.price,
                    'currency': plan.currency_id.name if plan.currency_id else 'USD',
                    'unlimited_sessions': plan.unlimited_sessions,
                    'sessions_per_period': plan.sessions_per_period,
                    'max_sessions_per_week': plan.max_sessions_per_week,
                }
            members_data.append({
                'id': m.id,
                'name': m.name or '',
                'role': m.role or '',
                'emergency_contacts': contacts,
                'courses': [
                    {'id': t.id, 'name': t.name, 'level': t.level or 'all'}
                    for t in m.enrolled_template_ids
                ],
                'sessions_used_this_week': m.sessions_used_this_week,
                'sessions_allowed_per_week': m.sessions_allowed_per_week,
                'plan': plan_data,
            })
        return request.make_response(
            json.dumps({
                'can_edit': is_parent,
                'household_name': household.name if household else '',
                'members': members_data,
            }),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route('/my/dojo/enroll', type='http', auth='user', methods=['POST'], csrf=False)
    def portal_enroll(self, session_id=None, member_id=None, **kwargs):
        def _err(msg):
            return request.make_response(
                json.dumps({'ok': False, 'error': msg}),
                headers=[('Content-Type', 'application/json')],
            )
        member = self._get_current_member()
        if not member:
            return _err('Not authenticated.')
        try:
            session_id = int(session_id)
            member_id  = int(member_id)
        except (TypeError, ValueError):
            return _err('Invalid parameters.')
        household_member_ids = self._get_household_member_ids()
        if member_id not in household_member_ids:
            return _err('Not authorised to enroll this member.')
        env = request.env
        # Only members with a student role may be enrolled in classes
        enroll_target = env['dojo.member'].sudo().browse(member_id)
        if not enroll_target.exists() or enroll_target.role not in ('student', 'both'):
            return _err('Only students can be enrolled in classes.')
        session = env['dojo.class.session'].sudo().browse(session_id)
        if not session.exists() or session.state not in ('open', 'draft'):
            return _err('Session is not available for enrollment.')
        # Enforce course roster: member must be enrolled in the course
        if session.template_id.course_member_ids:
            if enroll_target.id not in session.template_id.course_member_ids.ids:
                return _err(
                    '%s is not enrolled in the course "%s". '
                    'Ask an instructor to add them to the course roster first.' %
                    (enroll_target.name, session.template_id.name)
                )
        existing = env['dojo.class.enrollment'].sudo().search([
            ('session_id', '=', session_id),
            ('member_id', '=', member_id),
            ('status', '!=', 'cancelled'),
        ], limit=1)
        if existing:
            return _err('Already enrolled in this session.')
        try:
            env['dojo.class.enrollment'].sudo().create({
                'session_id': session_id,
                'member_id': member_id,
                'status': 'registered',
            })
        except ValidationError as ve:
            return _err(str(ve.args[0]) if ve.args else str(ve))
        return request.make_response(
            json.dumps({'ok': True}),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route('/my/dojo/household/save', type='http', auth='user', methods=['POST'], csrf=False)
    def portal_household_save(self, **kwargs):
        def _err(msg):
            return request.make_response(
                json.dumps({'ok': False, 'error': msg}),
                headers=[('Content-Type', 'application/json')],
            )
        member = self._get_current_member()
        if not member or member.role not in ('parent', 'both'):
            return _err('Not authorised.')
        try:
            payload = json.loads(request.httprequest.data)
        except Exception:
            return _err('Invalid request body.')
        household = member.sudo().household_id
        if household and payload.get('household_name'):
            household.sudo().write({'name': payload['household_name'].strip()})
        nc = payload.get('new_contact')
        if nc and nc.get('name') and nc.get('phone'):
            household_member_ids = self._get_household_member_ids()
            nc_mid = nc.get('member_id')
            if nc_mid and int(nc_mid) in household_member_ids:
                request.env['dojo.emergency.contact'].sudo().create({
                    'member_id': int(nc_mid),
                    'name': nc['name'].strip(),
                    'relationship': (nc.get('relationship') or '').strip() or 'Other',
                    'phone': nc['phone'].strip(),
                    'email': (nc.get('email') or '').strip() or False,
                    'is_primary': False,
                })
        return request.make_response(
            json.dumps({'ok': True}),
            headers=[('Content-Type', 'application/json')],
        )

    # ── /my/dojo/json/billing  (parents only) ──────────────────────────────
    @http.route('/my/dojo/json/billing', type='http', auth='user')
    def portal_json_billing(self, **kwargs):
        member = self._get_current_member()
        if not member or member.role not in ('parent', 'both'):
            return request.make_response(
                json.dumps({'error': 'Not authorised'}),
                headers=[('Content-Type', 'application/json')],
            )
        member_ids = self._get_household_member_ids()
        env = request.env

        # Active subscription for any household member
        sub = env['dojo.member.subscription'].sudo().search([
            ('member_id', 'in', member_ids),
            ('state', '=', 'active'),
        ], limit=1)
        # Fall back to any non-cancelled subscription
        if not sub:
            sub = env['dojo.member.subscription'].sudo().search([
                ('member_id', 'in', member_ids),
                ('state', 'not in', ('cancelled',)),
            ], order='start_date desc', limit=1)

        sub_data = None
        if sub:
            plan = sub.plan_id
            sub_data = {
                'id': sub.id,
                'plan_id': plan.id,
                'plan_name': plan.name or '',
                'price': plan.price,
                'currency': plan.currency_id.name if plan.currency_id else 'USD',
                'period': plan.billing_period or 'monthly',
                'state': sub.state,
                'start_date': fields.Date.to_string(sub.start_date) if sub.start_date else None,
                'next_billing_date': fields.Date.to_string(sub.next_billing_date) if sub.next_billing_date else None,
            }

        # All invoices for household subscriptions
        all_subs = env['dojo.member.subscription'].sudo().search([
            ('member_id', 'in', member_ids),
        ])
        invoices_data = []
        for inv in all_subs.mapped('invoice_ids').sorted(key=lambda i: i.invoice_date or i.create_date, reverse=True):
            invoices_data.append({
                'id': inv.id,
                'name': inv.name or '',
                'date': fields.Date.to_string(inv.invoice_date) if inv.invoice_date else None,
                'due': fields.Date.to_string(inv.invoice_date_due) if inv.invoice_date_due else None,
                'amount': inv.amount_total,
                'state': inv.state,
                'currency': inv.currency_id.name if inv.currency_id else 'USD',
            })

        # Available plans (for plan-switch overlay)
        plans = env['dojo.subscription.plan'].sudo().search([('active', '=', True)])
        plans_data = [{
            'id': p.id,
            'name': p.name,
            'price': p.price,
            'period': p.billing_period,
            'currency': p.currency_id.name if p.currency_id else 'USD',
            'description': p.description or '',
        } for p in plans]

        # Payment method from household
        household = env['dojo.household'].sudo().search(
            [('member_ids', 'in', member_ids)], limit=1
        )
        if household and household.payment_card_last4:
            payment_method = {
                'has_card': True,
                'brand': household.payment_card_brand or '',
                'last4': household.payment_card_last4 or '',
                'expiry': household.payment_card_expiry or '',
                'stripe_customer_id': household.stripe_customer_id or '',
            }
        else:
            payment_method = {'has_card': False, 'brand': '', 'last4': '', 'expiry': ''}

        return request.make_response(
            json.dumps({'subscription': sub_data, 'invoices': invoices_data, 'plans': plans_data, 'payment_method': payment_method}),
            headers=[('Content-Type', 'application/json')],
        )

    # ── Billing action endpoints (parents only) ───────────────────────────
    def _get_household_active_sub(self):
        """Return the active subscription for the current household, or None."""
        member = self._get_current_member()
        if not member or member.role not in ('parent', 'both'):
            return None
        member_ids = self._get_household_member_ids()
        sub = request.env['dojo.member.subscription'].sudo().search([
            ('member_id', 'in', member_ids),
            ('state', 'in', ('active', 'paused')),
        ], order='start_date desc', limit=1)
        return sub or None

    @http.route('/my/dojo/billing/change-plan', type='http', auth='user', methods=['POST'], csrf=False)
    def portal_billing_change_plan(self, plan_id=None, **kwargs):
        def _err(msg):
            return request.make_response(
                json.dumps({'ok': False, 'error': msg}),
                headers=[('Content-Type', 'application/json')],
            )
        sub = self._get_household_active_sub()
        if not sub:
            return _err('No active subscription found.')
        try:
            plan_id = int(plan_id)
        except (TypeError, ValueError):
            return _err('Invalid plan.')
        plan = request.env['dojo.subscription.plan'].sudo().browse(plan_id)
        if not plan.exists() or not plan.active:
            return _err('Plan not available.')
        sub.sudo().write({'plan_id': plan_id})
        return request.make_response(
            json.dumps({'ok': True}),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route('/my/dojo/billing/pause', type='http', auth='user', methods=['POST'], csrf=False)
    def portal_billing_pause(self, **kwargs):
        sub = self._get_household_active_sub()
        if not sub or sub.state != 'active':
            return request.make_response(
                json.dumps({'ok': False, 'error': 'No active subscription to pause.'}),
                headers=[('Content-Type', 'application/json')],
            )
        sub.sudo().write({'state': 'paused'})
        return request.make_response(
            json.dumps({'ok': True}),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route('/my/dojo/billing/resume', type='http', auth='user', methods=['POST'], csrf=False)
    def portal_billing_resume(self, **kwargs):
        sub = self._get_household_active_sub()
        if not sub or sub.state != 'paused':
            return request.make_response(
                json.dumps({'ok': False, 'error': 'Subscription is not paused.'}),
                headers=[('Content-Type', 'application/json')],
            )
        sub.sudo().write({'state': 'active'})
        return request.make_response(
            json.dumps({'ok': True}),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route('/my/dojo/billing/cancel', type='http', auth='user', methods=['POST'], csrf=False)
    def portal_billing_cancel(self, **kwargs):
        sub = self._get_household_active_sub()
        if not sub:
            return request.make_response(
                json.dumps({'ok': False, 'error': 'No active subscription found.'}),
                headers=[('Content-Type', 'application/json')],
            )
        sub.sudo().write({'state': 'cancelled', 'end_date': fields.Date.today()})
        return request.make_response(
            json.dumps({'ok': True}),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route('/my/dojo/billing/wallet-provision', type='http', auth='user', methods=['GET'])
    def portal_billing_wallet_provision(self, **kwargs):
        """Return a Stripe Ephemeral Key for Google Wallet push provisioning."""
        member = self._get_current_member()
        if not member or member.role not in ('parent', 'both'):
            return request.make_response(
                json.dumps({'error': 'Not authorised'}),
                headers=[('Content-Type', 'application/json')],
            )
        member_ids = self._get_household_member_ids()
        household = request.env['dojo.household'].sudo().search(
            [('member_ids', 'in', member_ids)], limit=1
        )
        if not household or not household.stripe_card_id:
            return request.make_response(
                json.dumps({'error': 'No Stripe card on file for this household.'}),
                headers=[('Content-Type', 'application/json')],
            )
        try:
            result = household.action_get_wallet_ephemeral_key()
            return request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')],
            )
        except Exception as e:
            return request.make_response(
                json.dumps({'error': str(e)}),
                headers=[('Content-Type', 'application/json')],
            )

    # ── /my/dojo/invoices  (parents only) ────────────────────────────────
    @http.route('/my/dojo/invoices', type='http', auth='user')
    def portal_my_dojo_invoices(self, **kwargs):
        member = self._get_current_member()
        if not member or member.role not in ('parent', 'both'):
            return request.render('dojo_members_portal.portal_no_member', {})
        invoice_ids = self._get_household_invoice_ids()
        invoices = request.env['account.move'].sudo().browse(invoice_ids).sorted(
            key=lambda i: i.invoice_date or i.create_date, reverse=True
        )
        return request.render('dojo_members_portal.portal_my_dojo_invoices', {
            'invoices': invoices,
            'page_name': 'dojo_invoices',
        })

    # ── /my/dojo/invoices/<int:invoice_id>/pdf ────────────────────────────
    @http.route(
        '/my/dojo/invoices/<int:invoice_id>/pdf',
        type='http', auth='user',
    )
    def portal_dojo_invoice_pdf(self, invoice_id, **kwargs):
        member = self._get_current_member()
        if not member or member.role not in ('parent', 'both'):
            return request.not_found()
        invoice_ids = self._get_household_invoice_ids()
        if invoice_id not in invoice_ids:
            return request.not_found()
        invoice = request.env['account.move'].sudo().browse(invoice_id)
        pdf_content, _ = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'account.account_invoices', invoice.ids
        )
        return request.make_response(
            pdf_content,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="invoice-{invoice.name}.pdf"'),
            ],
        )

    # ── /my/dojo/household ────────────────────────────────────────────────
    @http.route(
        '/my/dojo/household',
        type='http', auth='user', methods=['GET', 'POST'],
    )
    def portal_my_household(self, **post):
        member = self._get_current_member()
        if not member:
            return request.render('dojo_members_portal.portal_no_member', {})

        can_edit = member.role in ('parent', 'both')
        household = member.sudo().household_id
        error = {}
        success = False

        if request.httprequest.method == 'POST' and can_edit:
            # Update household name
            new_name = post.get('household_name', '').strip()
            if household and new_name:
                household.sudo().write({'name': new_name})

            # Process emergency contact updates for each household member
            member_ids = self._get_household_member_ids()
            for m_id in member_ids:
                # Delete removed contacts
                removed_ids = post.get(f'remove_contact_{m_id}', '').split(',')
                for rid in removed_ids:
                    try:
                        rid = int(rid)
                        contact = request.env['dojo.emergency.contact'].sudo().browse(rid)
                        if contact.member_id.id == m_id:
                            contact.unlink()
                    except (ValueError, Exception):
                        pass

            # Add new emergency contact if submitted
            new_contact_member_id = post.get('new_contact_member_id')
            new_contact_name = post.get('new_contact_name', '').strip()
            new_contact_relationship = post.get('new_contact_relationship', '').strip()
            new_contact_phone = post.get('new_contact_phone', '').strip()

            if new_contact_name and new_contact_phone and new_contact_member_id:
                try:
                    nc_member_id = int(new_contact_member_id)
                    if nc_member_id in member_ids:
                        request.env['dojo.emergency.contact'].sudo().create({
                            'member_id': nc_member_id,
                            'name': new_contact_name,
                            'relationship': new_contact_relationship or 'Other',
                            'phone': new_contact_phone,
                            'email': post.get('new_contact_email', '').strip() or False,
                            'is_primary': False,
                        })
                except (ValueError, Exception):
                    error['new_contact'] = _('Could not save the new contact.')

            if not error:
                return request.redirect('/my/dojo?tab=household&saved=1')

        # Re-fetch members for display (POST with errors falls through here)
        household_members = request.env['dojo.member'].sudo().browse(
            self._get_household_member_ids()
        )
        return request.render('dojo_members_portal.portal_my_household', {
            'member': member,
            'can_edit': can_edit,
            'household': household,
            'household_members': household_members,
            'page_name': 'dojo_household',
            'error': error,
            'success': False,
        })
