from odoo import models

from odoo.addons.dojo_sms_twilio.tools.sms_api_twilio import SmsApiTwilio


class ResCompany(models.Model):
    _inherit = "res.company"

    def _get_sms_api_class(self):
        """Return Twilio SMS provider if configured; fall back to default IAP otherwise."""
        self.ensure_one()
        ICP = self.env["ir.config_parameter"].sudo()
        sid = ICP.get_param("twilio.account_sid", "").strip()
        token = ICP.get_param("twilio.auth_token", "").strip()
        if sid and token:
            return SmsApiTwilio
        # Fall back to standard IAP provider
        return super()._get_sms_api_class()
