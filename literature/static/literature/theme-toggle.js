// Theme-toggle button — light / dark / auto cycle, persisted in
// localStorage. Issue #80: extracted from the inline <script> in
// templates/base.html so the CSP can drop 'unsafe-inline' from
// script-src. The early FOUC-mitigating reader lives in
// theme-preload.js (loaded synchronously in <head>).
(function () {
    var KEY = 'literature-theme';
    var btn = document.getElementById('theme-toggle');
    if (!btn) return;
    var labelEl = btn.querySelector('.theme-toggle__label');
    function mode() {
        var t = null;
        try { t = localStorage.getItem(KEY); } catch (e) {}
        return (t === 'light' || t === 'dark') ? t : 'auto';
    }
    function render(m) {
        btn.setAttribute('data-mode', m);
        if (labelEl) labelEl.textContent = m.charAt(0).toUpperCase() + m.slice(1);
        btn.setAttribute('aria-label', 'Theme: ' + m + ' (click to change)');
    }
    function apply(m) {
        if (m === 'auto') {
            document.documentElement.removeAttribute('data-theme');
            try { localStorage.removeItem(KEY); } catch (e) {}
        } else {
            document.documentElement.setAttribute('data-theme', m);
            try { localStorage.setItem(KEY, m); } catch (e) {}
        }
        render(m);
    }
    render(mode());
    btn.addEventListener('click', function () {
        var order = ['light', 'dark', 'auto'];
        apply(order[(order.indexOf(mode()) + 1) % 3]);
    });
})();
