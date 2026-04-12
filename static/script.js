"use strict";
/* ═══════════════════════════════════════════════════════════
   ZONNESTRAND VERHUUR · script.js
   Features: theme, toasts, notifications, search, onboarding,
             live poll, repair AJAX, broken modal, clock
   ═══════════════════════════════════════════════════════════ */

// ── 1. THEME ─────────────────────────────────────────────────
;(function applyTheme() {
    const saved = localStorage.getItem("zs-theme");
    const pref  = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", saved || pref);
})();

function setTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    localStorage.setItem("zs-theme", t);
}

// ── 2. TOASTS ────────────────────────────────────────────────
window.showToast = function(msg, type = "info") {
    const region = document.getElementById("toast-container");
    if (!region) return;
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.innerHTML = `<span class="toast-indicator"></span>
        <span class="toast-content">${msg}</span>
        <button class="toast-dismiss" onclick="dismissToast(this.closest('.toast'))">✕</button>`;
    region.appendChild(el);
    setTimeout(() => dismissToast(el), 5000);
};

window.dismissToast = function(el) {
    if (!el) return;
    el.style.transition = "opacity .3s, transform .3s";
    el.style.opacity    = "0";
    el.style.transform  = "translateX(112%)";
    setTimeout(() => el?.remove(), 320);
};

