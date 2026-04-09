"use strict";
/* ══════════════════════════════════════════════
   ZONNESTRAND VERHUUR · script.js
   ══════════════════════════════════════════════ */

// ── DARK MODE ────────────────────────────────
;(function initTheme() {
    const saved = localStorage.getItem("zs-theme");
    const sys   = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", saved || sys);
})();

function setTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    localStorage.setItem("zs-theme", t);
}

// ── TOAST ────────────────────────────────────
window.showToast = function(msg, type="info") {
    const stack = document.getElementById("toast-stack");
    if (!stack) return;
    const el = document.createElement("div");
    el.className = `toast toast-${type}`;
    const icons = { success:"✓", error:"✕", info:"i" };
    el.innerHTML = `
      <span class="toast-bar"></span>
      <span class="toast-body">
        <strong class="toast-icon">${icons[type]||"i"}</strong>
        <span>${msg}</span>
      </span>
      <button class="toast-x" onclick="dismissToast(this.closest('.toast'))">×</button>`;
    stack.appendChild(el);
    setTimeout(() => dismissToast(el), 5000);
};

window.dismissToast = function(el) {
    if (!el) return;
    el.style.transition = "opacity .3s, transform .3s";
    el.style.opacity = "0";
    el.style.transform = "translateX(110%)";
    setTimeout(() => el?.remove(), 320);
};

