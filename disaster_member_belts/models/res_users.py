# -*- coding: utf-8 -*-
"""
res_users.py
------------
Extends res.users so that belt_rank, attendance_count, and ready_for_test
are directly accessible on the user object (proxied from the linked partner).

Also sets the post-login home action based on dojo group membership:
  - Dojo Admin     → Members overview
  - Dojo Instructor → Members overview (their students)
"""

from odoo import api, fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    belt_rank = fields.Selection(
        related='partner_id.belt_rank',
        string='Belt Rank',
        readonly=False,
        store=True,
    )

    attendance_count = fields.Integer(
        related='partner_id.attendance_count',
        string='Attendance Count',
        readonly=False,
        store=True,
    )

    ready_for_test = fields.Boolean(
        related='partner_id.ready_for_test',
        string='Ready for Test',
        readonly=True,
        store=True,
    )

    next_belt_rank = fields.Char(
        related='partner_id.next_belt_rank',
        string='Next Belt Rank',
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Home-action helpers
    # ------------------------------------------------------------------

    def _get_dojo_home_action(self):
        """
        Return the ir.actions.actions record to use as the post-login
        home screen for this user, based on their dojo group membership.

        - Dojo Admin / System  → Members overview
        - Dojo Instructor      → Members overview
        - Anything else        → None (leave Odoo default)
        """
        self.ensure_one()
        is_dojo_user = (
            self.has_group('disaster_member_belts.group_dojo_admin')
            or self.has_group('disaster_member_belts.group_dojo_instructor')
            or self.has_group('base.group_system')
        )

        if not is_dojo_user:
            return None

        # All dojo backend users land on the Members overview
        action = self.env.ref(
            'disaster_member_belts.action_member_list', raise_if_not_found=False
        )
        return action or None

    def _apply_dojo_home_action(self):
        """Set action_id to the dojo home action if not already customised."""
        for user in self:
            if user.share:          # portal / public users – skip
                continue
            action = user._get_dojo_home_action()
            if action and user.action_id != action:
                user.sudo().write({'action_id': action.id})

    # ------------------------------------------------------------------
    # ORM overrides — auto-apply when user is created or groups change
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._apply_dojo_home_action()
        return users

    def write(self, vals):
        result = super().write(vals)
        # Re-evaluate whenever group membership changes
        if 'groups_id' in vals or 'action_id' not in vals:
            self._apply_dojo_home_action()
        return result

