from odoo import api, fields, models


class DojoMember(models.Model):
    _inherit = "dojo.member"

    crm_lead_ids = fields.One2many(
        "crm.lead",
        "dojo_member_id",
        string="CRM Leads",
        help="Leads that were converted into this member.",
    )
    lead_count = fields.Integer(
        string="Leads",
        compute="_compute_lead_count",
    )

    @api.depends("crm_lead_ids")
    def _compute_lead_count(self):
        for rec in self:
            rec.lead_count = len(rec.crm_lead_ids)

    def action_view_leads(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Leads",
            "res_model": "crm.lead",
            "view_mode": "list,form",
            "domain": [("dojo_member_id", "=", self.id)],
        }

    def unlink(self):
        """Delete CRM leads that were linked to this member before removing
        the member record itself."""
        leads = self.sudo().mapped("crm_lead_ids")
        if leads:
            leads.unlink()
        return super().unlink()
