"""
dojo_household_billing.py
──────────────────────────
Extends dojo.household with Stripe Billing Customer tracking.

Architecture
────────────
  dojo.household  ─►  stripe.Customer        (Billing, cus_…)
                  ─►  stripe.PaymentMethod   (card-on-file, pm_…)

Stripe Issuing Cardholder / Card lives on hr.employee — see hr_employee_issuing.py.
Note: dojo_subscriptions.dojo_household used to hold Issuing fields here.
      Those have been removed; this module owns all Stripe fields now.
"""
from odoo import _, fields, models
from odoo.exceptions import UserError


class DojoHouseholdBilling(models.Model):
    _inherit = "dojo.household"

    # ── Stripe Billing ─────────────────────────────────────────────────────
    stripe_billing_customer_id = fields.Char(
        string="Stripe Customer ID",
        copy=False,
        help="Stripe Billing Customer ID (cus_…) for this household.",
    )
    stripe_payment_method_id = fields.Char(
        string="Stripe Payment Method",
        copy=False,
        help="Default Stripe PaymentMethod ID (pm_…) attached to this household's customer.",
    )
    payment_card_brand = fields.Char(
        string="Card Brand",
        help="e.g. Visa, Mastercard (from Stripe)",
    )
    payment_card_last4 = fields.Char(
        string="Last 4 Digits",
        size=4,
    )
    payment_card_expiry = fields.Char(
        string="Expiry (MM/YY)",
        size=5,
    )

    # ── Internal helpers ───────────────────────────────────────────────────
    def _get_stripe_api(self):
        """Return (stripe_module, secret_key). Never sets the global api_key."""
        try:
            import stripe as stripe_lib
        except ImportError:
            raise UserError(_(
                'The stripe Python package is not installed. '
                'Add "stripe" to requirements.txt and rebuild the container.'
            ))
        ICP = self.env['ir.config_parameter'].sudo()
        secret_key = ICP.get_param('stripe.secret_key', '')
        if not secret_key:
            raise UserError(_(
                'Stripe secret key is not configured. '
                'Go to Settings \u2192 Technical \u2192 System Parameters '
                'and set "stripe.secret_key".'
            ))
        return stripe_lib, secret_key

    # ── Stripe Billing Customer ────────────────────────────────────────────
    def action_create_stripe_customer(self):
        """Create a Stripe Billing Customer for this household if not already present.

        Returns the customer ID string (cus_…).
        """
        self.ensure_one()
        if self.stripe_billing_customer_id:
            return self.stripe_billing_customer_id

        guardian = self.primary_guardian_id
        if not guardian:
            raise UserError(_(
                'A primary guardian must be set before creating a Stripe customer.'
            ))

        stripe, api_key = self._get_stripe_api()
        customer = stripe.Customer.create(
            name=guardian.name,
            email=guardian.email or None,
            phone=guardian.mobile or guardian.phone or None,
            metadata={'odoo_household_id': str(self.id)},
            api_key=api_key,
        )
        self.sudo().write({'stripe_billing_customer_id': customer['id']})
        return customer['id']

    def action_save_payment_method(self, payment_method_id):
        """Attach a Stripe PaymentMethod to this household's Stripe Customer.

        Creates the Stripe Customer first if necessary.
        Sets payment_method_id as the customer's default for invoices.
        Updates payment_card_* display fields from the PaymentMethod data.

        Args:
            payment_method_id (str): Stripe pm_… ID from Elements / checkout.
        """
        self.ensure_one()
        stripe, api_key = self._get_stripe_api()
        customer_id = (
            self.stripe_billing_customer_id or self.action_create_stripe_customer()
        )

        # Attach PM to customer
        pm = stripe.PaymentMethod.attach(
            payment_method_id,
            customer=customer_id,
            api_key=api_key,
        )
        # Set as default payment method for future invoices
        stripe.Customer.modify(
            customer_id,
            invoice_settings={'default_payment_method': payment_method_id},
            api_key=api_key,
        )

        card = pm.get('card', {}) if isinstance(pm, dict) else getattr(pm, 'card', {})
        if hasattr(card, 'to_dict'):
            card = card.to_dict()

        self.sudo().write({
            'stripe_payment_method_id': payment_method_id,
            'payment_card_brand': (card.get('brand') or '').capitalize(),
            'payment_card_last4': card.get('last4') or '',
            'payment_card_expiry': '{:02d}/{}'.format(
                card.get('exp_month', 0),
                str(card.get('exp_year', ''))[-2:],
            ),
        })
        return True

    def action_charge_invoice(self, invoice):
        """Charge an Odoo invoice against the household's saved Stripe PaymentMethod.

        Creates a PaymentIntent in off_session mode and confirms it immediately.
        Returns the stripe.PaymentIntent object (or dict).
        Raises UserError if no Stripe customer / PM is configured.

        Args:
            invoice (account.move): Posted Odoo invoice to charge.
        """
        self.ensure_one()
        if not self.stripe_billing_customer_id:
            raise UserError(_('No Stripe customer configured for this household.'))
        if not self.stripe_payment_method_id:
            raise UserError(_('No Stripe payment method saved for this household.'))

        stripe, api_key = self._get_stripe_api()
        currency = (invoice.currency_id.name or 'usd').lower()
        # Stripe uses minor units (cents for USD, etc.)
        amount_cents = int(round(invoice.amount_total * 100))

        pi = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency=currency,
            customer=self.stripe_billing_customer_id,
            payment_method=self.stripe_payment_method_id,
            confirm=True,
            off_session=True,
            description='Dojo Subscription: {}'.format(
                invoice.ref or invoice.name or str(invoice.id)
            ),
            metadata={
                'odoo_invoice_id': str(invoice.id),
                'odoo_subscription_id': str(
                    invoice.subscription_id.id if invoice.subscription_id else ''
                ),
            },
            api_key=api_key,
        )
        return pi
