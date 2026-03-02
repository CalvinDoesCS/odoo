from odoo import api, fields, models, _


class DojoMember(models.Model):
    """Extends dojo.member with Odoo Sign waiver fields."""

    _inherit = "dojo.member"

    waiver_request_id = fields.Many2one(
        "sign.request",
        string="Waiver Request",
        ondelete="set null",
        copy=False,
        help="Sign request sent to this member for waiver collection.",
    )
    waiver_state = fields.Selection(
        related="waiver_request_id.state",
        string="Waiver Status",
        readonly=True,
        store=True,
    )
    has_signed_waiver = fields.Boolean(
        compute="_compute_has_signed_waiver",
        store=True,
        string="Waiver Signed",
    )

    @api.depends("waiver_request_id", "waiver_request_id.state")
    def _compute_has_signed_waiver(self):
        for member in self:
            member.has_signed_waiver = bool(
                member.waiver_request_id
                and member.waiver_request_id.state == "signed"
            )

    def action_grant_portal_if_waiver_signed(self):
        """Called by the daily cron.  For every member whose waiver has been signed
        but who does not yet have a portal login, grant portal access and update
        the onboarding record."""
        for member in self.filtered(
            lambda m: m.has_signed_waiver and not m.has_portal_login
        ):
            if member.partner_id.email:
                member.action_grant_portal_access()
                record = self.env["dojo.onboarding.record"].search(
                    [("member_id", "=", member.id)], limit=1, order="create_date desc"
                )
                if record and not record.step_portal_access:
                    record.step_portal_access = True
