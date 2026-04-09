"use strict";
/* ═══════════════════════════════════════════════════
   ZONNESTRAND VERHUUR · script.js
   ═══════════════════════════════════════════════════ */

// ── 1. THEME ─────────────────────────────────────────
;(function applyTheme() {
    const saved = localStorage.getItem("zs-theme");
    const pref  = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", saved || pref);
})();

function setTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    localStorage.setItem("zs-theme", t);
}

// ── 2. TOAST ─────────────────────────────────────────
window.showToast = function(msg, type = "info") {
    const region = document.getElementById("toast-region");
    if (!region) return;
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    el.innerHTML = `
        <span class="toast-indicator"></span>
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

// ── 3. DOM READY ─────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {

    // Theme toggle
    document.getElementById("theme-btn")?.addEventListener("click", () => {
        const cur = document.documentElement.getAttribute("data-theme");
        setTheme(cur === "dark" ? "light" : "dark");
    });

    // Auto-dismiss server toasts
    document.querySelectorAll(".toast").forEach(el => setTimeout(() => dismissToast(el), 4500));

    // Live clock
    const clock = document.getElementById("live-clock");
    function tick() {
        if (!clock) return;
        const n = new Date(), p = x => String(x).padStart(2, "0");
        clock.textContent = `${p(n.getHours())}:${p(n.getMinutes())}:${p(n.getSeconds())}`;
    }
    tick(); setInterval(tick, 1000);

    // Hamburger menu
    const hamburger = document.getElementById("hamburger");
    const navLinks  = document.getElementById("nav-links");
    hamburger?.addEventListener("click", () => {
        const open = navLinks.classList.toggle("is-open");
        hamburger.classList.toggle("is-open", open);
        hamburger.setAttribute("aria-expanded", open);
    });
    document.addEventListener("click", e => {
        if (!hamburger?.contains(e.target) && !navLinks?.contains(e.target)) {
            navLinks?.classList.remove("is-open");
            hamburger?.classList.remove("is-open");
        }
    });

    // Navbar scroll shadow
    const header = document.getElementById("site-header");
    window.addEventListener("scroll", () => {
        header?.classList.toggle("is-scrolled", window.scrollY > 4);
    }, { passive: true });

    // Confirm on data-confirm links/buttons
    document.addEventListener("click", e => {
        const el = e.target.closest("[data-confirm]");
        if (el && !confirm(el.dataset.confirm)) e.preventDefault();
    });

    // Chair filter buttons  (new class names: .filt, .is-active, .is-hidden)
    const filts = document.querySelectorAll(".filt");
    const grid  = document.getElementById("chair-grid");
    filts.forEach(btn => btn.addEventListener("click", () => {
        filts.forEach(b => b.classList.remove("is-active"));
        btn.classList.add("is-active");
        const f = btn.dataset.filter;
        grid?.querySelectorAll(".chair-card").forEach(card => {
            const s    = card.dataset.status;
            const show = f === "all"
                || s === f
                || (f === "kapot" && (s === "kapot" || s === "in_reparatie"));
            card.classList.toggle("is-hidden", !show);
        });
    }));

    // ── AJAX repair forms (.repair-inline and .repair-row-form) ──
    document.addEventListener("submit", async e => {
        const form = e.target.closest(".repair-inline, .repair-row-form");
        if (!form) return;
        e.preventDefault();
        const chairId = form.dataset.chairId;
        const sel     = form.querySelector("select");
        const btn     = form.querySelector("button[type='submit']");
        const orig    = btn.textContent;
        btn.disabled  = true;
        btn.textContent = "…";

        const fd = new FormData();
        fd.append("repair_status", sel.value);
        try {
            const res  = await fetch(`/repair-status/${chairId}`, {
                method: "POST", headers: { "X-Requested-With": "XMLHttpRequest" }, body: fd,
            });
            const data = await res.json();
            if (!res.ok || data.error) { window.showToast(data.error || "Fout.", "error"); return; }

            if (data.chair_status === "vrij") {
                window.showToast(`Stoel ${chairId}: ${data.label} ✅`, "success");
                const row = form.closest("tr");
                if (row) { row.style.transition = "opacity .4s"; row.style.opacity = "0"; setTimeout(() => row.remove(), 420); }
                const card = document.querySelector(`.chair-card[data-id="${chairId}"]`);
                if (card) setTimeout(() => location.reload(), 700);
                return;
            }

            // Update card in-place
            const card = document.querySelector(`.chair-card[data-id="${chairId}"]`);
            if (card) {
                const lbl  = card.querySelector(".cc-status");
                const icon = card.querySelector(".cc-icon");
                if (lbl)  lbl.textContent  = sel.value === "in_reparatie" ? "In reparatie" : "Kapot";
                if (icon) icon.textContent  = sel.value === "in_reparatie" ? "🛠" : "🔧";
            }
            // Update tag in beheer row
            const row = form.closest("tr");
            if (row) {
                const tag = row.querySelector("[class^='repair-tag']");
                if (tag) {
                    const map = { kapot: ["repair-tag-kapot","🔴 Kapot"], in_reparatie: ["repair-tag-reparatie","🛠 In reparatie"] };
                    const [cls, txt] = map[sel.value] || ["repair-tag-kapot","🔴 Kapot"];
                    tag.className = cls; tag.textContent = txt;
                }
            }
            window.showToast(`Stoel ${chairId}: ${data.label}`, "success");
        } catch { window.showToast("Verbindingsfout.", "error"); }
        finally { btn.disabled = false; btn.textContent = orig; }
    });

    // ── Live polling (index page) ──
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

    // ── Broken modal ──
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
        modal?.setAttribute("hidden", "");
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
    modal?.addEventListener("click", e => { if (e.target === modal) closeBrokenModal(); });
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeBrokenModal(); });

});