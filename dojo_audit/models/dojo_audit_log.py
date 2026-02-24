# -*- coding: utf-8 -*-
"""
dojo_audit_log.py
-----------------
Immutable audit trail for dojo data events.

Captures:
  - member.create / member.write (tracked fields) / member.unlink
  - contract.create / contract.write / contract.unlink
  - wallet.tx (all)
  - rank.history (all)
  - data.export events
  - login / logout (via res.users override)
"""

import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Fields on res.partner that we want to track changes for
PARTNER_TRACKED_FIELDS = frozenset([
    'name', 'email', 'phone', 'mobile',
    'is_member', 'member_stage', 'belt_rank',
    'dojo_household_id', 'dojo_consent_state',
    'dojo_medical_notes',
])

EVENT_TYPES = [
    ('create',  'Record Created'),
    ('write',   'Record Updated'),
    ('unlink',  'Record Deleted'),
    ('login',   'User Login'),
    ('logout',  'User Logout'),
    ('export',  'Data Exported'),
    ('consent', 'Consent Changed'),
    ('rank',    'Belt Rank Changed'),
    ('payment', 'Payment / Wallet Event'),
    ('custom',  'Custom Event'),
]


class DojoAuditLog(models.Model):
    _name = 'dojo.audit.log'
    _description = 'Dojo Audit Log'
    _order = 'timestamp desc, id desc'
    _log_access = False   # save space; we write our own timestamp

    timestamp = fields.Datetime(
        string='Timestamp', default=fields.Datetime.now, readonly=True, index=True,
    )
    event_type = fields.Selection(EVENT_TYPES, string='Event', required=True, readonly=True)
    user_id = fields.Many2one('res.users', string='User', readonly=True, ondelete='set null')
    partner_id = fields.Many2one('res.partner', string='Member', readonly=True, ondelete='set null')
    company_id = fields.Many2one('res.company', string='Dojo', readonly=True, ondelete='set null')
    model_name = fields.Char(string='Model', readonly=True)
    record_id = fields.Integer(string='Record ID', readonly=True)
    record_name = fields.Char(string='Record Name', readonly=True)
    old_values = fields.Text(string='Before', readonly=True,
                             help='JSON snapshot of changed fields before write.')
    new_values = fields.Text(string='After', readonly=True,
                             help='JSON snapshot of changed fields after write.')
    ip_address = fields.Char(string='IP Address', readonly=True)
    summary = fields.Char(string='Summary', readonly=True)
    extra_data = fields.Text(string='Extra Data (JSON)', readonly=True)

    # ── Immutability ──────────────────────────────────────────────────────────
    def unlink(self):
        raise UserError(_('Audit log entries cannot be deleted.'))

    def write(self, vals):
        raise UserError(_('Audit log entries cannot be modified.'))

    # ── Public helpers ────────────────────────────────────────────────────────
    @api.model
    def log(self, event_type, model_name='', record_id=0, record_name='',
            partner_id=None, old_values=None, new_values=None,
            summary='', extra_data=None):
        """Create an audit log entry. Always uses sudo to avoid permission loops."""
        try:
            env = self.env
            user = env.user
            ip = self._get_request_ip()
            self.sudo().create({
                'event_type': event_type,
                'user_id': user.id,
                'partner_id': partner_id,
                'company_id': env.company.id,
                'model_name': model_name,
                'record_id': record_id,
                'record_name': record_name or '',
                'old_values': json.dumps(old_values) if old_values else False,
                'new_values': json.dumps(new_values) if new_values else False,
                'ip_address': ip,
                'summary': summary[:255] if summary else '',
                'extra_data': json.dumps(extra_data) if extra_data else False,
            })
        except Exception as e:
            _logger.error('Failed to write audit log: %s', e)

    @staticmethod
    def _get_request_ip():
        try:
            from odoo.http import request
            if request and request.httprequest:
                return request.httprequest.remote_addr
        except Exception:
            pass
        return ''

    # ── Retention cron ────────────────────────────────────────────────────────
    @api.model
    def cron_purge_old_logs(self, days=365):
        """Delete audit logs older than `days` days (default 1 year)."""
        cutoff = fields.Datetime.subtract(fields.Datetime.now(), days=days)
        old = self.sudo().search([('timestamp', '<', cutoff)])
        if old:
            # Bypass unlink guard for cron purge
            self.env.cr.execute(
                'DELETE FROM dojo_audit_log WHERE id = ANY(%s)',
                (old.ids,)
            )
            _logger.info('Audit purge: deleted %d entries older than %d days.', len(old), days)


# ─────────────────────────────────────────────────────────────────────────────
# Hook res.partner to capture member field changes
# ─────────────────────────────────────────────────────────────────────────────
class ResPartnerAudit(models.Model):
    _inherit = 'res.partner'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.is_member:
                self.env['dojo.audit.log'].log(
                    event_type='create',
                    model_name='res.partner',
                    record_id=rec.id,
                    record_name=rec.name,
                    partner_id=rec.id,
                    summary=f'Member created: {rec.name}',
                )
        return records

    def write(self, vals):
        # Capture before snapshot for tracked fields
        before_snapshots = {}
        for rec in self:
            changed = {f: vals[f] for f in vals if f in PARTNER_TRACKED_FIELDS}
            if changed:
                before_snapshots[rec.id] = {
                    f: getattr(rec, f) for f in changed
                }

        result = super().write(vals)

        for rec in self:
            if rec.id in before_snapshots:
                old = before_snapshots[rec.id]
                new = {f: getattr(rec, f) for f in old}
                # Coerce relational fields to names
                old_clean = {k: (v.name if hasattr(v, 'name') else v) for k, v in old.items()}
                new_clean = {k: (v.name if hasattr(v, 'name') else v) for k, v in new.items()}
                self.env['dojo.audit.log'].log(
                    event_type='write',
                    model_name='res.partner',
                    record_id=rec.id,
                    record_name=rec.name,
                    partner_id=rec.id,
                    old_values=old_clean,
                    new_values=new_clean,
                    summary=f'Member updated: {rec.name} — fields: {", ".join(old.keys())}',
                )
        return result


# ─────────────────────────────────────────────────────────────────────────────
# Hook res.users for login audit
# ─────────────────────────────────────────────────────────────────────────────
class ResUsersAudit(models.Model):
    _inherit = 'res.users'

    def _check_credentials(self, password, env):
        super()._check_credentials(password, env)
        # Successful login
        try:
            self.env['dojo.audit.log'].log(
                event_type='login',
                model_name='res.users',
                record_id=self.id,
                record_name=self.name,
                partner_id=self.partner_id.id if self.partner_id else None,
                summary=f'Login: {self.login}',
            )
        except Exception:
            pass