// ── 3. DOM READY ─────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {

    // Theme toggle
    document.getElementById("theme-btn")?.addEventListener("click", () => {
        const cur = document.documentElement.getAttribute("data-theme");
        setTheme(cur === "dark" ? "light" : "dark");
    });

    // Auto-dismiss server toasts
    document.querySelectorAll(".toast").forEach(el => setTimeout(() => dismissToast(el), 4500));

    // ── Live clock ──────────────────────────────────────────
    const clock = document.getElementById("live-clock");
    function tick() {
        if (!clock) return;
        const n = new Date(), p = x => String(x).padStart(2, "0");
        clock.textContent = `${p(n.getHours())}:${p(n.getMinutes())}:${p(n.getSeconds())}`;
    }
    tick(); setInterval(tick, 1000);

    // ── Hamburger ───────────────────────────────────────────
    const hamburger = document.getElementById("hamburger");
    const navLinks  = document.getElementById("nav-links");
    hamburger?.addEventListener("click", () => {
        const open = navLinks.classList.toggle("open");
        hamburger.classList.toggle("open", open);
        hamburger.setAttribute("aria-expanded", String(open));
    });
    document.addEventListener("click", e => {
        if (!hamburger?.contains(e.target) && !navLinks?.contains(e.target)) {
            navLinks?.classList.remove("open");
            hamburger?.classList.remove("open");
        }
    });

    // ── Confirm dialogs ─────────────────────────────────────
    document.addEventListener("click", e => {
        const el = e.target.closest("[data-confirm]");
        if (el && !confirm(el.dataset.confirm)) e.preventDefault();
    });

    // ── Chair filter (feature 10: responsive) ───────────────
    const filts = document.querySelectorAll(".filter-btn");
    const grid  = document.getElementById("chair-grid");
    filts.forEach(btn => btn.addEventListener("click", () => {
        filts.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        applyFiltersAndSearch();
    }));

    // ── Search bar (feature 8) ───────────────────────────────
    const searchInput = document.getElementById("chair-search");
    const searchClear = document.getElementById("search-clear");

    function applyFiltersAndSearch() {
        const activeFilter = document.querySelector(".filter-btn.active")?.dataset.filter || "all";
        const query = searchInput?.value.trim() || "";
        grid?.querySelectorAll(".chair-card").forEach(card => {
            const matchFilter = activeFilter === "all"
                || card.dataset.status === activeFilter
                || (activeFilter === "kapot" && (card.dataset.status === "kapot" || card.dataset.status === "in_reparatie"));
            const matchSearch = !query || card.dataset.id === query;
            card.classList.toggle("hidden", !(matchFilter && matchSearch));

            // Highlight searched card
            card.classList.toggle("is-highlighted", !!query && card.dataset.id === query);
        });
        if (searchClear) searchClear.style.display = query ? "flex" : "none";
    }

    searchInput?.addEventListener("input", applyFiltersAndSearch);

    searchClear?.addEventListener("click", () => {
        if (searchInput) searchInput.value = "";
        applyFiltersAndSearch();
    });

    // Scroll highlighted card into view
    searchInput?.addEventListener("change", () => {
        const highlighted = grid?.querySelector(".is-highlighted");
        highlighted?.scrollIntoView({ behavior: "smooth", block: "center" });
    });

    // ── NOTIFICATIONS (feature 9) ────────────────────────────
    const notifBtn      = document.getElementById("notif-btn");
    const notifDropdown = document.getElementById("notif-dropdown");
    const notifBadge    = document.getElementById("notif-badge");
    const ndList        = document.getElementById("nd-list");
    let notifOpen       = false;

    async function loadNotifications() {
        try {
            const res   = await fetch("/api/notifications");
            const items = await res.json();
            if (!ndList) return;
            if (items.length === 0) {
                ndList.innerHTML = '<p class="nd-empty">Geen meldingen.</p>';
            } else {
                ndList.innerHTML = items.map(n => `
                    <div class="nd-item nd-${n.type}">
                        <p class="nd-msg">${n.message}</p>
                        <span class="nd-time">${n.time}</span>
                    </div>`).join("");
            }
            if (notifBadge) notifBadge.style.display = "none";
        } catch { /* ignore */ }
    }

    async function pollNotifCount() {
        try {
            const res  = await fetch("/api/notif-count");
            const data = await res.json();
            if (notifBadge) {
                if (data.count > 0) {
                    notifBadge.textContent = data.count > 9 ? "9+" : data.count;
                    notifBadge.style.display = "flex";
                } else {
                    notifBadge.style.display = "none";
                }
            }
        } catch { /* ignore */ }
    }

    notifBtn?.addEventListener("click", (e) => {
        e.stopPropagation();
        notifOpen = !notifOpen;
        if (notifOpen) {
            notifDropdown?.removeAttribute("hidden");
            loadNotifications();
        } else {
            notifDropdown?.setAttribute("hidden", "");
        }
    });

    window.closeNotif = function() {
        notifOpen = false;
        notifDropdown?.setAttribute("hidden", "");
    };

    document.addEventListener("click", e => {
        const wrap = document.getElementById("notif-wrap");
        if (wrap && !wrap.contains(e.target)) closeNotif();
    });

    // Poll notification count every 30s
    if (notifBtn) {
        pollNotifCount();
        setInterval(pollNotifCount, 30000);
    }

    // ── AJAX repair forms ────────────────────────────────────
    document.addEventListener("submit", async e => {
        const form = e.target.closest(".repair-inline, .repair-row-form");
        if (!form) return;
        e.preventDefault();
        const chairId = form.dataset.chairId;
        const sel     = form.querySelector("select");
        const btn     = form.querySelector("button[type='submit']");
        const orig    = btn.textContent;
        btn.disabled  = true; btn.textContent = "…";

        const fd = new FormData();
        fd.append("repair_status", sel.value);
        try {
            const res  = await fetch(`/repair-status/${chairId}`, {
                method:"POST", headers:{"X-Requested-With":"XMLHttpRequest"}, body:fd
            });
            const data = await res.json();
            if (!res.ok || data.error) { showToast(data.error || "Fout.", "error"); return; }

            if (data.chair_status === "vrij") {
                showToast(`Stoel ${chairId}: ${data.label} ✅`, "success");
                const row = form.closest("tr");
                if (row) { row.style.transition="opacity .4s"; row.style.opacity="0"; setTimeout(()=>row.remove(),420); }
                const card = grid?.querySelector(`.chair-card[data-id="${chairId}"]`);
                if (card) setTimeout(()=>location.reload(), 700);
                return;
            }
            const card = grid?.querySelector(`.chair-card[data-id="${chairId}"]`);
            if (card) {
                const lbl  = card.querySelector(".cc-status");
                const icon = card.querySelector(".cc-icon");
                if (lbl)  lbl.textContent  = sel.value==="in_reparatie" ? "In reparatie" : "Kapot";
                if (icon) icon.textContent  = sel.value==="in_reparatie" ? "🛠" : "🔧";
            }
            const row = form.closest("tr");
            if (row) {
                const tag = row.querySelector("[class^='repair-tag']");
                if (tag) {
                    const map = {kapot:["repair-tag kapot","🔴 Kapot"],in_reparatie:["repair-tag in_reparatie","🛠 In reparatie"]};
                    const [cls,txt] = map[sel.value] || ["repair-tag kapot","🔴 Kapot"];
                    tag.className=cls; tag.textContent=txt;
                }
            }
            showToast(`Stoel ${chairId}: ${data.label}`, "success");
        } catch { showToast("Verbindingsfout.", "error"); }
        finally { btn.disabled=false; btn.textContent=orig; }
    });

    // ── Live polling (every 20s) ─────────────────────────────
    if (grid) {
        setInterval(async () => {
            try {
                const [cr, sr] = await Promise.all([fetch("/api/chairs"), fetch("/api/stats")]);
                const chairs = await cr.json(), stats = await sr.json();
                let changed = false;
                chairs.forEach(({ id, status }) => {
                    const c = grid.querySelector(`.chair-card[data-id="${id}"]`);
                    if (c && c.dataset.status !== status) changed = true;
                });
                if (changed) { location.reload(); return; }
                ["vrij","bezet","kapot"].forEach(s => {
                    const el = document.getElementById(`stat-${s}`);
                    if (el) el.textContent = stats[s];
                });
            } catch {}
        }, 20000);
    }

    // ── Broken modal ─────────────────────────────────────────
    const modal     = document.getElementById("broken-modal");
    const bForm     = document.getElementById("broken-form");
    const mChairNum = document.getElementById("modal-chair-n");
    const reasonSel = document.getElementById("reason_choice");
    const customGrp = document.getElementById("custom-reason-group");
    const customInp = document.getElementById("custom_reason");

    window.openBrokenModal = id => {
        if (!modal) return;
        mChairNum.textContent = id;
        bForm.action = `/broken/${id}`;
        modal.removeAttribute("hidden");
        document.body.style.overflow = "hidden";
        reasonSel?.focus();
    };
    window.closeBrokenModal = () => {
        modal?.setAttribute("hidden","");
        document.body.style.overflow = "";
        bForm?.reset();
        if (customGrp) customGrp.style.display = "none";
        if (customInp) customInp.required = false;
    };
    reasonSel?.addEventListener("change", () => {
        const show = reasonSel.value === "anders";
        if (customGrp) customGrp.style.display = show ? "block" : "none";
        if (customInp) customInp.required = show;
    });
    modal?.addEventListener("click", e => { if (e.target===modal) closeBrokenModal(); });
    document.addEventListener("keydown", e => { if (e.key==="Escape") closeBrokenModal(); });

    // ── Onboarding (feature 7) ───────────────────────────────
    window.obNext = function(step) {
        document.querySelectorAll(".ob-step").forEach(s => s.classList.remove("active"));
        document.querySelectorAll(".ob-dot").forEach(d => d.classList.remove("active"));
        const stepEl = document.getElementById(`ob-step-${step}`);
        const dotEl  = document.getElementById(`dot-${step}`);
        if (stepEl) stepEl.classList.add("active");
        if (dotEl)  dotEl.classList.add("active");
    };
    window.closeOnboarding = function() {
        const ob = document.getElementById("onboarding-modal");
        if (ob) {
            ob.style.transition = "opacity .3s";
            ob.style.opacity    = "0";
            setTimeout(() => ob.remove(), 320);
        }
        document.body.style.overflow = "";
    };
    if (document.getElementById("onboarding-modal")) {
        document.body.style.overflow = "hidden";
    }

});

