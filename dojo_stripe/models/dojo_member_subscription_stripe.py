"""
dojo_member_subscription_stripe.py
────────────────────────────────────
Extends dojo.member.subscription to charge via Stripe Billing immediately
after posting the Odoo invoice, when the household has a saved payment method.

Fallback: if no Stripe customer + PM is configured on the household, the base
action_generate_invoice() result is returned unchanged (email-invoice path).

The dunning escalation (_handle_billing_failure) defined in
dojo_subscriptions is triggered on Stripe charge failure exactly as it
would be on any other billing error.
"""
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DojoMemberSubscriptionStripe(models.Model):
    _inherit = "dojo.member.subscription"

    def action_generate_invoice(self):
        """Generate invoice, then charge via Stripe if Billing is configured.

        When the household has both a stripe_billing_customer_id and a
        stripe_payment_method_id, a Stripe PaymentIntent is created after
        the Odoo invoice is posted.

        On success  → _reset_billing_failures() is called.
        On failure  → _handle_billing_failure() is called (triggers dunning).

        Falls back silently to the email-invoice path when Stripe is not
        configured for the household.
        """
        invoice = super().action_generate_invoice()

        household = self.member_id.household_id
        if not household:
            return invoice

        # Check whether Stripe Billing is configured for this household
        if (not hasattr(household, 'stripe_billing_customer_id')
                or not household.stripe_billing_customer_id
                or not household.stripe_payment_method_id):
            # No Stripe configured — invoice-by-email path already handled by super()
            return invoice

        try:
            pi = household.action_charge_invoice(invoice)
            # stripe SDK returns either a dict or a StripeObject; normalise
            status = pi.get('status') if isinstance(pi, dict) else getattr(pi, 'status', '')
            pi_id = pi.get('id') if isinstance(pi, dict) else getattr(pi, 'id', '?')

            if status == 'succeeded':
                self._reset_billing_failures()
                _logger.info(
                    'Dojo Stripe: PaymentIntent %s succeeded for subscription %s.',
                    pi_id, self.id,
                )
            elif status in ('requires_action', 'requires_payment_method'):
                # Authentication or new-card required — treat as soft billing failure
                exc = UserError(_(
                    'Stripe payment requires further action: %s (pi=%s)'
                ) % (status, pi_id))
                self._handle_billing_failure(exc)
        except Exception as exc:
            _logger.error(
                'Dojo Stripe: charge failed for subscription %s: %s',
                self.id, exc, exc_info=True,
            )
            self._handle_billing_failure(exc)

        return invoice
