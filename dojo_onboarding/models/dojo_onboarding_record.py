from odoo import api, fields, models


class DojoOnboardingRecord(models.Model):
    _name = 'dojo.onboarding.record'
    _description = 'Member Onboarding Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    _rec_name = 'member_id'

    member_id = fields.Many2one(
        'dojo.member',
        string='Member',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one('res.company', string='Company', index=True)

    state = fields.Selection(
        selection=[
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
        ],
        default='in_progress',
        required=True,
        tracking=True,
    )

    # Step completion flags
    step_member_info = fields.Boolean('Member Info', default=False)
    step_household = fields.Boolean('Household', default=False)
    step_enrollment = fields.Boolean('Class Enrollment', default=False)
    step_subscription = fields.Boolean('Subscription', default=False)
    step_portal_access = fields.Boolean('Portal Access', default=False)

    progress_pct = fields.Integer(
        string='Progress (%)',
        compute='_compute_progress',
        store=True,
    )

    @api.depends(
        'step_member_info', 'step_household', 'step_enrollment',
        'step_subscription', 'step_portal_access',
    )
    def _compute_progress(self):
        steps = [
            'step_member_info', 'step_household', 'step_enrollment',
            'step_subscription', 'step_portal_access',
        ]
        for rec in self:
            completed = sum(1 for s in steps if getattr(rec, s))
            rec.progress_pct = int(completed / len(steps) * 100)
