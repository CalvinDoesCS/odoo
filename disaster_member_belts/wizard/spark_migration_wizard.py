# -*- coding: utf-8 -*-
"""
spark_migration_wizard.py
--------------------------
One-shot import wizard: upload CSVs exported from Spark Membership
and migrate them into the Dojo Manager (Odoo) database.

Supported imports
-----------------
  • Members       → res.partner  (is_member=True)
  • Contracts     → disaster.member.contract
  • Attendance    → disaster.class.attendance  (+ creates sessions as needed)
  • Leads         → disaster.lead
  • Payments      → account.move (out_invoice, posted)
  • Belt History  → updates res.partner.belt_rank

Sample CSVs live in:
  /opt/odoo19/odoo19/custom-addons/disaster_member_belts/Transfer_Spark_Folder/

Usage
-----
  Dojo Manager → Configuration → Import from Spark
"""

import base64
import csv
import io
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ── Belt rank normalisation ────────────────────────────────────────────────
BELT_MAP = {
    'white': 'white', 'white belt': 'white',
    'yellow': 'yellow', 'yellow belt': 'yellow',
    'orange': 'orange', 'orange belt': 'orange',
    'green': 'green', 'green belt': 'green',
    'blue': 'blue', 'blue belt': 'blue',
    'purple': 'purple', 'purple belt': 'purple',
    'brown': 'brown', 'brown belt': 'brown',
    'red': 'red', 'red belt': 'red',
    'black': 'black', 'black belt': 'black',
    '': 'white',
}

# ── Member stage normalisation ─────────────────────────────────────────────
STAGE_MAP = {
    'active': 'active', 'member': 'active', 'paid': 'active',
    'trial': 'trial', 'trial member': 'trial',
    'lead': 'lead', 'prospect': 'lead', 'new': 'lead',
    'inactive': 'inactive', 'lapsed': 'inactive',
    'cancelled': 'inactive', 'expired': 'inactive',
    '': 'lead',
}

# ── Lead stage normalisation ───────────────────────────────────────────────
LEAD_STAGE_MAP = {
    'new': 'new', 'open': 'new',
    'contacted': 'contacted', 'reached out': 'contacted',
    'appointment': 'appointment', 'scheduled': 'appointment',
    'trial': 'trial',
    'converted': 'converted', 'won': 'converted', 'signed up': 'converted',
    'lost': 'lost', 'closed': 'lost', 'no show': 'lost',
    '': 'new',
}

# ── Lead source normalisation ──────────────────────────────────────────────
SOURCE_MAP = {
    'walk_in': 'walk_in', 'walk in': 'walk_in', 'walkin': 'walk_in',
    'referral': 'referral', 'referred': 'referral',
    'social': 'social', 'instagram': 'social', 'facebook': 'social',
    'website': 'website', 'web': 'website', 'online': 'website',
    'phone': 'phone', 'call': 'phone',
    'event': 'event',
    '': 'other',
}

# ── Billing cycle normalisation ────────────────────────────────────────────
BILLING_MAP = {
    'monthly': 'monthly', 'month': 'monthly',
    'quarterly': 'quarterly', 'quarter': 'quarterly',
    'annual': 'annual', 'yearly': 'annual', 'year': 'annual',
    '': 'monthly',
}


def _parse_csv(file_data):
    """Decode base64-encoded CSV and return list of normalised dicts."""
    if not file_data:
        return []
    raw = base64.b64decode(file_data).decode('utf-8-sig', errors='replace')
    reader = csv.DictReader(io.StringIO(raw))
    rows = []
    for row in reader:
        rows.append({
            k.strip().lower().replace(' ', '_'): (v.strip() if v else '')
            for k, v in row.items()
            if k  # skip blank header cols
        })
    return rows


def _col(row, *keys):
    """Return first non-empty value from a list of possible column names."""
    for k in keys:
        v = row.get(k, '')
        if v:
            return v
    return ''


