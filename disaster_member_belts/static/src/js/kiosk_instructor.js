/* Dojo Kiosk – Instructor Dashboard JS */
'use strict';

var kiInstructor = (function () {

    var _selectedSessionId = null;
    var _addDebounceTimer = null;
    var _autoRefreshTimer = null;

    // ── Helpers ─────────────────────────────────────────────────────
    function el(id) { return document.getElementById(id); }

    function getCsrf() {
        var m = document.querySelector('meta[name=csrf-token]');
        return m ? m.getAttribute('content') : '';
    }

    function postJson(url, data) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrf(),
            },
            body: JSON.stringify({ jsonrpc: '2.0', method: 'call', params: data }),
        }).then(function (r) { return r.json(); })
            .then(function (resp) { return resp.result || resp; });
    }

    function escHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    var BELT_CLASS = {
        white: 'belt-white', yellow: 'belt-yellow', orange: 'belt-orange',
        green: 'belt-green', blue: 'belt-blue', purple: 'belt-purple',
        brown: 'belt-brown', red: 'belt-red', black: 'belt-black',
    };

    // ── Clock ───────────────────────────────────────────────────────
    function updateClock() {
        var now = new Date();
        var h = String(now.getHours()).padStart(2, '0');
        var m = String(now.getMinutes()).padStart(2, '0');
        var c = el('ki-clock');
        if (c) c.textContent = h + ':' + m;
    }

    // ── Session selection ───────────────────────────────────────────
    function selectSession(id) {
        _selectedSessionId = parseInt(id, 10);

        // Highlight in left panel
        document.querySelectorAll('.ki-session-row').forEach(function (row) {
            row.classList.toggle('ki-session-active', parseInt(row.dataset.id, 10) === _selectedSessionId);
        });

        // Show detail panel
        el('ki-detail-empty').style.display = 'none';
        el('ki-detail-content').style.display = 'block';

        refreshAttendees();
        startAutoRefresh();
    }

    // ── Refresh attendance list ─────────────────────────────────────
    function refreshAttendees() {
        if (!_selectedSessionId) return;

        postJson('/dojo/kiosk/instructor/attendees', { session_id: _selectedSessionId })
            .then(function (data) {
                if (data.error) return;
                renderSessionDetail(data.session, data.attendees);
            })
            .catch(function () { });
    }

    function renderSessionDetail(session, attendees) {
        // Header
        var nameEl = el('ki-det-name');
        var metaEl = el('ki-det-meta');
        if (nameEl) nameEl.textContent = session.name;
        if (metaEl) {
            metaEl.textContent = session.time +
                (session.instructor ? ' · ' + session.instructor : '') +
                (session.location ? ' · ' + session.location : '');
        }

        // Action buttons visibility based on state
        var btnStart = el('ki-btn-start');
        var btnEnd = el('ki-btn-end');
        var btnCancel = el('ki-btn-cancel');
        if (btnStart) btnStart.style.display = (session.state === 'scheduled') ? '' : 'none';
        if (btnEnd) btnEnd.style.display = (session.state === 'in_progress') ? '' : 'none';
        if (btnCancel) btnCancel.style.display = (session.state === 'cancelled') ? 'none' : '';

        // Stats
        var remaining = Math.max(0, (session.capacity || 0) - (session.count || 0));
        setText('ki-stat-count', attendees.length);
        setText('ki-stat-capacity', session.capacity || 0);
        setText('ki-stat-remaining', remaining);

        // Attendance list
        var listEl = el('ki-attendee-list');
        var emptyEl = el('ki-attendee-empty');
        if (!listEl) return;

        if (!attendees.length) {
            listEl.innerHTML = '';
            if (emptyEl) emptyEl.style.display = 'block';
        } else {
            if (emptyEl) emptyEl.style.display = 'none';
            listEl.innerHTML = attendees.map(function (a) {
                var beltCls = BELT_CLASS[a.belt_rank] || 'belt-white';
                var belt = (a.belt_rank || 'white').replace('_', ' ');
                return '<div class="ki-att-row">' +
                    '<img class="ki-att-avatar" src="' + escHtml(a.avatar_url) + '" alt=""/>' +
                    '<div class="ki-att-info">' +
                    '  <div class="ki-att-name">' + escHtml(a.name) + '</div>' +
                    '  <div class="ki-att-belt ' + beltCls + '">' + escHtml(belt) + '</div>' +
                    '</div>' +
                    '<div class="ki-att-time">' + escHtml(a.check_in) + '</div>' +
                    '</div>';
            }).join('');
        }
    }

    function setText(id, val) {
        var e = el(id);
        if (e) e.textContent = val;
    }

    // ── Session state actions ───────────────────────────────────────
    function sessionAction(action) {
        if (!_selectedSessionId) return;
        postJson('/dojo/kiosk/instructor/session_action', {
            session_id: _selectedSessionId,
            action: action,
        }).then(function (data) {
            if (data.error) {
                alert('Cannot perform action: ' + data.error);
                return;
            }
            // Update pill in left panel
            var row = document.querySelector('.ki-session-row[data-id="' + _selectedSessionId + '"]');
            if (row) {
                row.className = 'ki-session-row ki-session-' + data.state + ' ki-session-active';
                var badge = row.querySelector('.ki-session-badge');
                if (badge) {
                    badge.className = 'ki-session-badge ki-badge-' + data.state;
                    var labels = {
                        scheduled: 'Scheduled', in_progress: 'In Progress',
                        done: 'Done', cancelled: 'Cancelled'
                    };
                    badge.textContent = labels[data.state] || data.state;
                }
            }
            refreshAttendees();
        });
    }

    // ── Add student live search ─────────────────────────────────────
    function onAddInput(val) {
        clearTimeout(_addDebounceTimer);
        var results = el('ki-add-results');
        if (!val || val.length < 2) {
            if (results) results.style.display = 'none';
            return;
        }
        _addDebounceTimer = setTimeout(function () {
            postJson('/dojo/kiosk/instructor/search_member', { query: val })
                .then(function (data) {
                    renderAddResults(data.members || []);
                });
        }, 300);
    }

    function renderAddResults(members) {
        var results = el('ki-add-results');
        if (!results) return;
        if (!members.length) {
            results.innerHTML = '<div class="ki-add-none">No members found</div>';
            results.style.display = 'block';
            return;
        }
        results.innerHTML = members.map(function (m) {
            var beltCls = BELT_CLASS[m.belt_rank] || 'belt-white';
            var belt = (m.belt_rank || 'white').replace('_', ' ');
            return '<div class="ki-add-result-row" onclick="kiInstructor.manualCheckin(' + m.id + ')">' +
                '<img class="ki-add-avatar" src="' + escHtml(m.avatar_url) + '" alt=""/>' +
                '<div class="ki-add-mname">' + escHtml(m.name) + '</div>' +
                '<div class="ki-add-mbelt ' + beltCls + '">' + escHtml(belt) + '</div>' +
                '</div>';
        }).join('');
        results.style.display = 'block';
    }

    function manualCheckin(partnerId) {
        if (!_selectedSessionId) return;
        var inp = el('ki-add-input');
        if (inp) inp.value = '';
        var results = el('ki-add-results');
        if (results) results.style.display = 'none';

        postJson('/dojo/kiosk/instructor/manual_checkin', {
            session_id: _selectedSessionId,
            partner_id: partnerId,
        }).then(function (data) {
            refreshAttendees();
        });
    }

    // ── Auto-refresh every 15 seconds ──────────────────────────────
    function startAutoRefresh() {
        clearInterval(_autoRefreshTimer);
        _autoRefreshTimer = setInterval(refreshAttendees, 15000);
    }

    // ── Init ────────────────────────────────────────────────────────
    function init() {
        updateClock();
        setInterval(updateClock, 10000);

        // Close add-results when clicking outside
        document.addEventListener('click', function (e) {
            var results = el('ki-add-results');
            var input = el('ki-add-input');
            if (results && input && !input.contains(e.target) && !results.contains(e.target)) {
                results.style.display = 'none';
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        selectSession: selectSession,
        refreshAttendees: refreshAttendees,
        sessionAction: sessionAction,
        onAddInput: onAddInput,
        manualCheckin: manualCheckin,
    };

})();
