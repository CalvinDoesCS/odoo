"""
hr_employee_issuing.py
───────────────────────
Extends hr.employee with Stripe Issuing Cardholder + virtual card fields.

Architecture
────────────
  hr.employee  ─►  stripe.issuing.Cardholder (individual, ich_…)
               ─►  stripe.issuing.Card        (virtual, ic_…)

Note: every dojo.instructor.profile already creates/is linked to an hr.employee
via dojo_base → no extra wiring is needed. Instructors get Issuing cards here.
"""
from odoo import _, fields, models
from odoo.exceptions import UserError


class HrEmployeeIssuing(models.Model):
    _inherit = "hr.employee"

    # ── Stripe Issuing fields ──────────────────────────────────────────────
    stripe_cardholder_id = fields.Char(
        string="Stripe Cardholder ID",
        copy=False,
        help="Stripe Issuing Cardholder ID (ich_…) for this employee.",
    )
    stripe_card_id = fields.Char(
        string="Stripe Card ID",
        copy=False,
        help="Stripe Issuing virtual Card ID (ic_…) for this employee.",
    )
    issuing_card_brand = fields.Char(string="Card Brand")
    issuing_card_last4 = fields.Char(string="Last 4 Digits", size=4)
    issuing_card_expiry = fields.Char(string="Expiry (MM/YY)", size=5)
    issuing_card_status = fields.Char(
        string="Card Status",
        copy=False,
        help="active, inactive, canceled — as reported by Stripe",
    )

    # ── Internal helper ────────────────────────────────────────────────────
    @staticmethod
    def _read_docker_secret(name):
        """Read a Docker secrets file at /run/secrets/<name>.

        Returns the stripped file content, or an empty string if the file
        does not exist (e.g. outside Docker or secret not mounted).
        """
        import os
        try:
            with open(f'/run/secrets/{name}', 'r') as fh:
                return fh.read().strip()
        except (IOError, OSError):
            return ''

    def _get_stripe_api(self):
        """Return (stripe_module, secret_key). Never sets the global api_key.

        Key resolution order:
          1. Docker secret file  /run/secrets/stripe_secret_key
          2. Odoo system parameter  stripe.secret_key  (fallback / dev)
        """
        try:
            import stripe as stripe_lib
        except ImportError:
            raise UserError(_(
                'The stripe Python package is not installed. '
                'Add "stripe" to requirements.txt and rebuild the container.'
            ))
        secret_key = self._read_docker_secret('stripe_secret_key')
        if not secret_key:
            ICP = self.env['ir.config_parameter'].sudo()
            secret_key = ICP.get_param('stripe.secret_key', '')
        if not secret_key:
            raise UserError(_(
                'Stripe secret key is not configured. '
                'Add it to the stripe_secret_key Docker secret file, or go to '
                'Settings → Technical → System Parameters and set '
                '"stripe.secret_key".'
            ))
        return stripe_lib, secret_key

    # ── Stripe Issuing actions ─────────────────────────────────────────────
    def action_create_stripe_cardholder(self):
        """Create a Stripe Issuing Cardholder for this employee."""
        self.ensure_one()
        if self.stripe_cardholder_id:
            return  # Already created

        stripe, api_key = self._get_stripe_api()
        company = self.env.company
        cardholder = stripe.issuing.Cardholder.create(
            name=self.name,
            email=self.work_email or None,
            phone_number=self.mobile_phone or self.work_phone or None,
            type='individual',
            billing={
                'address': {
                    'line1': company.street or '123 Main St',
                    'city': company.city or 'City',
                    'state': company.state_id.code if company.state_id else 'CA',
                    'postal_code': company.zip or '00000',
                    'country': company.country_id.code if company.country_id else 'US',
                }
            },
            api_key=api_key,
        )
        self.sudo().write({'stripe_cardholder_id': cardholder['id']})

    def action_create_stripe_card(self):
        """Create a Stripe Issuing virtual Card for this employee."""
        self.ensure_one()
        if not self.stripe_cardholder_id:
            self.action_create_stripe_cardholder()
        if self.stripe_card_id:
            return  # Already created

        stripe, api_key = self._get_stripe_api()
        currency = (self.env.company.currency_id.name or 'usd').lower()
        card = stripe.issuing.Card.create(
            cardholder=self.stripe_cardholder_id,
            currency=currency,
            type='virtual',
            api_key=api_key,
        )
        self.sudo().write({
            'stripe_card_id': card['id'],
            'issuing_card_brand': (card.get('brand') or '').capitalize(),
            'issuing_card_last4': card.get('last4') or '',
            'issuing_card_expiry': '{:02d}/{}'.format(
                card.get('exp_month', 0),
                str(card.get('exp_year', ''))[-2:],
            ),
            'issuing_card_status': card.get('status') or 'active',
        })

    def action_get_wallet_ephemeral_key(self):
        """Return a Stripe Ephemeral Key dict for Google Wallet push provisioning."""
        self.ensure_one()
        if not self.stripe_card_id:
            raise UserError(_('No Stripe card exists for this employee yet.'))
        stripe, api_key = self._get_stripe_api()
        eph = stripe.EphemeralKey.create(
            {'issuing_card': self.stripe_card_id},
            stripe_version='2024-06-20',
            api_key=api_key,
        )
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'ephemeral_key_secret': eph['secret'],
            'stripe_card_id': self.stripe_card_id,
            'publishable_key': ICP.get_param('stripe.publishable_key', ''),
        }

    def action_issue_card_button(self):
        """Button: create Issuing cardholder + virtual card if not already done."""
        self.ensure_one()
        self.action_create_stripe_cardholder()
        self.action_create_stripe_card()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Stripe Card Issued'),
                'message': _(
                    'Virtual card \u2022\u2022\u2022\u2022 %s has been created and is active.'
                ) % (self.issuing_card_last4 or ''),
                'type': 'success',
                'sticky': False,
            },
        }
