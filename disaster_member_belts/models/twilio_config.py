# -*- coding: utf-8 -*-
"""
twilio_config.py
----------------
Extends res.company with Dojo voice-call settings.

SMS credentials (Account SID, Auth Token, from-numbers) are fully managed by
the built-in `sms_twilio` Odoo addon under:
  General Settings -> SMS -> SMS Provider = Twilio -> Manage Twilio Account

This file ONLY adds voice-call fields that sms_twilio does not provide.
Voice calls are placed directly via the Twilio Voice REST API (requests),
using the credentials already stored on res.company by sms_twilio.
"""

from odoo import fields, models


class ResCompanyVoip(models.Model):
    _inherit = 'res.company'

    # ------------------------------------------------------------------
    # Voice / VoIP settings
    # (SMS credentials live on res.company via the sms_twilio addon)
    # ------------------------------------------------------------------
    dojo_call_enabled = fields.Boolean(
        string='Enable Outbound Voice Calls',
        default=False,
        help='Allow staff to place a Twilio voice call to a guardian from '
             'the Attendance Roster or member contact form. '
             'Requires Twilio credentials in General Settings -> SMS -> Twilio.',
    )
    dojo_call_twiml_url = fields.Char(
        string='Voice Greeting (TwiML URL)',
        default='https://demo.twilio.com/welcome/voice/',
        help='Twilio fetches this URL when the call is answered and executes '
             'the TwiML instructions (play a message, gather input, etc.). '
             'Create a free TwiML Bin at console.twilio.com -> TwiML Bins.',
    )
    dojo_call_timeout = fields.Integer(
        string='Ring Timeout (seconds)',
        default=30,
        help='How many seconds to let the phone ring before hanging up.',
    )
    dojo_call_status_callback = fields.Char(
        string='Status Callback URL',
        help='Optional webhook Twilio posts call-status updates to '
             '(completed / failed / no-answer).  Leave blank if not needed.',
    )


class ResConfigSettingsVoip(models.TransientModel):
    _inherit = 'res.config.settings'

    dojo_call_enabled = fields.Boolean(
        related='company_id.dojo_call_enabled',
        readonly=False,
        string='Enable Outbound Voice Calls',
    )
    dojo_call_twiml_url = fields.Char(
        related='company_id.dojo_call_twiml_url',
        readonly=False,
        string='Voice Greeting (TwiML URL)',
    )
    dojo_call_timeout = fields.Integer(
        related='company_id.dojo_call_timeout',
        readonly=False,
        string='Ring Timeout (seconds)',
    )
    dojo_call_status_callback = fields.Char(
        related='company_id.dojo_call_status_callback',
        readonly=False,
        string='Status Callback URL',
    )
