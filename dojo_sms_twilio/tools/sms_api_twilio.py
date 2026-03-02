import logging

from odoo.addons.sms.tools.sms_api import SmsApiBase

_logger = logging.getLogger(__name__)


class SmsApiTwilio(SmsApiBase):
    """
    Odoo 19 SMS API provider that routes messages through Twilio.
    Plugged in via res.company._get_sms_api_class() override.
    """

    # Odoo 19 SMS failure types understood by sms.sms._send_with_api()
    PROVIDER_TO_SMS_FAILURE_TYPE = SmsApiBase.PROVIDER_TO_SMS_FAILURE_TYPE | {}

    def __init__(self, env, account=None):
        super().__init__(env, account=account)
        ICP = env["ir.config_parameter"].sudo()
        self._sid = ICP.get_param("twilio.account_sid", "").strip()
        self._token = ICP.get_param("twilio.auth_token", "").strip()
        self._from = ICP.get_param("twilio.from_number", "").strip()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_client(self):
        if not self._sid or not self._token:
            return None
        try:
            from twilio.rest import Client  # noqa: PLC0415
            return Client(self._sid, self._token)
        except ImportError:
            _logger.error(
                "dojo_sms_twilio: 'twilio' Python package not installed. "
                "Run: pip install twilio"
            )
            return None
        except Exception as exc:  # noqa: BLE001
            _logger.error("dojo_sms_twilio: failed to init Twilio client: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Required interface  (Odoo 19)
    # _send_sms_batch receives grouped-by-content messages:
    #   [{ 'content': str, 'numbers': [{'uuid': str, 'number': str}, ...] }, ...]
    # Must return:
    #   [{ 'uuid': str, 'state': 'success'|'server_error'|..., 'credit': int }, ...]
    # ------------------------------------------------------------------

    def _send_sms_batch(self, messages, delivery_reports_url=False):
        client = self._get_client()
        if client is None:
            _logger.warning(
                "dojo_sms_twilio: Twilio not configured or unavailable. "
                "Messages will NOT be sent."
            )
            # Return server_error for all
            results = []
            for msg in messages:
                for num in msg.get("numbers", []):
                    results.append({"uuid": num["uuid"], "state": "server_error"})
            return results

        results = []
        for msg in messages:
            content = msg.get("content", "")
            for num_entry in msg.get("numbers", []):
                uuid = num_entry.get("uuid", "")
                number = (num_entry.get("number") or "").strip()

                if not number:
                    results.append({"uuid": uuid, "state": "wrong_number_format"})
                    continue

                try:
                    twilio_msg = client.messages.create(
                        body=content,
                        from_=self._from,
                        to=number,
                    )
                    _logger.info(
                        "dojo_sms_twilio: SID=%s to=%s status=%s",
                        twilio_msg.sid,
                        number,
                        twilio_msg.status,
                    )
                    if twilio_msg.status in ("queued", "sending", "sent", "delivered"):
                        results.append({"uuid": uuid, "state": "success", "credit": 1})
                    else:
                        results.append({"uuid": uuid, "state": "server_error"})
                except Exception as exc:  # noqa: BLE001
                    _logger.error(
                        "dojo_sms_twilio: error sending to %s: %s", number, exc
                    )
                    results.append({"uuid": uuid, "state": "server_error"})

        return results
