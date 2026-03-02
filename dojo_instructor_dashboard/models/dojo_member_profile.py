from odoo import api, models
from odoo.fields import Date


class DojoMemberProfile(models.Model):
    """Adds a single RPC method that returns all data needed by the
    Member Profile OWL component."""

    _inherit = "dojo.member"

    @api.model
    def get_member_profile_data(self, member_id):
        """Return a rich dict of member data for the OWL profile component.

        Called via ``orm.call("dojo.member", "get_member_profile_data", [id])``.
        Uses sudo() so instructors can always see a student's full profile
        regardless of record-level rules on related models.
        """
        member = self.sudo().browse(member_id)
        if not member.exists():
            return {}

        # ── Subscription plan ─────────────────────────────────────────────
        plan_name = ""
        sub = member.active_subscription_id
        if sub and sub.plan_id:
            plan_name = sub.plan_id.name or ""

        # ── Basics ────────────────────────────────────────────────────────
        data = {
            "id": member.id,
            "name": member.name or "",
            "email": member.email or "",
            "phone": member.phone or "",
            "date_of_birth": str(member.date_of_birth) if member.date_of_birth else "",
            "role": member.role or "",
            "membership_state": member.membership_state or "",
            "emergency_note": member.emergency_note or "",
            "plan_name": plan_name,
        }

        # ── Household ─────────────────────────────────────────────────────
        hh = member.household_id
        if hh:
            data["household"] = {
                "id": hh.id,
                "name": hh.name or "",
                "primary_guardian": (
                    hh.primary_guardian_id.name if hh.primary_guardian_id else ""
                ),
                "members": [
                    {"id": m.id, "name": m.name or "", "role": m.role or ""}
                    for m in hh.member_ids
                ],
            }
        else:
            data["household"] = None

        # ── Course template rosters ────────────────────────────────────────
        level_labels = dict(
            self.env["dojo.class.template"]._fields["level"].selection
        )
        templates = self.sudo().env["dojo.class.template"].search(
            [("course_member_ids", "in", [member_id])]
        )
        data["course_templates"] = [
            {
                "id": t.id,
                "name": t.name or "",
                "level": level_labels.get(t.level, t.level or ""),
                "instructors": (
                    ", ".join(t.instructor_profile_ids.mapped("name")) or "—"
                ),
            }
            for t in templates
        ]

        # ── Upcoming session enrollments ───────────────────────────────────
        # Use sudo() so instructors can see all sessions/enrollments,
        # not just ones in their own sessions.
        today = Date.today()
        env = self.sudo().env
        future_sessions = env["dojo.class.session"].search(
            [("start_datetime", ">=", str(today) + " 00:00:00")],
            order="start_datetime asc",
            limit=200,
        )
        enrollments = env["dojo.class.enrollment"].search(
            [
                ("member_id", "=", member_id),
                ("session_id", "in", future_sessions.ids),
                ("status", "!=", "cancelled"),
            ],
            limit=50,
        )
        # Sort by session start so the list is chronological
        enrollments = enrollments.sorted(
            key=lambda e: e.session_id.start_datetime or ""
        )
        data["upcoming_enrollments"] = [
            {
                "id": e.id,
                "template_name": (
                    e.session_id.template_id.name
                    if e.session_id.template_id
                    else "—"
                ),
                "start_datetime": (
                    str(e.session_id.start_datetime)
                    if e.session_id.start_datetime
                    else ""
                ),
                "instructor": (
                    e.session_id.instructor_profile_id.name
                    if e.session_id.instructor_profile_id
                    else "—"
                ),
                "status": e.status or "",
                "attendance_state": e.attendance_state or "",
            }
            for e in enrollments
        ]

        return data
