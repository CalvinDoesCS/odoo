/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class MemberProfile extends Component {
    static template = "dojo_instructor_dashboard.MemberProfile";
    static props = ["action", "actionType?"];

    setup() {
        this.orm    = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.rootRef = useRef("root");

        this.state = useState({
            loading: true,
            member: null,
        });

        onWillStart(() => this._loadData());

        onMounted(() => {
            const el = this.rootRef.el;
            if (!el) return;
            let node = el.parentElement;
            while (node && node !== document.body) {
                const computed = getComputedStyle(node);
                if (computed.overflow === "hidden" || computed.overflowY === "hidden") {
                    node.style.overflowY = "auto";
                }
                node = node.parentElement;
            }
        });
    }

    async _loadData() {
        const memberId = this.props.action?.context?.active_id;
        if (!memberId) {
            this.state.loading = false;
            return;
        }
        const member = await this.orm.call(
            "dojo.member", "get_member_profile_data", [memberId]
        );
        this.state.member = (member && member.id) ? member : null;
        this.state.loading = false;
    }

    get memberId() {
        return this.props.action?.context?.active_id;
    }

    goBack() {
        window.history.back();
    }

    // ── Quick Actions ────────────────────────────────────────────────

    editMember() {
        if (!this.memberId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "dojo.member",
            res_id: this.memberId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    async addCredits() {
        if (!this.memberId) return;
        // Try to open the credit grant wizard; fall back to subscription form
        try {
            await this.action.doAction("dojo_credits.action_dojo_credit_grant_wizard", {
                additionalContext: { active_id: this.memberId, active_model: "dojo.member" },
            });
        } catch {
            // If the wizard action doesn't exist, navigate to subscription
            this.viewSubscription();
        }
    }

    viewSubscription() {
        if (!this.memberId) return;
        const subId = this.state.member?.subscription?.id;
        if (subId) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "dojo.member.subscription",
                res_id: subId,
                views: [[false, "form"]],
                target: "current",
            });
        } else {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "dojo.member.subscription",
                views: [[false, "list"], [false, "form"]],
                domain: [["member_id", "=", this.memberId]],
                target: "current",
            });
        }
    }

    logAttendance() {
        if (!this.memberId) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "dojo.attendance.log",
            views: [[false, "form"]],
            target: "new",
            context: { default_member_id: this.memberId },
        });
    }

    inviteBeltTest() {
        if (!this.memberId) return;
        // Toggle test_invite_pending or open belt test registration form
        try {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "dojo.member",
                res_id: this.memberId,
                views: [[false, "form"]],
                target: "current",
            });
        } catch {
            this.notification.add("Belt test action not available.", { type: "warning" });
        }
    }

    sendMessage() {
        if (!this.memberId) return;
        try {
            this.action.doAction("dojo_communications.action_dojo_send_message_wizard", {
                additionalContext: {
                    active_id: this.memberId,
                    active_model: "dojo.member",
                    active_ids: [this.memberId],
                },
            });
        } catch {
            this.notification.add("Send message action not available.", { type: "warning" });
        }
    }

    // ── Date / Time helpers ──────────────────────────────────────────

    /** "2025-03-15 09:00:00" (UTC) → "Mar 15 · 9:00 AM" local */
    fmtDt(dtStr) {
        if (!dtStr) return "—";
        const d = new Date(dtStr.replace(" ", "T") + "Z");
        return d.toLocaleString(undefined, {
            month: "short", day: "numeric",
            hour: "numeric", minute: "2-digit",
        });
    }

    /** "YYYY-MM-DD" → "March 15, 2025" */
    fmtDate(dateStr) {
        if (!dateStr) return "—";
        const [y, m, d] = dateStr.split("-").map(Number);
        return new Date(y, m - 1, d).toLocaleDateString(undefined, {
            month: "long", day: "numeric", year: "numeric",
        });
    }

    // ── Label helpers ────────────────────────────────────────────────

    roleLabel(role) {
        return (
            { student: "Student", parent: "Parent", both: "Parent & Student" }[role]
            || role
        );
    }

    stateLabel(state) {
        return (
            { lead: "Lead", trial: "Trial", active: "Active", paused: "Paused", cancelled: "Cancelled" }[state]
            || state
        );
    }

    stateClass(state) {
        return (
            {
                lead:      "o_mp_state_lead",
                trial:     "o_mp_state_trial",
                active:    "o_mp_state_active",
                paused:    "o_mp_state_paused",
                cancelled: "o_mp_state_cancelled",
            }[state] || "o_mp_state_lead"
        );
    }

    subStateLabel(state) {
        return (
            {
                draft:     "Draft",
                active:    "Active",
                paused:    "Paused",
                cancelled: "Cancelled",
                expired:   "Expired",
            }[state] || state
        );
    }

    subStateClass(state) {
        return (
            {
                draft:     "o_di_badge_secondary",
                active:    "o_di_badge_success",
                paused:    "o_ad_badge_warning",
                cancelled: "o_di_badge_danger",
                expired:   "o_di_badge_danger",
            }[state] || "o_di_badge_secondary"
        );
    }

    attendanceClass(state) {
        return (
            {
                present: "o_di_badge_success",
                late:    "o_ad_badge_warning",
                absent:  "o_di_badge_danger",
                excused: "o_ad_badge_info",
                pending: "o_di_badge_secondary",
            }[state] || "o_di_badge_secondary"
        );
    }

    attendanceLabel(state) {
        return (
            { present: "Present", late: "Late", absent: "Absent", excused: "Excused", pending: "Pending" }[state]
            || state
        );
    }

    enrollmentLabel(status) {
        return (
            { registered: "Registered", waitlist: "Waitlist", cancelled: "Cancelled" }[status]
            || status
        );
    }

    creditTypeLabel(t) {
        return (
            { grant: "Grant", hold: "Hold", expiry: "Expiry", adjustment: "Adjustment" }[t]
            || t
        );
    }

    creditTypeClass(t) {
        return (
            {
                grant:      "o_di_badge_success",
                hold:       "o_ad_badge_warning",
                expiry:     "o_di_badge_danger",
                adjustment: "o_ad_badge_info",
            }[t] || "o_di_badge_secondary"
        );
    }

    creditStatusLabel(s) {
        return (
            { pending: "Pending", confirmed: "Confirmed", cancelled: "Cancelled" }[s]
            || s
        );
    }

    creditStatusClass(s) {
        return (
            {
                pending:   "o_ad_badge_warning",
                confirmed: "o_di_badge_success",
                cancelled: "o_di_badge_secondary",
            }[s] || "o_di_badge_secondary"
        );
    }

    // ── Belt helpers ─────────────────────────────────────────────────

    /**
     * Convert a belt color (hex or named) to a semi-transparent background
     * suitable for the hero badge.
     */
    rankBgColor(color) {
        if (!color) return "rgba(255,255,255,0.08)";
        // Simple opacity trick: wrap hex or named color with a fallback
        return "rgba(0,0,0,0.35)";
    }

    rankPct(done, threshold) {
        if (!threshold || threshold <= 0) return 0;
        return Math.min(100, Math.round((done / threshold) * 100));
    }

    rankProgressClass(done, threshold) {
        const pct = this.rankPct(done, threshold);
        if (pct >= 75) return "o_ad_bar_fill o_ad_rate_good";
        if (pct >= 40) return "o_ad_bar_fill o_ad_rate_ok";
        return "o_ad_bar_fill o_ad_rate_bad";
    }

    get imageUrl() {
        if (!this.state.member) return "";
        return `/web/image/dojo.member/${this.state.member.id}/image_1920`;
    }
}

registry.category("actions").add("dojo_member_profile", MemberProfile);

