# -*- coding: utf-8 -*-
"""
dojo_automation_rule.py
-----------------------
Automation rule builder for dojo events.

dojo.automation.rule   – the trigger + filter + name
dojo.automation.action – one action within a rule (many per rule)
"""

import json
import logging

import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TRIGGER_SELECTION = [
    ('membership_created',   'Membership Created'),
    ('membership_activated', 'Membership Activated'),
    ('membership_past_due',  'Membership Past Due'),
    ('membership_cancelled', 'Membership Cancelled'),
    ('membership_on_hold',   'Membership Put On Hold'),
    ('checkin',              'Member Checked In'),
    ('no_show',              'Member No-Show'),
    ('belt_test_passed',     'Belt Test Passed'),
    ('belt_test_failed',     'Belt Test Failed'),
    ('lead_created',         'Lead Created'),
    ('lead_converted',       'Lead Converted to Member'),
    ('anniversary',          'Membership Anniversary'),
    ('custom',               'Custom / Manual'),
]

ACTION_TYPE_SELECTION = [
    ('tag',           'Add / Remove Tag'),
    ('email',         'Send Email'),
    ('sms',           'Send SMS'),
    ('push',          'Send Push Notification'),
    ('webhook',       'HTTP Webhook'),
    ('create_activity', 'Create Activity'),
    ('update_field',  'Update Field on Record'),
]


class DojoAutomationRule(models.Model):
    _name = 'dojo.automation.rule'
    _description = 'Dojo Automation Rule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'

    name = fields.Char(string='Rule Name', required=True, tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Dojo',
        default=lambda self: self.env.company,
    )
    trigger = fields.Selection(
        TRIGGER_SELECTION, string='Trigger', required=True, tracking=True,
    )
    domain_filter = fields.Char(
        string='Filter (domain)',
        help='Odoo domain applied to the partner/record before executing actions. '
             'Leave empty to run for all records. '
             'E.g. [("belt_rank","=","blue")]',
    )
    description = fields.Text(string='Description / Notes')
    action_ids = fields.One2many(
        'dojo.automation.action', 'rule_id', string='Actions',
    )
    run_count = fields.Integer(string='Times Run', default=0, readonly=True)
    last_run_dt = fields.Datetime(string='Last Run', readonly=True)

    # ── Execute ──────────────────────────────────────────────────────
    def execute_for_partner(self, partner):
        """Execute this rule for a given partner record."""
        self.ensure_one()
        # Apply domain filter
        if self.domain_filter:
            try:
                import ast
                domain = ast.literal_eval(self.domain_filter) + [('id', '=', partner.id)]
                if not self.env['res.partner'].search_count(domain):
                    return  # partner doesn't match filter
            except Exception as e:
                _logger.warning('dojo.automation.rule %s: invalid domain: %s', self.name, e)

        for action in self.action_ids:
            try:
                action.execute(partner)
            except Exception as e:
                _logger.error('dojo.automation.action %s failed: %s', action.id, e)

        self.write({
            'run_count': self.run_count + 1,
            'last_run_dt': fields.Datetime.now(),
        })

    @api.model
    def fire_trigger(self, trigger_key, partner_id):
        """Called from other modules when a trigger event occurs."""
        rules = self.search([
            ('trigger', '=', trigger_key),
            ('active', '=', True),
        ])
        partner = self.env['res.partner'].browse(partner_id)
        for rule in rules:
            rule.execute_for_partner(partner)

    def action_test_run(self):
        """Manual test: pick first active member and run rule."""
        self.ensure_one()
        partner = self.env['res.partner'].search(
            [('is_member', '=', True), ('member_stage', '=', 'active')], limit=1
        )
        if not partner:
            raise UserError(_('No active member found to test with.'))
        self.execute_for_partner(partner)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Test Run Complete'),
                'message': _('Rule "%s" executed for %s.') % (self.name, partner.name),
                'type': 'success',
            },
        }


