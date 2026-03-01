from odoo import api, fields, models


class DojoMember(models.Model):
    _inherit = "dojo.member"

    rank_history_ids = fields.One2many(
        "dojo.member.rank", "member_id", string="Belt History"
    )
    current_rank_id = fields.Many2one(
        "dojo.belt.rank",
        compute="_compute_current_rank",
        store=True,
        string="Current Belt",
    )

    @api.depends("rank_history_ids.date_awarded", "rank_history_ids.rank_id")
    def _compute_current_rank(self):
        for member in self:
            latest = member.rank_history_ids.sorted("date_awarded", reverse=True)[:1]
            member.current_rank_id = latest.rank_id if latest else False
