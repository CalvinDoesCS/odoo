from odoo import api, models


class DojoKioskService(models.AbstractModel):
    _inherit = "dojo.kiosk.service"

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_marketing_cards_data(self, publish_kiosk=True):
        """Return serialisable list of active marketing cards for the kiosk."""
        base_url = self.env["ir.config_parameter"].sudo().get_param(
            "web.base.url", default=""
        )
        domain = [("active", "=", True)]
        if publish_kiosk:
            domain.append(("publish_kiosk", "=", True))
        cards = self.env["dojo.marketing.card"].sudo().search(domain)
        result = []
        for card in cards:
            qr_url = None
            if card.card_type == "badge":
                # Badge QR is per-member; the kiosk slide shows instructions instead
                qr_url = None
            elif card.target_url:
                qr_url = f"{base_url}/dojo/marketing/qr/{card.id}"
            result.append({
                "id": card.id,
                "card_type": card.card_type,
                "name": card.name,
                "subtitle": card.subtitle or "",
                "body": card.body or "",
                "qr_url": qr_url,
                "sequence": card.sequence,
            })
        return result

    # ── Overrides ─────────────────────────────────────────────────────────────

    def get_config_bootstrap(self, token):
        result = super().get_config_bootstrap(token)
        result["marketing_cards"] = self._get_marketing_cards_data(publish_kiosk=True)
        return result
