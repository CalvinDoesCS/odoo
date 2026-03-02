import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

STAGE_TRIAL_BOOKED = "Trial Booked"


class DojoBookTrialWizard(models.TransientModel):
    """
    Staff-facing wizard to book a lead into a free-trial class session.

    Moves the lead to the 'Trial Booked' stage (which fires the existing
    base.automation confirmation email + SMS) and links the chosen session
    as `lead.trial_session_id`.
    """

    _name = "dojo.book.trial.wizard"
    _description = "Book Trial Class for CRM Lead"

    # ----------------------------------------------------------------
    # Fields
    # ----------------------------------------------------------------

    lead_id = fields.Many2one(
        "crm.lead",
        string="Lead",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    session_id = fields.Many2one(
        "dojo.class.session",
        string="Trial Session",
        required=True,
        domain="[('state', 'in', ['draft', 'open'])]",
        help="Select an upcoming open class session for the free trial.",
    )
    capacity_warning = fields.Boolean(
        string="Session is Full",
        compute="_compute_capacity_warning",
        store=False,
    )
    force_book = fields.Boolean(
        string="Override Capacity",
        default=False,
        help="Tick to book the lead into this session even though it is at capacity.",
    )

    # ----------------------------------------------------------------
    # Defaults
    # ----------------------------------------------------------------

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        lead_id = self.env.context.get("default_lead_id") or self.env.context.get("active_id")
        if lead_id:
            res["lead_id"] = lead_id
        return res

    # ----------------------------------------------------------------
    # Computed
    # ----------------------------------------------------------------

    @api.depends("session_id")
    def _compute_capacity_warning(self):
        for rec in self:
            if rec.session_id:
                session = rec.session_id
                capacity = session.capacity or 0
                seats_taken = session.seats_taken or 0
                rec.capacity_warning = capacity > 0 and seats_taken >= capacity
            else:
                rec.capacity_warning = False

    # ----------------------------------------------------------------
    # Confirm booking
    # ----------------------------------------------------------------

    def action_confirm(self):
        self.ensure_one()
        lead = self.lead_id
        session = self.session_id

        if not session:
            raise UserError(_("Please select a trial session before confirming."))

        if self.capacity_warning and not self.force_book:
            raise UserError(
                _(
                    "The selected session is at full capacity (%(taken)d/%(cap)d). "
                    "Tick 'Override Capacity' to book anyway, or choose a different session.",
                    taken=session.seats_taken,
                    cap=session.capacity,
                )
            )

        # Find the Trial Booked stage
        trial_booked_stage = self.env["crm.stage"].search(
            [("name", "=", STAGE_TRIAL_BOOKED)], limit=1
        )
        if not trial_booked_stage:
            raise UserError(
                _(
                    "CRM stage '%s' not found. Please ensure dojo_crm data is properly loaded.",
                    STAGE_TRIAL_BOOKED,
                )
            )

        # Write both fields; stage write triggers automation_trial_booked_email
        lead.write(
            {
                "trial_session_id": session.id,
                "stage_id": trial_booked_stage.id,
                "trial_reminder_sent": False,  # reset in case of rebooking
            }
        )

        lead.message_post(
            body=_(
                "Trial booked: %(session)s (%(start)s). Booked by %(user)s.",
                session=session.name,
                start=session.start_datetime,
                user=self.env.user.name,
            ),
            subtype_xmlid="mail.mt_note",
        )

        _logger.info(
            "dojo_crm: lead %d booked into trial session %d (%s) by user %d",
            lead.id,
            session.id,
            session.name,
            self.env.uid,
        )

        return {"type": "ir.actions.act_window_close"}