// ── CONFETTI (feature 33) ──────────────────────────────────────────────
window.launchConfetti = function() {
    const canvas = document.createElement('canvas');
    canvas.id = 'confetti-canvas';
    canvas.style.cssText = 'position:fixed;inset:0;z-index:9998;pointer-events:none';
    document.body.appendChild(canvas);
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    const colors = ['#2a9abf','#2ebd6b','#f59e0b','#ef4444','#f5e6c8','#0f3f52'];
    const pieces = Array.from({length:120}, () => ({
        x: Math.random() * canvas.width,
        y: Math.random() * -canvas.height,
        w: 8 + Math.random() * 8,
        h: 5 + Math.random() * 5,
        color: colors[Math.floor(Math.random() * colors.length)],
        rot: Math.random() * 360,
        speed: 2 + Math.random() * 4,
        spin: (Math.random() - .5) * 8,
        drift: (Math.random() - .5) * 2,
    }));

    let frame;
    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        let done = 0;
        pieces.forEach(p => {
            p.y += p.speed; p.rot += p.spin; p.x += p.drift;
            if (p.y > canvas.height + 20) done++;
            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate(p.rot * Math.PI / 180);
            ctx.fillStyle = p.color;
            ctx.fillRect(-p.w/2, -p.h/2, p.w, p.h);
            ctx.restore();
        });
        if (done < pieces.length) frame = requestAnimationFrame(draw);
        else canvas.remove();
    }
    draw();
    setTimeout(() => { cancelAnimationFrame(frame); canvas.remove(); }, 5000);
};

// ── SWIPE FILTER (feature 30) ─────────────────────────────────────────
(function swipeFilter() {
    const bar = document.querySelector('.filter-bar');
    if (!bar) return;
    let startX = 0, startY = 0;
    bar.addEventListener('touchstart', e => { startX = e.touches[0].clientX; startY = e.touches[0].clientY; }, {passive:true});
    bar.addEventListener('touchend', e => {
        const dx = e.changedTouches[0].clientX - startX;
        const dy = e.changedTouches[0].clientY - startY;
        if (Math.abs(dx) < Math.abs(dy) * 1.5 || Math.abs(dx) < 40) return;
        const btns = Array.from(document.querySelectorAll('.filter-btn'));
        const active = btns.findIndex(b => b.classList.contains('active'));
        let next = dx < 0 ? active + 1 : active - 1;
        if (next < 0) next = btns.length - 1;
        if (next >= btns.length) next = 0;
        btns[next]?.click();
        if (navigator.vibrate) navigator.vibrate(30); // haptic
    }, {passive:true});
})();