/* ═══════════════════════════════════════════════
   STRANDSTOELEN VERHUUR · script.js
   ═══════════════════════════════════════════════ */

"use strict";

// ── DARK MODE ────────────────────────────────────────────
function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
}

(function initTheme() {
    const saved = localStorage.getItem("theme");
    if (saved) {
        applyTheme(saved);
    } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
        applyTheme("dark");
    }
})();

// ── TOAST HELPER (callable from anywhere) ────────────────
window.showToast = function(msg, type = "info") {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    const icons = { success: "✅", error: "❌", info: "ℹ️" };
    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || "ℹ️"}</span>
        <span class="toast-msg">${msg}</span>
        <button class="toast-close" aria-label="Sluiten">×</button>
    `;
    toast.querySelector(".toast-close").onclick = () => dismissToast(toast);
    container.appendChild(toast);
    setTimeout(() => dismissToast(toast), 5000);
};

function dismissToast(el) {
    el.style.transition = "opacity .35s ease, transform .35s ease";
    el.style.opacity = "0";
    el.style.transform = "translateX(110%)";
    setTimeout(() => el.remove(), 370);
}

// ── DOM READY ────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {

    // Dark mode toggle
    const darkBtn = document.getElementById("dark-toggle");
    if (darkBtn) {
        darkBtn.addEventListener("click", () => {
            const current = document.documentElement.getAttribute("data-theme");
            applyTheme(current === "dark" ? "light" : "dark");
        });
    }

    // Auto-dismiss server-rendered toasts
    document.querySelectorAll(".toast").forEach((el) => {
        setTimeout(() => dismissToast(el), 4500);
    });

    // ── LIVE CLOCK ──────────────────────────────────────
    const clock = document.getElementById("live-clock");
    function tick() {
        if (!clock) return;
        const now = new Date();
        const pad = n => String(n).padStart(2, "0");
        clock.textContent = `🕐 ${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    }
    tick();
    setInterval(tick, 1000);

    // ── HAMBURGER ────────────────────────────────────────
    const navToggle = document.getElementById("nav-toggle");
    const navLinks  = document.getElementById("nav-links");
    if (navToggle && navLinks) {
        navToggle.addEventListener("click", () => {
            const open = navLinks.classList.toggle("open");
            navToggle.classList.toggle("open", open);
            navToggle.setAttribute("aria-label", open ? "Menu sluiten" : "Menu openen");
        });
        // Close on outside click
        document.addEventListener("click", (e) => {
            if (!navToggle.contains(e.target) && !navLinks.contains(e.target)) {
                navLinks.classList.remove("open");
                navToggle.classList.remove("open");
            }
        });
    }

    // ── CONFIRM DIALOGS (data-confirm attribute) ─────────
    document.addEventListener("click", (e) => {
        const el = e.target.closest("[data-confirm]");
        if (!el) return;
        const msg = el.getAttribute("data-confirm");
        if (msg && !confirm(msg)) e.preventDefault();
    });

    // ── CHAIR FILTER ─────────────────────────────────────
    const filterBtns = document.querySelectorAll(".filter-btn");
    const chairGrid  = document.getElementById("chair-grid");

    filterBtns.forEach((btn) => {
        btn.addEventListener("click", () => {
            filterBtns.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            const filter = btn.dataset.filter;

            chairGrid?.querySelectorAll(".chair-card").forEach((card) => {
                const status = card.dataset.status;
                const show = filter === "all"
                    || status === filter
                    || (filter === "kapot" && (status === "kapot" || status === "in_reparatie"));
                card.classList.toggle("hidden", !show);
            });
        });
    });

    // ── LIVE POLLING (every 20s on index page) ───────────
    if (chairGrid) {
        setInterval(async () => {
            try {
                const [cr, sr] = await Promise.all([fetch("/api/chairs"), fetch("/api/stats")]);
                const chairs = await cr.json();
                const stats  = await sr.json();

                // If any status changed → reload for updated buttons/renter info
                for (const { id, status } of chairs) {
                    const card = document.querySelector(`.chair-card[data-id="${id}"]`);
                    if (card && card.dataset.status !== status) {
                        window.location.reload();
                        return;
                    }
                }

                // Update counters
                ["vrij", "bezet", "kapot"].forEach(s => {
                    const el = document.getElementById(`stat-${s}`);
                    if (el) el.textContent = stats[s];
                });
            } catch { /* ignore network errors */ }
        }, 20000);
    }

    // ── BROKEN MODAL ─────────────────────────────────────
    const modal      = document.getElementById("broken-modal");
    const brokenForm = document.getElementById("broken-form");
    const modalChair = document.getElementById("modal-chair-num");

    window.openBrokenModal = function(chairId) {
        if (!modal) return;
        modalChair.textContent = chairId;
        brokenForm.action = `/broken/${chairId}`;
        modal.removeAttribute("hidden");
        document.getElementById("reason")?.focus();
    };

    window.closeBrokenModal = function() {
        modal?.setAttribute("hidden", "");
        if (brokenForm) brokenForm.reset();
    };

    // Close modal on overlay click
    modal?.addEventListener("click", (e) => {
        if (e.target === modal) closeBrokenModal();
    });

    // Close modal on Escape
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeBrokenModal();
    });

    console.log("🏖️ StrandStoelen JS geladen.");
});