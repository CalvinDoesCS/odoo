/* global KIOSK_SESSION_ID */
'use strict';

// ================================================================
//  Dojo Kiosk – kiosk.js
//  Modes: barcode scan | PIN number pad | name search
// ================================================================

var kiosk = (function () {

    // ---- State --------------------------------------------------
    var sessionId = 0;
    var currentMode = 'barcode';   // 'barcode' | 'pin' | 'name'
    var memberPinVal = '';
    var selectedMember = null;
    var resetTimer = null;
    var barcodeBuffer = '';
    var barcodeTimer = null;

    // ---- Belt badge colours ------------------------------------
    var BELT_CLASS = {
        'white': 'belt-white',
        'yellow': 'belt-yellow',
        'orange': 'belt-orange',
        'green': 'belt-green',
        'blue': 'belt-blue',
        'purple': 'belt-purple',
        'brown': 'belt-brown',
        'red': 'belt-red',
        'black': 'belt-black',
    };

    // ---- Helpers -----------------------------------------------
    function debounce(fn, ms) {
        var t;
        return function () {
            var args = arguments;
            clearTimeout(t);
            t = setTimeout(function () { fn.apply(null, args); }, ms);
        };
    }

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

    // ---- Clock -------------------------------------------------
    function updateClock() {
        var now = new Date();
        var h = String(now.getHours()).padStart(2, '0');
        var m = String(now.getMinutes()).padStart(2, '0');
        var clockEl = el('kiosk-clock');
        if (clockEl) clockEl.textContent = h + ':' + m;
    }

    // ---- Session selector --------------------------------------
    function selectSession(val) {
        sessionId = parseInt(val, 10) || 0;
    }

    // ---- Mode switching ----------------------------------------
    function setMode(mode) {
        currentMode = mode;

        ['barcode', 'pin', 'name'].forEach(function (m) {
            var tab = el('tab-' + m);
            if (tab) tab.classList.toggle('active', m === mode);
        });

        var areas = {
            barcode: el('kiosk-barcode-area'),
            pin: el('kiosk-pin-area'),
            name: el('kiosk-name-area'),
        };
        Object.keys(areas).forEach(function (k) {
            if (areas[k]) areas[k].style.display = (k === mode) ? '' : 'none';
        });

        if (mode === 'barcode') {
            barcodeBuffer = '';
            var bi = el('kiosk-barcode-input');
            if (bi) bi.focus();
        } else if (mode === 'pin') {
            resetMemberPin();
        } else if (mode === 'name') {
            var ni = el('kiosk-name-input');
            if (ni) { ni.value = ''; ni.focus(); }
            showIdle();
        }
    }

    // ---- Barcode mode ------------------------------------------
    function onDocumentKeydown(e) {
        if (currentMode !== 'barcode') return;
        if (e.key === 'Shift' || e.key === 'Control' || e.key === 'Alt' || e.key === 'Meta') return;

        if (e.key === 'Enter') {
            clearTimeout(barcodeTimer);
            var barcode = barcodeBuffer.trim();
            barcodeBuffer = '';
            if (barcode.length >= 2) {
                lookupAndCheckin('barcode', barcode);
            }
        } else if (e.key.length === 1) {
            barcodeBuffer += e.key;
            clearTimeout(barcodeTimer);
            barcodeTimer = setTimeout(function () { barcodeBuffer = ''; }, 1500);
        }
    }

    // ---- PIN mode ----------------------------------------------
    function memberPinKey(k) {
        clearTimeout(resetTimer);
        if (k === 'back') {
            memberPinVal = memberPinVal.slice(0, -1);
        } else if (memberPinVal.length < 4) {
            memberPinVal += String(k);
        }
        updatePinDots();
        var err = el('member-pin-error');
        if (err) err.style.display = 'none';

        if (memberPinVal.length === 4) {
            resetTimer = setTimeout(function () {
                lookupAndCheckin('pin', memberPinVal);
            }, 400);
        }
    }

    function updatePinDots() {
        for (var i = 0; i < 4; i++) {
            var dot = el('mpd-' + i);
            if (dot) dot.classList.toggle('filled', i < memberPinVal.length);
        }
    }

    function resetMemberPin() {
        memberPinVal = '';
        updatePinDots();
        clearTimeout(resetTimer);
        var err = el('member-pin-error');
        if (err) err.style.display = 'none';
    }

    // ---- Lookup & check-in (barcode / PIN) ---------------------
    function lookupAndCheckin(mode, value) {
        postJson('/dojo/kiosk/lookup', { mode: mode, value: value })
            .then(function (data) {
                if (data.error || !data.member) {
                    if (mode === 'pin') {
                        var err = el('member-pin-error');
                        if (err) err.style.display = 'block';
                        resetTimer = setTimeout(resetMemberPin, 2000);
                    } else {
                        var icon = document.querySelector('.kiosk-barcode-icon');
                        if (icon) {
                            icon.classList.add('kiosk-barcode-error-flash');
                            setTimeout(function () {
                                icon.classList.remove('kiosk-barcode-error-flash');
                            }, 600);
                        }
                    }
                    return;
                }
                var m = data.member;
                selectedMember = { id: m.id, name: m.name, belt: m.belt_rank, avatar: m.avatar_url };
                doCheckin();
            })
            .catch(function () {
                var err = el('member-pin-error');
                if (err) err.style.display = 'block';
            });
    }

    // ---- Name search mode --------------------------------------
    function fetchSearch(query) {
        query = (query || '').trim();
        if (!query) { showIdle(); return; }
        postJson('/dojo/kiosk/search', { query: query, session_id: sessionId })
            .then(function (data) {
                if (data.error) { showNoResults(); return; }
                renderResults(data.members || []);
            })
            .catch(showNoResults);
    }

    var debouncedSearch = debounce(fetchSearch, 300);

    function renderResults(members) {
        var results = el('kiosk-results');
        var idle = el('kiosk-idle');
        if (!results) return;

        if (!members.length) {
            results.innerHTML = '<div class="kiosk-no-results">No members found — ask staff for help.</div>';
            results.style.display = 'block';
            if (idle) idle.style.display = 'none';
            return;
        }

        results.innerHTML = members.map(function (m) {
            var beltCls = BELT_CLASS[m.belt_rank] || 'belt-white';
            var name = escHtml(m.name);
            var belt = escHtml((m.belt_rank || 'white').replace('_', ' '));
            // JSON.stringify inside a double-quoted HTML attribute: encode " as &quot;
            function attrJson(v) { return JSON.stringify(v).replace(/"/g, '&quot;'); }
            return '<div class="kiosk-member-card" ' +
                'onclick="kiosk.onMemberTap(' + m.id + ',' + attrJson(m.name) + ',' +
                attrJson(m.belt_rank || 'white') + ',' + attrJson(m.avatar_url || '') + ')">' +
                '<img class="kiosk-member-avatar" src="' + escHtml(m.avatar_url || '/web/image/res.partner/' + m.id + '/avatar_128') + '" alt="">' +
                '<div class="kiosk-member-name">' + name + '</div>' +
                '<div class="kiosk-member-belt ' + beltCls + '">' + belt + '</div>' +
                '</div>';
        }).join('');

        results.style.display = 'grid';
        if (idle) idle.style.display = 'none';
    }

    function showIdle() {
        var results = el('kiosk-results');
        var idle = el('kiosk-idle');
        if (results) { results.style.display = 'none'; results.innerHTML = ''; }
        if (idle) idle.style.display = 'flex';
    }

    function showNoResults() {
        var results = el('kiosk-results');
        if (results) {
            results.innerHTML = '<div class="kiosk-no-results">No members found — ask staff for help.</div>';
            results.style.display = 'block';
        }
    }

    function onMemberTap(id, name, belt, avatar) {
        selectedMember = { id: id, name: name, belt: belt, avatar: avatar };
        doCheckin();
    }

    // ---- Check-in POST -----------------------------------------
    function doCheckin() {
        if (!selectedMember) return;
        postJson('/dojo/kiosk/checkin', {
            partner_id: selectedMember.id,
            session_id: sessionId,
        }).then(function (data) {
            showConfirm(data);
        }).catch(function () {
            showConfirm({
                status: 'error', name: selectedMember.name,
                belt_rank: selectedMember.belt, avatar_url: selectedMember.avatar,
            });
        });
    }

    // ---- Confirm overlay ---------------------------------------
    function showConfirm(data) {
        var overlay = el('kiosk-confirm');
        if (!overlay) return;

        var beltCls = BELT_CLASS[data.belt_rank] || 'belt-white';
        var name = data.name || (selectedMember && selectedMember.name) || '';
        var belt = (data.belt_rank || 'white').replace('_', ' ');
        var avatar = data.avatar_url || (selectedMember ? selectedMember.avatar : '') || '';

        var msgEl = el('kiosk-confirm-msg');
        if (data.status === 'ok') {
            msgEl.textContent = '✅ Checked In!';
            msgEl.className = 'kiosk-confirm-msg';
        } else if (data.status === 'already_in') {
            msgEl.textContent = '👋 Already Checked In';
            msgEl.className = 'kiosk-confirm-msg already-in';
        } else if (data.status === 'no_session') {
            msgEl.textContent = '⚠️ No active session selected';
            msgEl.className = 'kiosk-confirm-msg already-in';
        } else {
            msgEl.textContent = '⚠️ Something went wrong';
            msgEl.className = 'kiosk-confirm-msg already-in';
        }

        el('kiosk-confirm-name').textContent = name;

        var beltEl = el('kiosk-confirm-belt');
        beltEl.textContent = belt;
        beltEl.className = 'kiosk-confirm-belt ' + beltCls;

        el('kiosk-confirm-avatar').src = avatar ||
            '/web/image/res.partner/' + (selectedMember ? selectedMember.id : 0) + '/avatar_128';

        var bar = el('kiosk-timer-bar');
        if (bar) {
            bar.style.animation = 'none';
            void bar.offsetWidth;
            bar.style.animation = '';
        }

        overlay.style.display = 'flex';
        clearTimeout(resetTimer);
        resetTimer = setTimeout(resetToSearch, 5000);
    }

    function resetToSearch() {
        var overlay = el('kiosk-confirm');
        if (overlay) overlay.style.display = 'none';

        selectedMember = null;

        if (currentMode === 'barcode') {
            barcodeBuffer = '';
            var bi = el('kiosk-barcode-input');
            if (bi) bi.focus();
        } else if (currentMode === 'pin') {
            resetMemberPin();
        } else {
            var ni = el('kiosk-name-input');
            if (ni) { ni.value = ''; ni.focus(); }
            var clr = el('kiosk-clear');
            if (clr) clr.style.display = 'none';
            showIdle();
        }
    }

    function clearInput() {
        var input = el('kiosk-name-input');
        if (input) { input.value = ''; input.focus(); }
        var btn = el('kiosk-clear');
        if (btn) btn.style.display = 'none';
        showIdle();
    }

    // ---- Init --------------------------------------------------
    function init() {
        sessionId = (typeof KIOSK_SESSION_ID !== 'undefined') ? (KIOSK_SESSION_ID || 0) : 0;

        updateClock();
        setInterval(updateClock, 10000);

        // Start in barcode mode
        setMode('barcode');

        // Global keydown captures barcode scanner input
        document.addEventListener('keydown', onDocumentKeydown);

        // Click barcode area → re-focus hidden input
        var barcodeArea = el('kiosk-barcode-area');
        if (barcodeArea) {
            barcodeArea.addEventListener('click', function () {
                var bi = el('kiosk-barcode-input');
                if (bi) bi.focus();
            });
        }

        // Name search input
        var nameInput = el('kiosk-name-input');
        if (nameInput) {
            nameInput.addEventListener('input', function () {
                var val = this.value;
                var clr = el('kiosk-clear');
                if (clr) clr.style.display = val ? 'block' : 'none';
                debouncedSearch(val);
            });
        }

        // Tap outside confirm card to dismiss
        var overlay = el('kiosk-confirm');
        if (overlay) {
            overlay.addEventListener('click', function (e) {
                if (e.target === overlay) {
                    clearTimeout(resetTimer);
                    resetToSearch();
                }
            });
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    return {
        onMemberTap: onMemberTap,
        clearInput: clearInput,
        selectSession: selectSession,
        setMode: setMode,
        memberPinKey: memberPinKey,
    };

})();

function kioskSelectSession(val) { kiosk.selectSession(val); }
function kioskClear() { kiosk.clearInput(); }
function kioskSetMode(m) { kiosk.setMode(m); }
function kioskMemberPinKey(k) { kiosk.memberPinKey(k); }
