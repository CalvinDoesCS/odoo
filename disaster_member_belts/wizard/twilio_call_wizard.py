# -*- coding: utf-8 -*-
"""
twilio_call_wizard.py
---------------------
One-click outbound voice call to a student's parent / guardian via Twilio.

Uses the `sms_twilio` Odoo addon:
  * Credentials (Account SID, Auth Token) come from res.company,
    managed in General Settings -> SMS -> Twilio.
  * From-number comes from the first sms.twilio.number on the company.
  * Voice-call-specific settings (TwiML URL, timeout) live on
    res.company.dojo_call_* (added by this module).
  * Calls are placed via a direct HTTPS POST to the Twilio Voice REST API
    using the `requests` library -- no extra Python SDK required.
"""

import logging
import requests as _requests

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class TwilioCallWizard(models.TransientModel):
    _name = 'disaster.twilio.call.wizard'
    _description = 'Place Twilio Voice Call to Guardian'

    # -- Who to call -------------------------------------------------------
    student_id = fields.Many2one(
        comodel_name='res.partner',
        string='Student',
        readonly=True,
    )
    guardian_id = fields.Many2one(
        comodel_name='res.partner',
        string='Guardian / Parent',
    )
    call_number = fields.Char(
        string='Phone Number',
        help='Number to call in E.164 format (+15551234567). '
             'Auto-filled from the guardian record.',
    )

    # -- Context / reason --------------------------------------------------
    call_reason = fields.Selection(
        selection=[
            ('absence', 'Missed Class - Absence Notice'),
            ('general', 'General Enquiry'),
            ('billing', 'Billing / Payment'),
            ('belt_test', 'Belt Test Invitation'),
            ('emergency', 'Emergency'),
        ],
        string='Reason for Call',
        default='absence',
        required=True,
    )
    session_id = fields.Many2one(
        comodel_name='disaster.class.session',
        string='Session (if absence)',
    )
    notes = fields.Text(
        string='Notes',
    )

    # -- Company / credentials (computed) ----------------------------------
    call_enabled = fields.Boolean(
        string='Calls Enabled',
        compute='_compute_call_status',
    )
    call_from_number = fields.Char(
        string='Calling From',
        compute='_compute_call_status',
        help='First Twilio number on your company record.',
    )

    # -- Result ------------------------------------------------------------
    call_sid = fields.Char(string='Call SID', readonly=True)
    call_status = fields.Char(string='Call Status', readonly=True)

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        student_id = self.env.context.get('default_student_id')
        if student_id:
            student = self.env['res.partner'].browse(student_id)
            res['student_id'] = student.id
            if student.guardian_id:
                guardian = student.guardian_id
                res['guardian_id'] = guardian.id
                res['call_number'] = guardian.phone or ''
        return res

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    @api.depends()
    def _compute_call_status(self):
        company = self.env.company.sudo()
        enabled = (
            company.dojo_call_enabled
            and bool(company.sms_twilio_account_sid)
            and bool(company.sms_twilio_auth_token)
        )
        from_num = ''
        if enabled and company.sms_twilio_number_ids:
            from_num = company.sms_twilio_number_ids[0].number or ''
        for rec in self:
            rec.call_enabled = enabled and bool(from_num)
            rec.call_from_number = from_num

    @api.onchange('guardian_id')
    def _onchange_guardian(self):
        if self.guardian_id:
            self.call_number = self.guardian_id.phone or ''

    # ------------------------------------------------------------------
    # Action: Place call (via Twilio Voice REST API + requests)
    # ------------------------------------------------------------------
    def action_place_call(self):
        """Initiate a Twilio outbound voice call to the guardian."""
        self.ensure_one()
        company = self.env.company.sudo()

        if not company.dojo_call_enabled:
            raise UserError(
                'Outbound calling is not enabled. '
                'Go to General Settings -> SMS -> Twilio and enable '
                'Voice Calls under the Dojo VoIP section.'
            )
        if not company.sms_twilio_account_sid or not company.sms_twilio_auth_token:
            raise UserError(
                'Twilio credentials are not configured. '
                'Go to General Settings -> SMS -> SMS Provider = Twilio '
                '-> Manage Twilio Account.'
            )
        if not company.sms_twilio_number_ids:
            raise UserError(
                'No Twilio phone numbers are registered on your company. '
                'Add one in General Settings -> SMS -> Manage Twilio Account.'
            )
        if not self.call_number:
            raise UserError(
                'No phone number to call. '
                'Add a mobile / phone number to the guardian record.'
            )

        to_number = self.call_number.strip()
        if not to_number.startswith('+'):
            raise UserError(
                f'Phone number "{to_number}" must be in E.164 format (+countrycode...). '
                'Update the phone number on the guardian record.'
            )

        from_number = company.sms_twilio_number_ids[0].number
        account_sid = company.sms_twilio_account_sid
        auth_token  = company.sms_twilio_auth_token
        twiml_url   = company.dojo_call_twiml_url or 'https://demo.twilio.com/welcome/voice/'
        timeout     = company.dojo_call_timeout or 30

        # POST to Twilio Calls API
        url = f'https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Calls.json'
        payload = {
            'To':      to_number,
            'From':    from_number,
            'Url':     twiml_url,
            'Timeout': timeout,
        }
        if company.dojo_call_status_callback:
            payload['StatusCallback']       = company.dojo_call_status_callback
            payload['StatusCallbackMethod'] = 'POST'

        try:
            resp = _requests.post(
                url,
                data=payload,
                auth=(account_sid, auth_token),
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            self.call_sid    = data.get('sid', '')
            self.call_status = data.get('status', '')
        except _requests.exceptions.HTTPError as exc:
            try:
                err_msg = exc.response.json().get('message', str(exc))
            except Exception:
                err_msg = str(exc)
            _logger.error('Twilio call HTTP error for %s: %s', to_number, err_msg)
            raise UserError(f'Twilio call failed:\n{err_msg}')
        except Exception as exc:
            _logger.error('Twilio call error for %s: %s', to_number, exc)
            raise UserError(f'Call failed:\n{exc}')

        # Post a chatter note on the student's record
        reason_label = dict(self._fields['call_reason'].selection).get(
            self.call_reason, self.call_reason
        )
        guardian_name = self.guardian_id.name if self.guardian_id else to_number
        note_body = (
            f"<p>Outbound call initiated to guardian "
            f"<strong>{guardian_name}</strong> ({to_number})<br/>"
            f"Reason: {reason_label}<br/>"
            f"Twilio Call SID: <code>{self.call_sid}</code><br/>"
            f"Status: {self.call_status}"
            + (f"<br/>Session: {self.session_id.name}" if self.session_id else "")
            + (f"<br/>Notes: {self.notes}" if self.notes else "")
            + "</p>"
        )
        if self.student_id:
            try:
                self.student_id.sudo().message_post(
                    body=note_body,
                    message_type='note',
                    subtype_xmlid='mail.mt_note',
                )
            except Exception:
                pass

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Call Placed',
                'message': (
                    f'Calling {to_number} ... '
                    f'(SID: {self.call_sid}, Status: {self.call_status})'
                ),
                'type': 'success',
                'sticky': False,
            },
        }
