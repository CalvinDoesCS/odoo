/** @odoo-module **/
/**
 * onboarding_stripe_payment.js  (dojo_onboarding_stripe)
 * ───────────────────────────────────────────────────────
 * OWL widget that embeds a Stripe PaymentElement inside the onboarding wizard's
 * "payment" step.
 *
 * Flow:
 *   1. On mount → POST /dojo/onboarding/stripe/setup  → get client_secret + pk
 *   2. Load Stripe.js dynamically → stripe.elements({clientSecret}) → mount PaymentElement
 *   3. Staff clicks "Save Card"
 *      a. elements.submit()  (validates input)
 *      b. stripe.confirmSetup({redirect:'if_required'})
 *      c. POST /dojo/onboarding/stripe/confirm  → store PM on wizard record
 *   4. Widget shows success card; wizard Next button becomes available.
 *
 * The "Skip" checkbox sets skip_payment=True on the record so action_next
 * won't raise a UserError.
 */

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, useRef, useEffect } from "@odoo/owl";
import { rpc } from "@web/core/network/rpc";

class OnboardingStripePayment extends Component {
    static template = "dojo_onboarding_stripe.OnboardingStripePayment";

    static props = {
        record: { type: Object },
        readonly: { type: Boolean, optional: true },
    };

    setup() {
        this.state = useState({
            // idle | loading | ready | processing | done | error
            status: "idle",
            errorMessage: "",
            cardDisplay: "",
        });
        this.mountRef = useRef("stripe-mount");
        this.stripe = null;
        this.elements = null;
        this._pendingPaymentEl = null;  // stored until DOM node is rendered

        // Mount the Stripe PaymentElement only AFTER the ref div is in the DOM.
        // The div is rendered when status === 'ready', so useEffect runs after
        // the status change triggers a re-render and the node actually exists.
        useEffect(
            (status) => {
                if (status === "ready" && this._pendingPaymentEl && this.mountRef.el) {
                    this._pendingPaymentEl.mount(this.mountRef.el);
                    this._pendingPaymentEl = null;
                }
            },
            () => [this.state.status],
        );

        onMounted(() => {
            const data = this.props.record.data;
            if (data.payment_captured) {
                // Card was already saved (e.g. user went back and forward)
                this.state.status = "done";
                this.state.cardDisplay = data.stripe_card_display || "Card saved";
            } else if (!data.skip_payment) {
                this._initStripe();
            }
        });
    }

    // ── Stripe initialisation ─────────────────────────────────────────────

    async _initStripe() {
        this.state.status = "loading";
        const wizardId = this.props.record.resId;

        let clientSecret, publishableKey;
        try {
            const result = await rpc("/dojo/onboarding/stripe/setup", {
                wizard_id: wizardId,
            });
            if (result.error) {
                this.state.status = "error";
                this.state.errorMessage = result.error;
                return;
            }
            clientSecret = result.client_secret;
            publishableKey = result.publishable_key;
        } catch (e) {
            this.state.status = "error";
            this.state.errorMessage = e.message || String(e) || "Network error — could not reach the server.";
            return;
        }

        try {
            const stripeJs = await this._loadStripeJs(publishableKey);
            this.stripe = stripeJs;

            this.elements = stripeJs.elements({
                clientSecret,
                appearance: {
                    theme: "stripe",
                    variables: { colorPrimary: "#714b67" },
                },
            });

            const paymentEl = this.elements.create("payment", {
                layout: "tabs",
                // Disable Link autofill and wallet shortcuts.
                // Link would pre-fill a card from a previous browser session.
                wallets: { applePay: "never", googlePay: "never", link: "never" },
            });
            // Store for mounting — useEffect will call .mount() once the
            // t-ref div appears in the DOM after status flips to 'ready'.
            this._pendingPaymentEl = paymentEl;
            this.state.status = "ready";
            // (useEffect mounts it after this render cycle)
        } catch (e) {
            this.state.status = "error";
            this.state.errorMessage = e.message || "Failed to initialise payment form.";
        }
    }

    async _loadStripeJs(publishableKey) {
        if (window.Stripe) {
            return window.Stripe(publishableKey);
        }
        return new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = "https://js.stripe.com/v3/";
            script.async = true;
            script.onload = () => resolve(window.Stripe(publishableKey));
            script.onerror = () => reject(new Error("Failed to load Stripe.js"));
            document.head.appendChild(script);
        });
    }

    // ── Save card ────────────────────────────────────────────────────────

    async onSaveCard() {
        if (!this.stripe || !this.elements) return;
        this.state.status = "processing";
        this.state.errorMessage = "";

        // Step 1: validate the element inputs
        const { error: submitError } = await this.elements.submit();
        if (submitError) {
            this.state.status = "error";
            this.state.errorMessage = submitError.message;
            this.state.status = "ready"; // allow retry
            return;
        }

        // Step 2: confirm the SetupIntent
        const { error, setupIntent } = await this.stripe.confirmSetup({
            elements: this.elements,
            redirect: "if_required",  // no redirect for card PMs
        });

        if (error) {
            this.state.status = "error";
            this.state.errorMessage = error.message;
            this.state.status = "ready";
            return;
        }

        // setupIntent.payment_method may be a string (PM id) or an object
        const pmId =
            typeof setupIntent.payment_method === "string"
                ? setupIntent.payment_method
                : setupIntent.payment_method.id;

        // Step 3: tell the server to record this PM on the wizard
        const wizardId = this.props.record.resId;
        let result;
        try {
            result = await rpc("/dojo/onboarding/stripe/confirm", {
                wizard_id: wizardId,
                payment_method_id: pmId,
            });
        } catch (e) {
            this.state.status = "error";
            this.state.errorMessage = e.message || String(e) || "Network error saving card.";
            return;
        }

        if (result.error) {
            this.state.status = "error";
            this.state.errorMessage = result.error;
            return;
        }

        this.state.status = "done";
        this.state.cardDisplay = result.display || "Card saved";

        // Refresh the wizard record so payment_captured = True is reflected
        // and the Next button validation in action_next() passes.
        await this.props.record.load();
    }

    // ── Retry ─────────────────────────────────────────────────────────────

    async onRetry() {
        this.state.errorMessage = "";
        await this._initStripe();
    }

    // ── Skip toggle ──────────────────────────────────────────────────────

    async onSkipChange(evt) {
        await this.props.record.update({ skip_payment: evt.target.checked });
        if (evt.target.checked) {
            // If user skips, clear any in-progress Stripe UI
            this.state.status = "idle";
        } else if (this.state.status === "idle" && !this.props.record.data.payment_captured) {
            await this._initStripe();
        }
    }
}

registry.category("view_widgets").add("onboarding_stripe_payment", {
    component: OnboardingStripePayment,
});
