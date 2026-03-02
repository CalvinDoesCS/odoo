from odoo import _, fields, models
from odoo.exceptions import UserError


class DojoOnboardingWizard(models.TransientModel):
    """Extends the onboarding wizard with waiver-sending logic when Sign is installed."""

    _inherit = "dojo.onboarding.wizard"

    # ── Extra step ────────────────────────────────────────────────────────────
    # Override the selection to add the waiver step.
    step = fields.Selection(
        selection_add=[("waiver", "6. Waiver")],
        ondelete={"waiver": "set default"},
    )

    send_waiver = fields.Boolean(
        "Send Waiver for Signing",
        default=True,
        help=(
            "When checked, an Odoo Sign waiver request will be emailed to the member "
            "using the template configured on the selected subscription plan.  "
            "Portal access will only be granted after the member has signed the waiver."
        ),
    )
    has_waiver_template = fields.Boolean(
        compute="_compute_has_waiver_template",
        help="True when the selected plan has a Sign waiver template configured.",
    )

    def _compute_has_waiver_template(self):
        for rec in self:
            rec.has_waiver_template = bool(
                rec.plan_id and rec.plan_id.sign_template_id
            )

    # ── Override navigation to inject/skip the waiver step ───────────────────
    _STEP_ORDER = [
        "member_info",
        "household",
        "guardian_setup",
        "enrollment",
        "subscription",
        "waiver",
        "portal_access",
    ]

    def action_next(self):
        self.ensure_one()
        # Perform base validations by calling the parent implementation but
        # intercept after to handle the waiver step skip.
        result = super().action_next()
        # If base logic landed us on 'portal_access' but there is no waiver
        # template, that's fine — waiver step would be skipped automatically
        # because the base _STEP_ORDER doesn't include 'waiver'.
        # When Sign IS installed we need to potentially stop at 'waiver'.
        # Re-examine: if current step is 'subscription' and a waiver template
        # exists, override the result to land on 'waiver' instead.
        # (Base already advanced; we need to re-check.)
        if self.step == "portal_access" and self.has_waiver_template:
            self.step = "waiver"
            return self._reopen_wizard()
        return result

    def action_back(self):
        self.ensure_one()
        if self.step == "portal_access" and self.has_waiver_template:
            self.step = "waiver"
            return self._reopen_wizard()
        if self.step == "waiver":
            self.step = "subscription"
            return self._reopen_wizard()
        return super().action_back()

    # ── Override action_confirm to send the waiver before granting portal ─────
    def action_confirm(self):
        # Let the base wizard run first (creates member, subscription, etc.)
        # by calling super() but we need the member reference.
        # We re-implement the portal + onboarding-record portion.
        self.ensure_one()

        # Temporarily disable portal creation in case we need to gate it.
        original_create_portal = self.create_portal_login
        waiver_needed = (
            self.plan_id
            and self.plan_id.sign_template_id
            and self.send_waiver
        )
        if waiver_needed:
            # Prevent base from creating the portal login; we'll do it here.
            self.create_portal_login = False

        try:
            result = super().action_confirm()
        finally:
            self.create_portal_login = original_create_portal

        if not waiver_needed:
            return result

        # Locate the member that was just created (base wizard opened its form).
        member_id = result.get("res_id")
        if not member_id:
            return result
        member = self.env["dojo.member"].browse(member_id)
        if not member.exists():
            return result

        if not member.email:
            raise UserError(
                _(
                    "An email address is required to send the waiver. "
                    "Please add an email in Step 1."
                )
            )

        template = self.plan_id.sign_template_id
        roles = template.sign_item_ids.mapped("responsible_id")
        if not roles:
            raise UserError(
                _(
                    'The waiver template "%s" has no signature items with assigned roles. '
                    "Please configure the template in the Sign module before enrolling members.",
                    template.name,
                )
            )

        request_items = [
            (0, 0, {"partner_id": member.partner_id.id, "role_id": role.id})
            for role in roles[:1]
        ]
        sign_request = self.env["sign.request"].create(
            {
                "template_id": template.id,
                "reference": _("Waiver \u2014 %s") % member.name,
                "request_item_ids": request_items,
            }
        )
        try:
            sign_request.action_sent()
        except Exception:
            pass  # falls back to draft; admin can send manually from Sign

        member.waiver_request_id = sign_request.id

        # Store document in Waivers Documents folder (if documents module available)
        try:
            folder = (
                self.env["documents.folder"]
                .sudo()
                .search([("name", "=", "Waivers")], limit=1)
            )
            if not folder:
                folder = (
                    self.env["documents.folder"]
                    .sudo()
                    .create({"name": "Waivers"})
                )
            self.env["documents.document"].sudo().create(
                {
                    "name": _("Waiver \u2014 %s") % member.name,
                    "folder_id": folder.id,
                    "res_model": "sign.request",
                    "res_id": sign_request.id,
                    "partner_id": member.partner_id.id,
                }
            )
        except Exception:
            pass  # documents module may not be installed

        # Update onboarding record: mark waiver sent, portal NOT yet granted.
        onb = self.env["dojo.onboarding.record"].search(
            [("member_id", "=", member.id)], limit=1, order="create_date desc"
        )
        if onb:
            onb.step_portal_access = False  # portal held until waiver signed

        return result
