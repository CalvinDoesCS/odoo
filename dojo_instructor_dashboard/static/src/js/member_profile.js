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

    goBack() {
        window.history.back();
    }

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

    attendanceClass(state) {
        return (
            {
                present: "o_di_badge_success",
                absent:  "o_di_badge_danger",
                excused: "o_ad_badge_warning",
                pending: "o_di_badge_secondary",
            }[state] || "o_di_badge_secondary"
        );
    }

    attendanceLabel(state) {
        return (
            { present: "Present", absent: "Absent", excused: "Excused", pending: "Pending" }[state]
            || state
        );
    }

    enrollmentLabel(status) {
        return (
            { registered: "Registered", waitlist: "Waitlist", cancelled: "Cancelled" }[status]
            || status
        );
    }

    get imageUrl() {
        if (!this.state.member) return "";
        return `/web/image/dojo.member/${this.state.member.id}/image_1920`;
    }
}

registry.category("actions").add("dojo_member_profile", MemberProfile);