// ── DOM READY ────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {

    // Dark mode toggle
    document.getElementById("dark-toggle")?.addEventListener("click", () => {
        const cur = document.documentElement.getAttribute("data-theme");
        setTheme(cur === "dark" ? "light" : "dark");
    });

    // Auto-dismiss server toasts
    document.querySelectorAll(".toast").forEach(el => setTimeout(() => dismissToast(el), 4500));

    // Live clock
    const clock = document.getElementById("live-clock");
    function tick() {
        if (!clock) return;
        const n = new Date();
        const p = x => String(x).padStart(2,"0");
        clock.textContent = `${p(n.getHours())}:${p(n.getMinutes())}:${p(n.getSeconds())}`;
    }
    tick(); setInterval(tick, 1000);

    // Hamburger
    const toggle  = document.getElementById("nav-toggle");
    const navMenu = document.getElementById("nav-menu");
    toggle?.addEventListener("click", () => {
        const o = navMenu.classList.toggle("open");
        toggle.classList.toggle("open", o);
    });
    document.addEventListener("click", e => {
        if (navMenu?.classList.contains("open") && !toggle?.contains(e.target) && !navMenu.contains(e.target)) {
            navMenu.classList.remove("open");
            toggle?.classList.remove("open");
        }
    });

    // Scroll: navbar shadow
    const navbar = document.getElementById("navbar");
    window.addEventListener("scroll", () => {
        navbar?.classList.toggle("scrolled", window.scrollY > 10);
    }, { passive: true });

    // Confirm dialogs
    document.addEventListener("click", e => {
        const el = e.target.closest("[data-confirm]");
        if (el && !confirm(el.dataset.confirm)) e.preventDefault();
    });

    // Chair filter
    const filts = document.querySelectorAll(".filt");
    const grid  = document.getElementById("chair-grid");
    filts.forEach(btn => btn.addEventListener("click", () => {
        filts.forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        const f = btn.dataset.filter;
        grid?.querySelectorAll(".chair-card").forEach(card => {
            const s = card.dataset.status;
            const show = f === "all" || s === f || (f === "kapot" && (s === "kapot" || s === "in_reparatie"));
            card.classList.toggle("hidden", !show);
        });
    }));

    // Live polling
    if (grid) {
        setInterval(async () => {
            try {
                const [cr, sr] = await Promise.all([fetch("/api/chairs"), fetch("/api/stats")]);
                const chairs = await cr.json();
                const stats  = await sr.json();
                let changed = false;
                chairs.forEach(({id, status}) => {
                    const c = grid.querySelector(`.chair-card[data-id="${id}"]`);
                    if (c && c.dataset.status !== status) changed = true;
                });
                if (changed) { window.location.reload(); return; }
                ["vrij","bezet","kapot"].forEach(s => {
                    const el = document.getElementById(`stat-${s}`);
                    if (el) el.textContent = stats[s];
                });
            } catch {}
        }, 20000);
    }

    // ── AJAX REPAIR FORMS (no page reload) ──────────────
    // Handles both .repair-inline (chair cards) and .repair-row-form (beheer table)
    document.addEventListener("submit", async function(e) {
        const form = e.target.closest(".repair-inline, .repair-row-form");
        if (!form) return;
        e.preventDefault();
        const chairId   = form.dataset.chairId;
        const sel       = form.querySelector("select");
        const newStatus = sel.value;
        const btn       = form.querySelector("button[type='submit']");
        const origLabel = btn.textContent;
        btn.disabled    = true;
        btn.textContent = "…";

        try {
            const fd = new FormData();
            fd.append("repair_status", newStatus);
            const res  = await fetch(`/repair-status/${chairId}`, {
                method:  "POST",
                headers: { "X-Requested-With": "XMLHttpRequest" },
                body:    fd,
            });
            const data = await res.json();
            if (!res.ok || data.error) {
                window.showToast(data.error || "Fout bij opslaan.", "error");
                return;
            }

            if (data.chair_status === "vrij") {
                // Gerepareerd — remove the row/card after short delay
                window.showToast(`Stoel ${chairId}: ${data.label} ✅`, "success");

                // Remove from beheer table row if present
                const row = form.closest("tr");
                if (row) {
                    row.style.transition = "opacity .4s";
                    row.style.opacity = "0";
                    setTimeout(() => row.remove(), 420);
                }

                // Update chair card on index page if present
                const card = document.querySelector(`.chair-card[data-id="${chairId}"]`);
                if (card) {
                    setTimeout(() => window.location.reload(), 600);
                    return;
                }
                return;
            }

            // Still kapot/in_reparatie — update card icon/label if on index page
            const card = document.querySelector(`.chair-card[data-id="${chairId}"]`);
            if (card) {
                const lblEl  = card.querySelector(".cc-label");
                const iconEl = card.querySelector(".cc-icon");
                if (lblEl)  lblEl.textContent  = newStatus === "in_reparatie" ? "In reparatie" : "Kapot";
                if (iconEl) iconEl.textContent  = newStatus === "in_reparatie" ? "🛠" : "🔧";
            }

            // Update repair tag in beheer table row if present
            const row = form.closest("tr");
            if (row) {
                const tag = row.querySelector(".repair-tag");
                if (tag) {
                    const tagMap = {
                        kapot:        { cls: "rt-kapot",        txt: "🔴 Kapot" },
                        in_reparatie: { cls: "rt-in_reparatie", txt: "🛠 In reparatie" },
                    };
                    const t = tagMap[newStatus];
                    if (t) {
                        tag.className = `repair-tag ${t.cls}`;
                        tag.textContent = t.txt;
                    }
                }
            }

            window.showToast(`Stoel ${chairId}: ${data.label}`, "success");
        } catch {
            window.showToast("Verbindingsfout bij opslaan.", "error");
        } finally {
            btn.disabled    = false;
            btn.textContent = origLabel;
        }
    });
    const modal      = document.getElementById("broken-modal");
    const brokenForm = document.getElementById("broken-form");
    const modalChairN = document.getElementById("modal-chair-n");
    const reasonSel   = document.getElementById("reason_choice");
    const customGroup = document.getElementById("custom-reason-group");
    const customInput = document.getElementById("custom_reason");

    window.openBrokenModal = function(id) {
        if (!modal) return;
        modalChairN.textContent = id;
        brokenForm.action = `/broken/${id}`;
        modal.removeAttribute("hidden");
        document.body.style.overflow = "hidden";
        reasonSel?.focus();
    };
    window.closeBrokenModal = function() {
        modal?.setAttribute("hidden", "");
        document.body.style.overflow = "";
        brokenForm?.reset();
        if (customGroup) customGroup.style.display = "none";
        if (customInput) customInput.required = false;
    };

    // Show/hide custom reason field
    reasonSel?.addEventListener("change", () => {
        const isAnders = reasonSel.value === "anders";
        if (customGroup) customGroup.style.display = isAnders ? "block" : "none";
        if (customInput) customInput.required = isAnders;
    });

    modal?.addEventListener("click", e => { if (e.target === modal) closeBrokenModal(); });
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeBrokenModal(); });

});