class DojoAutomationAction(models.Model):
    _name = 'dojo.automation.action'
    _description = 'Automation Action Step'
    _order = 'sequence, id'

    rule_id = fields.Many2one(
        'dojo.automation.rule', string='Rule',
        required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)
    action_type = fields.Selection(
        ACTION_TYPE_SELECTION, string='Action Type', required=True, default='email',
    )
    config_json = fields.Text(
        string='Configuration (JSON)',
        help='JSON config specific to the action type.',
    )
    # Convenience fields (populated based on action_type)
    email_template_id = fields.Many2one(
        'mail.template', string='Email Template', ondelete='set null',
    )
    sms_body = fields.Text(string='SMS Body')
    push_title = fields.Char(string='Push Title')
    push_body = fields.Text(string='Push Body')
    webhook_url = fields.Char(string='Webhook URL')
    webhook_method = fields.Selection(
        [('POST', 'POST'), ('GET', 'GET'), ('PUT', 'PUT')],
        string='HTTP Method', default='POST',
    )
    webhook_headers = fields.Text(
        string='Headers (JSON)', default='{"Content-Type": "application/json"}',
    )
    activity_type_id = fields.Many2one(
        'mail.activity.type', string='Activity Type', ondelete='set null',
    )
    activity_summary = fields.Char(string='Activity Summary')
    tag_ids = fields.Many2many(
        'res.partner.category', string='Tags to Add',
        relation='dojo_auto_action_tag_add_rel',
    )
    tag_remove_ids = fields.Many2many(
        'res.partner.category', string='Tags to Remove',
        relation='dojo_auto_action_tag_rm_rel',
    )

    # ── Execute ─────────────────────────────────────────────────────
    def execute(self, partner):
        """Execute this single action against a partner."""
        self.ensure_one()
        atype = self.action_type

        if atype == 'tag':
            if self.tag_ids:
                partner.sudo().category_id = [(4, t.id) for t in self.tag_ids]
            if self.tag_remove_ids:
                partner.sudo().category_id = [(3, t.id) for t in self.tag_remove_ids]

        elif atype == 'email' and self.email_template_id:
            self.email_template_id.sudo().send_mail(partner.id, force_send=True)

        elif atype == 'sms' and self.sms_body:
            number = partner.mobile or partner.phone
            if number:
                self.env['sms.sms'].sudo().create({
                    'number': number,
                    'body': self.sms_body,
                    'partner_id': partner.id,
                }).send()

        elif atype == 'push' and (self.push_title or self.push_body):
            self.env['dojo.push.device'].send_to_partners(
                [partner.id],
                title=self.push_title or '',
                body=self.push_body or '',
            )

        elif atype == 'webhook' and self.webhook_url:
            self._fire_webhook(partner)

        elif atype == 'create_activity' and self.activity_type_id:
            partner.activity_schedule(
                activity_type_id=self.activity_type_id.id,
                summary=self.activity_summary or self.rule_id.name,
            )

    def _fire_webhook(self, partner):
        """POST JSON payload to webhook_url."""
        try:
            headers = json.loads(self.webhook_headers or '{}')
        except json.JSONDecodeError:
            headers = {'Content-Type': 'application/json'}

        payload = {
            'trigger': self.rule_id.trigger,
            'rule': self.rule_id.name,
            'partner_id': partner.id,
            'partner_name': partner.name,
            'partner_email': partner.email or '',
            'partner_phone': partner.phone or '',
            'belt_rank': partner.belt_rank or '',
            'member_stage': partner.member_stage or '',
        }

        # Merge extra config from config_json
        if self.config_json:
            try:
                extra = json.loads(self.config_json)
                payload.update(extra)
            except json.JSONDecodeError:
                pass

        method = (self.webhook_method or 'POST').upper()
        try:
            resp = requests.request(
                method, self.webhook_url,
                json=payload, headers=headers, timeout=10,
            )
            resp.raise_for_status()
            _logger.info('Webhook %s → %s: %s', self.webhook_url, method, resp.status_code)
        except Exception as e:
            _logger.error('Webhook failed for rule %s: %s', self.rule_id.name, e)