class SparkMigrationWizard(models.TransientModel):
    _name = 'disaster.spark.migration.wizard'
    _description = 'Import from Spark Membership (CSV)'

    # ── File uploads ────────────────────────────────────────────────────────
    members_file = fields.Binary(string='Members CSV', attachment=False)
    members_filename = fields.Char()
    contracts_file = fields.Binary(string='Contracts CSV', attachment=False)
    contracts_filename = fields.Char()
    attendance_file = fields.Binary(string='Attendance CSV', attachment=False)
    attendance_filename = fields.Char()
    leads_file = fields.Binary(string='Leads CSV', attachment=False)
    leads_filename = fields.Char()
    payments_file = fields.Binary(string='Payments CSV', attachment=False)
    payments_filename = fields.Char()
    belt_history_file = fields.Binary(string='Belt History CSV', attachment=False)
    belt_history_filename = fields.Char()

    # ── Options ─────────────────────────────────────────────────────────────
    overwrite_existing = fields.Boolean(
        string='Overwrite existing records (match by email)',
        default=False,
    )
    create_portal_users = fields.Boolean(
        string='Create portal login accounts for imported members',
        default=True,
    )
    dry_run = fields.Boolean(
        string='Dry run — validate only, do not save anything',
        default=False,
    )

    # ── Result ───────────────────────────────────────────────────────────────
    state = fields.Selection(
        [('draft', 'Ready'), ('done', 'Complete')],
        default='draft',
        string='State',
    )
    result_summary = fields.Text(string='Import Summary', readonly=True)

    # ── Private helpers ──────────────────────────────────────────────────────

    def _find_partner(self, email):
        if not email:
            return self.env['res.partner'].browse()
        return self.env['res.partner'].search(
            [('email', '=ilike', email.strip())], limit=1)

    def _get_or_create_plan(self, plan_name, billing_raw, price_raw):
        Plan = self.env['disaster.membership.plan']
        name = plan_name.strip() or 'Imported Plan'
        plan = Plan.search([('name', 'ilike', name)], limit=1)
        if not plan:
            try:
                price = float(str(price_raw).replace('$', '').replace(',', ''))
            except (ValueError, TypeError):
                price = 0.0
            plan = Plan.create({
                'name': name,
                'billing_cycle': BILLING_MAP.get(billing_raw.lower(), 'monthly'),
                'price': price,
            })
        return plan

    def _get_or_create_session(self, class_name, checkin_dt_str):
        """Return matching session or a shared 'Imported Attendance' session."""
        Session = self.env['disaster.class.session']
        if class_name and checkin_dt_str and len(checkin_dt_str) >= 10:
            date_part = checkin_dt_str[:10]
            session = Session.search([
                ('name', 'ilike', class_name),
                ('date_start', '>=', date_part + ' 00:00:00'),
                ('date_start', '<=', date_part + ' 23:59:59'),
            ], limit=1)
            if session:
                return session
        # Fall back to the shared import session
        session = Session.search([('name', '=', 'Spark Import — Attendance')], limit=1)
        if not session:
            session = Session.create({
                'name': 'Spark Import — Attendance',
                'class_type': 'general',
                'date_start': fields.Datetime.now(),
                'state': 'done',
            })
        return session

    # ── Step 1: Members ──────────────────────────────────────────────────────

    def _import_members(self, rows, partner_map, stats):
        portal_gid = self.env.ref('base.group_portal').id
        for row in rows:
            try:
                first = _col(row, 'first_name', 'firstname')
                last = _col(row, 'last_name', 'lastname')
                name = _col(row, 'name', 'full_name') or f'{first} {last}'.strip() or 'Unknown'
                email = _col(row, 'email', 'email_address').lower()

                belt_raw = _col(row, 'belt_rank', 'belt', 'rank').lower()
                stage_raw = _col(row, 'status', 'member_stage', 'stage').lower()

                # Warn on unrecognised selection values instead of silently defaulting
                belt = BELT_MAP.get(belt_raw)
                if belt is None:
                    stats['errors'].append(
                        f'{email}: unknown belt_rank "{belt_raw}" → defaulted to white')
                    belt = 'white'

                stage = STAGE_MAP.get(stage_raw)
                if stage is None:
                    stats['errors'].append(
                        f'{email}: unknown status "{stage_raw}" → defaulted to lead')
                    stage = 'lead'

                att = 0
                for c in ('total_attendance', 'attendance_count', 'check_ins', 'total_checkins'):
                    v = row.get(c, '')
                    if v:
                        try:
                            att = int(float(v))
                            break
                        except (ValueError, TypeError):
                            stats['errors'].append(
                                f'{email}: non-numeric attendance value "{v}" → set to 0')

                vals = {
                    'name': name,
                    'email': email,
                    'phone': _col(row, 'phone', 'mobile', 'phone_number'),
                    'is_member': True,
                    'belt_rank': belt,
                    'member_stage': stage,
                    'attendance_count': att,
                }
                dob = _col(row, 'date_of_birth', 'dob', 'birthday')
                if dob:
                    vals['date_of_birth'] = dob

                existing = self._find_partner(email)
                if existing:
                    if self.overwrite_existing:
                        if not self.dry_run:
                            existing.write(vals)
                        partner_map[email] = existing
                        stats['updated'] += 1
                    else:
                        partner_map[email] = existing
                        stats['skipped'] += 1
                else:
                    if not self.dry_run:
                        partner = self.env['res.partner'].create(vals)
                        partner_map[email] = partner
                        if self.create_portal_users and email:
                            if not self.env['res.users'].search([('login', '=', email)], limit=1):
                                self.env['res.users'].create({
                                    'name': name,
                                    'login': email,
                                    'password': 'member123',
                                    'partner_id': partner.id,
                                    'group_ids': [(6, 0, [portal_gid])],
                                })
                    stats['created'] += 1
            except Exception as e:
                stats['errors'].append(f'{_col(row, "email")}: {e}')
                _logger.warning('Spark import member error: %s', e)

    # ── Step 2: Belt History ─────────────────────────────────────────────────

    def _import_belt_history(self, rows, partner_map, stats):
        for row in rows:
            try:
                email = _col(row, 'email').lower()
                partner = partner_map.get(email) or self._find_partner(email)
                if not partner:
                    stats['errors'].append(f'Member not found: {email}')
                    continue
                belt_raw = _col(row, 'belt_rank', 'belt').lower()
                belt = BELT_MAP.get(belt_raw)
                if belt is None:
                    stats['errors'].append(
                        f'{email}: unknown belt_rank "{belt_raw}" — row skipped')
                    continue
                if not self.dry_run:
                    partner.belt_rank = belt
                stats['updated'] += 1
            except Exception as e:
                stats['errors'].append(str(e))

    # ── Step 3: Contracts ────────────────────────────────────────────────────

    def _import_contracts(self, rows, partner_map, stats):
        for row in rows:
            try:
                email = _col(row, 'email', 'member_email').lower()
                partner = partner_map.get(email) or self._find_partner(email)
                if not partner:
                    stats['skipped'] += 1
                    continue

                plan_name = _col(row, 'plan_name', 'plan', 'membership_plan')
                billing_raw = _col(row, 'billing_cycle', 'frequency').lower()
                price_raw = _col(row, 'price', 'amount', 'monthly_fee')
                plan = self._get_or_create_plan(plan_name, billing_raw, price_raw)

                start = _col(row, 'start_date', 'contract_start', 'date_start') or str(fields.Date.today())
                end = _col(row, 'end_date', 'contract_end', 'date_end') or False
                status_raw = _col(row, 'status', 'contract_status').lower()
                state = ('active' if 'active' in status_raw
                         else 'expired' if any(k in status_raw for k in ('expir', 'lapse'))
                         else 'cancelled' if 'cancel' in status_raw
                         else 'draft')

                existing = self.env['disaster.member.contract'].search([
                    ('partner_id', '=', partner.id),
                    ('plan_id', '=', plan.id),
                ], limit=1)
                if existing:
                    stats['skipped'] += 1
                    continue

                if not self.dry_run:
                    self.env['disaster.member.contract'].create({
                        'partner_id': partner.id,
                        'plan_id': plan.id,
                        'date_start': start,
                        'date_end': end or False,
                        'state': state,
                        'price': float(price_raw.replace('$', '').replace(',', '') or 0),
                    })
                stats['created'] += 1
            except Exception as e:
                stats['errors'].append(str(e))
                _logger.warning('Spark import contract error: %s', e)

    # ── Step 4: Attendance ───────────────────────────────────────────────────

    def _import_attendance(self, rows, partner_map, stats):
        for row in rows:
            try:
                email = _col(row, 'email', 'member_email').lower()
                partner = partner_map.get(email) or self._find_partner(email)
                if not partner:
                    stats['skipped'] += 1
                    continue

                checkin = _col(row, 'check_in', 'checkin_time', 'date', 'attendance_date')
                class_name = _col(row, 'class_name', 'class', 'session_name')
                session = self._get_or_create_session(class_name, checkin)

                existing = self.env['disaster.class.attendance'].search([
                    ('partner_id', '=', partner.id),
                    ('session_id', '=', session.id),
                ], limit=1)
                if existing:
                    stats['skipped'] += 1
                    continue

                if not self.dry_run:
                    self.env['disaster.class.attendance'].create({
                        'partner_id': partner.id,
                        'session_id': session.id,
                        'check_in': checkin or fields.Datetime.now(),
                    })
                stats['created'] += 1
            except Exception as e:
                stats['errors'].append(str(e))
                _logger.warning('Spark import attendance error: %s', e)

    # ── Step 5: Leads ────────────────────────────────────────────────────────

    def _import_leads(self, rows, stats):
        for row in rows:
            try:
                first = _col(row, 'first_name', 'firstname')
                last = _col(row, 'last_name', 'lastname')
                name = _col(row, 'name', 'full_name') or f'{first} {last}'.strip() or 'Unknown'
                email = _col(row, 'email', 'email_address').lower()
                stage_raw = _col(row, 'stage', 'status').lower()
                source_raw = _col(row, 'source', 'lead_source').lower()

                stage = LEAD_STAGE_MAP.get(stage_raw)
                if stage is None:
                    stats['errors'].append(
                        f'{email}: unknown lead stage "{stage_raw}" → defaulted to new')
                    stage = 'new'

                source = SOURCE_MAP.get(source_raw)
                if source is None:
                    stats['errors'].append(
                        f'{email}: unknown source "{source_raw}" → defaulted to other')
                    source = 'other'

                existing = self.env['disaster.lead'].search(
                    [('email', '=', email)], limit=1) if email else None
                if existing:
                    stats['skipped'] += 1
                    continue

                if not self.dry_run:
                    self.env['disaster.lead'].create({
                        'name': name,
                        'email': email,
                        'phone': _col(row, 'phone', 'mobile'),
                        'stage': stage,
                        'source': source,
                        'notes': _col(row, 'notes', 'comments'),
                    })
                stats['created'] += 1
            except Exception as e:
                stats['errors'].append(str(e))
                _logger.warning('Spark import lead error: %s', e)

    # ── Step 6: Payments ─────────────────────────────────────────────────────

    def _import_payments(self, rows, partner_map, stats):
        journal = self.env['account.journal'].search(
            [('type', '=', 'sale'), ('company_id', '=', self.env.company.id)],
            limit=1,
        )
        if not journal:
            stats['errors'].append('No Sales journal found — skipping all payments')
            return

        for row in rows:
            try:
                email = _col(row, 'email', 'member_email').lower()
                partner = partner_map.get(email) or self._find_partner(email)
                if not partner:
                    stats['skipped'] += 1
                    continue

                amount_raw = _col(row, 'amount', 'payment_amount')
                try:
                    amount = float(str(amount_raw).replace('$', '').replace(',', ''))
                except (ValueError, TypeError):
                    amount = 0.0
                if amount <= 0:
                    stats['skipped'] += 1
                    continue

                date_raw = _col(row, 'date', 'payment_date') or str(fields.Date.today())
                description = _col(row, 'description', 'plan', 'notes') or 'Imported Payment'

                if not self.dry_run:
                    move = self.env['account.move'].create({
                        'move_type': 'out_invoice',
                        'partner_id': partner.id,
                        'invoice_date': date_raw[:10],
                        'journal_id': journal.id,
                        'invoice_line_ids': [(0, 0, {
                            'name': description,
                            'quantity': 1.0,
                            'price_unit': amount,
                        })],
                    })
                    move.action_post()
                stats['created'] += 1
            except Exception as e:
                stats['errors'].append(str(e))
                _logger.warning('Spark import payment error: %s', e)

    # ── Main action ──────────────────────────────────────────────────────────

    def action_import(self):
        self.ensure_one()

        partner_map = {}  # email → res.partner (built during member import)

        # Per-section stats template
        def new_stats():
            return {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}

        s_members = new_stats()
        s_belt = new_stats()
        s_contracts = new_stats()
        s_attendance = new_stats()
        s_leads = new_stats()
        s_payments = new_stats()

        # Run each section
        members_rows = _parse_csv(self.members_file)
        if members_rows:
            self._import_members(members_rows, partner_map, s_members)

        belt_rows = _parse_csv(self.belt_history_file)
        if belt_rows:
            self._import_belt_history(belt_rows, partner_map, s_belt)

        contract_rows = _parse_csv(self.contracts_file)
        if contract_rows:
            self._import_contracts(contract_rows, partner_map, s_contracts)

        attendance_rows = _parse_csv(self.attendance_file)
        if attendance_rows:
            self._import_attendance(attendance_rows, partner_map, s_attendance)

        leads_rows = _parse_csv(self.leads_file)
        if leads_rows:
            self._import_leads(leads_rows, s_leads)

        payment_rows = _parse_csv(self.payments_file)
        if payment_rows:
            self._import_payments(payment_rows, partner_map, s_payments)

        # ── Build summary text ───────────────────────────────────────────────
        mode = '⚠️  DRY RUN — nothing was saved\n\n' if self.dry_run else '✅ IMPORT COMPLETE\n\n'
        sections = [
            ('👥 MEMBERS',       s_members),
            ('🥋 BELT HISTORY',  s_belt),
            ('📋 CONTRACTS',     s_contracts),
            ('✅ ATTENDANCE',    s_attendance),
            ('🎯 LEADS',         s_leads),
            ('💳 PAYMENTS',      s_payments),
        ]
        lines = [mode]
        any_files = any([
            self.members_file, self.belt_history_file, self.contracts_file,
            self.attendance_file, self.leads_file, self.payments_file,
        ])
        if not any_files:
            lines.append('No files were uploaded. Please upload at least one CSV.')
        else:
            for title, st in sections:
                total = st['created'] + st['updated'] + st['skipped']
                if total == 0 and not st['errors']:
                    continue
                lines.append(f'{title}')
                lines.append(f'  Created : {st["created"]}')
                if st['updated']:
                    lines.append(f'  Updated : {st["updated"]}')
                if st['skipped']:
                    lines.append(f'  Skipped : {st["skipped"]}')
                if st['errors']:
                    lines.append(f'  ⚠  Errors: {len(st["errors"])}')
                    for e in st['errors'][:5]:
                        lines.append(f'     • {e}')
                    if len(st['errors']) > 5:
                        lines.append(f'     … and {len(st["errors"]) - 5} more')
                lines.append('')

        self.result_summary = '\n'.join(lines)
        self.state = 'done'

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_reset(self):
        self.write({
            'state': 'draft',
            'result_summary': False,
            'members_file': False, 'members_filename': False,
            'contracts_file': False, 'contracts_filename': False,
            'attendance_file': False, 'attendance_filename': False,
            'leads_file': False, 'leads_filename': False,
            'payments_file': False, 'payments_filename': False,
            'belt_history_file': False, 'belt_history_filename': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
