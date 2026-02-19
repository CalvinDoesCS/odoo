# -*- coding: utf-8 -*-
"""
broadcast_wizard.py
-------------------
Bulk SMS / Email broadcast wizard.

Sends a message to a filtered set of members via:
  - Email   (mail.mail)
  - SMS     (sms.sms — requires the `sms` module)
  - Both

Filters
-------
  all           – every partner with is_member=True
  active        – member_stage == 'active'
  trial         – member_stage == 'trial'
  lead          – member_stage == 'lead'
  belt_rank     – specific belt rank(s)
  instructor    – is_instructor == True
  specific      – manually chosen partner_ids
"""

from odoo import api, fields, models


class DojoBroadcastWizard(models.TransientModel):
    _name = 'disaster.broadcast.wizard'
    _description = 'Dojo Broadcast Message Wizard'

    # ------------------------------------------------------------------
    # Message content
    # ------------------------------------------------------------------
    subject = fields.Char(string='Subject', required=True)
    body = fields.Text(string='Message Body', required=True)

    # ------------------------------------------------------------------
    # Channel
    # ------------------------------------------------------------------
    channel = fields.Selection(
        selection=[
            ('email', 'Email Only'),
            ('sms',   'SMS Only'),
            ('both',  'Email + SMS'),
        ],
        string='Send Via',
        default='email',
        required=True,
    )

    # ------------------------------------------------------------------
    # Recipient filter
    # ------------------------------------------------------------------
    recipient_filter = fields.Selection(
        selection=[
            ('all',        'All Members'),
            ('active',     'Active Members'),
            ('trial',      'Trial Members'),
            ('lead',       'Leads'),
            ('belt_rank',  'By Belt Rank'),
            ('instructor', 'Instructors'),
            ('specific',   'Specific People'),
        ],
        string='Send To',
        default='active',
        required=True,
    )
    belt_rank_filter = fields.Selection(
        selection=[
            ('white',  'White'),
            ('yellow', 'Yellow'),
            ('orange', 'Orange'),
            ('green',  'Green'),
            ('blue',   'Blue'),
            ('purple', 'Purple'),
            ('brown',  'Brown'),
            ('red',    'Red'),
            ('black',  'Black'),
        ],
        string='Belt Rank',
    )
    specific_partner_ids = fields.Many2many(
        comodel_name='res.partner',
        string='Specific Recipients',
        domain="[('is_member', '=', True)]",
    )

    # ------------------------------------------------------------------
    # Preview / stats
    # ------------------------------------------------------------------
    recipient_count = fields.Integer(
        string='Recipients',
        compute='_compute_recipient_count',
    )

    @api.depends(
        'recipient_filter', 'belt_rank_filter', 'specific_partner_ids',
    )
    def _compute_recipient_count(self):
        for wiz in self:
            wiz.recipient_count = len(wiz._get_recipients())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _get_recipients(self):
        Partner = self.env['res.partner']
        rf = self.recipient_filter
        if rf == 'all':
            return Partner.search([('is_member', '=', True)])
        if rf == 'active':
            return Partner.search([('is_member', '=', True), ('member_stage', '=', 'active')])
        if rf == 'trial':
            return Partner.search([('is_member', '=', True), ('member_stage', '=', 'trial')])
        if rf == 'lead':
            return Partner.search([('is_member', '=', True), ('member_stage', '=', 'lead')])
        if rf == 'belt_rank':
            return Partner.search([
                ('is_member', '=', True),
                ('belt_rank', '=', self.belt_rank_filter),
            ])
        if rf == 'instructor':
            return Partner.search([('is_instructor', '=', True)])
        if rf == 'specific':
            return self.specific_partner_ids
        return Partner.browse()

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------
    def action_send(self):
        recipients = self._get_recipients()
        sent_email = sent_sms = 0

        for partner in recipients:
            if self.channel in ('email', 'both') and partner.email:
                mail_vals = {
                    'subject':   self.subject,
                    'body_html': f'<p>{self.body}</p>',
                    'email_to':  partner.email,
                    'auto_delete': True,
                }
                self.env['mail.mail'].create(mail_vals).send()
                sent_email += 1

            if self.channel in ('sms', 'both') and partner.phone:
                # Use Odoo's sms.sms model directly
                try:
                    self.env['sms.sms'].create({
                        'number':  partner.phone,
                        'body':    self.body,
                        'partner_id': partner.id,
                        'state':   'outgoing',
                    })
                    sent_sms += 1
                except Exception:
                    pass  # sms module may not be fully configured

        # Return a notification
        return {
            'type': 'ir.actions.client',
            'tag':  'display_notification',
            'params': {
                'title':   'Broadcast Sent',
                'message': (
                    f'✅ {sent_email} email(s) and {sent_sms} SMS(s) '
                    f'sent to {len(recipients)} recipient(s).'
                ),
                'sticky': False,
                'type':   'success',
            },
        }
