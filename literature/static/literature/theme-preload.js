// Early FOUC mitigation — runs synchronously in <head> before any
// stylesheet/body render so the requested theme is set before paint.
// Issue #80: extracted from the inline <script> in templates/base.html
// so the CSP can drop 'unsafe-inline' from script-src.
(function () {
    try {
        var t = localStorage.getItem('literature-theme');
        if (t === 'light' || t === 'dark') {
            document.documentElement.setAttribute('data-theme', t);
        }
    } catch (e) {}
})();
