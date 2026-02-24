/** @odoo-module **/
/**
 * dojo_widgets.js – Standalone OWL widgets for the Dojo Dashboard.
 *   • DojoTodoWidget   – native Odoo To-Do  (project.task, project_id=False)
 *   • DojoCalendarWidget – upcoming calendar events (calendar.event)
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { user } from "@web/core/user";

// ─────────────────────────────────────────────────────────────────────────────
// To-Do Widget
// ─────────────────────────────────────────────────────────────────────────────
export class DojoTodoWidget extends Component {
    static template = "dojo_dashboard.TodoWidget";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            todos: [],
            newTodo: "",
            loading: true,
        });

        onWillStart(() => this._load());
    }

    async _load() {
        try {
            this.state.todos = await this.orm.searchRead(
                "project.task",
                [
                    ["user_ids", "in", [user.userId]],
                    ["project_id", "=", false],
                    ["parent_id", "=", false],
                    ["is_closed", "=", false],
                ],
                ["id", "name", "state", "date_deadline", "priority"],
                { order: "priority desc, date_deadline asc, id desc", limit: 30 }
            );
        } catch (e) {
            console.warn("[DojoTodoWidget] load failed:", e);
            this.state.todos = [];
        }
        this.state.loading = false;
    }

    async addTodo() {
        const name = (this.state.newTodo || "").trim();
        if (!name) return;
        await this.orm.create("project.task", [{ name, project_id: false }]);
        this.state.newTodo = "";
        await this._load();
    }

    onKeydown(ev) {
        if (ev.key === "Enter") this.addTodo();
    }

    async markDone(id) {
        await this.orm.write("project.task", [id], { state: "1_done" });
        this.state.todos = this.state.todos.filter(t => t.id !== id);
    }

    openTodos() {
        this.action.doAction("project_todo.project_task_action_todo");
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Calendar Widget
// ─────────────────────────────────────────────────────────────────────────────
export class DojoCalendarWidget extends Component {
    static template = "dojo_dashboard.CalendarWidget";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        this.state = useState({
            events: [],
            loading: true,
        });

        onWillStart(() => this._load());
    }

    async _load() {
        const today = _today();
        const until = _daysFromNow(14);
        const combined = [];

        // ── Odoo calendar events ─────────────────────────────────────
        try {
            const calEvents = await this.orm.searchRead(
                "calendar.event",
                [
                    ["start", ">=", today + " 00:00:00"],
                    ["start", "<=", until + " 23:59:59"],
                    ["partner_ids", "in", [user.partnerId]],
                ],
                ["id", "name", "start", "stop", "location", "allday"],
                { order: "start asc", limit: 10 }
            );
            calEvents.forEach(e => combined.push({
                id: "cal_" + e.id,
                name: e.name,
                start: e.start,
                location: e.location || "",
                allday: e.allday,
                type: "event",
            }));
        } catch (e) {
            console.warn("[DojoCalendarWidget] calendar.event failed:", e);
        }

        // ── Dojo class sessions ───────────────────────────────────────
        try {
            // Instructors see only their own sessions; others see all.
            const sessionDomain = [
                ["date_start", ">=", today + " 00:00:00"],
                ["date_start", "<=", until + " 23:59:59"],
                ["state", "not in", ["cancelled", "canceled"]],
            ];
            const sessions = await this.orm.searchRead(
                "disaster.class.session",
                sessionDomain,
                ["id", "name", "date_start", "date_end", "location",
                    "instructor_id", "course_id"],
                { order: "date_start asc", limit: 15 }
            );
            sessions.forEach(s => combined.push({
                id: "ses_" + s.id,
                name: s.name || (s.course_id && s.course_id[1]) || "Class",
                start: s.date_start,
                location: s.location || "",
                allday: false,
                type: "session",
                instructor: s.instructor_id ? s.instructor_id[1] : "",
            }));
        } catch (e) {
            console.warn("[DojoCalendarWidget] disaster.class.session failed:", e);
        }

        // Sort merged list by start time
        combined.sort((a, b) => (a.start > b.start ? 1 : -1));
        this.state.events = combined.slice(0, 18);
        this.state.loading = false;
    }

    openCalendar() {
        this.action.doAction("calendar.action_calendar_event");
    }

    openNewEvent() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "calendar.event",
            views: [[false, "form"]],
            target: "new",
        });
    }

    dayLabel(dtStr) {
        if (!dtStr) return "";
        const d = new Date(dtStr);
        const today = new Date();
        const tomorrow = new Date();
        tomorrow.setDate(today.getDate() + 1);
        if (_sameDay(d, today)) return _t("Today");
        if (_sameDay(d, tomorrow)) return _t("Tomorrow");
        return d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
    }

    timeLabel(dtStr, allday) {
        if (allday) return _t("All day");
        if (!dtStr) return "";
        return new Date(dtStr).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────
function _today() {
    return new Date().toISOString().slice(0, 10);
}
function _daysFromNow(n) {
    const d = new Date();
    d.setDate(d.getDate() + n);
    return d.toISOString().slice(0, 10);
}
function _sameDay(a, b) {
    return a.getFullYear() === b.getFullYear() &&
        a.getMonth() === b.getMonth() &&
        a.getDate() === b.getDate();
}
