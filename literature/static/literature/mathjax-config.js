// MathJax 3 configuration. Must be assigned to window.MathJax BEFORE the
// vendored tex-mml-svg.js bundle loads.
//
// Issue #79: this config lives in its own static file (not an inline
// <script>) so the CSP can keep script-src 'self' — no 'unsafe-inline',
// no cdn.jsdelivr.net.
//
// The vendored bundle is the SVG-output build (tex-mml-svg.js), so every
// glyph ships as an embedded SVG path and no web fonts are fetched at
// runtime. Delimiters match the v2 setup and the \(...\) convention used
// throughout Item.abstract; single `$` is deliberately left disabled so
// currency amounts in an abstract aren't mis-parsed as math.
window.MathJax = {
    tex: {
        inlineMath: [["\\(", "\\)"]],
        displayMath: [["\\[", "\\]"], ["$$", "$$"]],
    },
    svg: { fontCache: "global" },
};
