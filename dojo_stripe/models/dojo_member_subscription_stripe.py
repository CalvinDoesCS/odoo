"""
dojo_member_subscription_stripe.py
────────────────────────────────────
Extends dojo.member.subscription to charge via Stripe immediately after
posting the Odoo invoice, when the household has a saved native payment.token.

Architecture (native payment_stripe):
  - payment.token  (provider_ref = cus_xxx, stripe_payment_method = pm_xxx)
    linked to the primary guardian's partner_id.
  - action_charge_invoice() on dojo.household creates a payment.transaction
    with operation='offline' and calls _send_payment_request().
  - Odoo reconciles the invoice via Stripe webhook or status-check cron.

Fallback: if no payment.token is found for the household guardian, the base
action_generate_invoice() result is returned unchanged (e-mail invoice path).

Dunning (_handle_billing_failure) is called on immediate errors (tx.state
becomes 'error' synchronously). Async failures are handled via webhooks.
"""
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DojoMemberSubscriptionStripe(models.Model):
    _inherit = "dojo.member.subscription"

    def action_generate_invoice(self):
        """Generate invoice then immediately charge via saved payment.token.

        If the household's primary guardian has an active Stripe payment.token,
        household.action_charge_invoice(invoice) is called right after the
        Odoo invoice is posted.

        On tx.state == 'error'  → _handle_billing_failure() (triggers dunning).
        On tx.state == 'done'   → _reset_billing_failures() (immediate success).
        On tx.state == 'pending' → async; Stripe webhook / cron will reconcile.

        Falls back to email-invoice path when no token is configured.
        """
        invoice = super().action_generate_invoice()

        household = self.member_id.household_id
        if not household:
            return invoice

        # Use the computed payment_token_count field from dojo_household_billing
        # to determine whether a card is on file.  Attribute check required in
        # case dojo_stripe is not installed (defensive programming).
        if not getattr(household, 'payment_token_count', 0):
            # No saved card — invoice-by-email path already handled by super()
            return invoice

        try:
            tx = household.action_charge_invoice(invoice)
        except UserError as exc:
            # e.g. "No saved Stripe payment method found" or "No active Stripe provider"
            _logger.warning(
                'Dojo Stripe: could not charge invoice %s for subscription %s: %s',
                invoice.name, self.id, exc,
            )
            self._handle_billing_failure(exc)
            return invoice
        except Exception as exc:
            _logger.error(
                'Dojo Stripe: unexpected error charging invoice %s for subscription %s: %s',
                invoice.name, self.id, exc, exc_info=True,
            )
            self._handle_billing_failure(exc)
            return invoice

        # tx.state is set synchronously by _send_payment_request()
        state = tx.state if tx else ''
        if state == 'done':
            self._reset_billing_failures()
            _logger.info(
                'Dojo Stripe: PaymentIntent succeeded immediately for subscription %s.',
                self.id,
            )
        elif state == 'error':
            error_msg = getattr(tx, 'state_message', None) or 'Stripe payment failed'
            exc = UserError(_(error_msg))
            _logger.warning(
                'Dojo Stripe: charge failed for subscription %s: %s',
                self.id, error_msg,
            )
            self._handle_billing_failure(exc)
        else:
            # 'pending', 'draft', etc. — async resolution via Stripe webhook
            _logger.info(
                'Dojo Stripe: transaction %s in state %r for subscription %s — '
                'awaiting Stripe webhook for reconciliation.',
                tx.id, state, self.id,
            )

        return invoice
