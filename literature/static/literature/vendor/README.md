# Vendored third-party assets

These files are checked in (not built or fetched at deploy time) so the site
can serve them from its own origin and the Content-Security-Policy can keep
`script-src 'self'` — i.e. **no `cdn.jsdelivr.net` allowance** (issue #79).
Self-hosting also removes the runtime dependency on a third-party CDN.

| File | Library | Version | Source URL | SHA-256 |
| --- | --- | --- | --- | --- |
| `tex-mml-svg.js` | MathJax | 3.2.2 | `https://cdn.jsdelivr.net/npm/mathjax@3.2.2/es5/tex-mml-svg.js` | `1f17a7ed95ff4a4b27d16bf0fb5f80b915686ee8673e82983a2876ecf8cb9fae` |
| `echarts.min.js` | Apache ECharts | 5.5.1 | `https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js` | `e84270bd0cd5bdf60fefc26d00c2a391cb2e81f4d26a7a9ee16185a54773a3cf` |

## Why the MathJax **SVG** bundle (and a v2 → v3 bump)

MathJax **2.7.9** (the previous CDN pin) cannot be vendored as a single file:
`MathJax.js` lazy-loads its config, extensions, and font data at runtime from
whatever directory it lives in — the full npm package is ~63 MB of
multi-format fonts. Self-hosting it properly means checking in that whole
tree.

MathJax **3.2.2**'s `tex-mml-svg.js` is a single ~2 MB bundle with every glyph
embedded as an SVG path, so it fetches **zero** extra files at runtime — no
web fonts, no `@font-face`. That makes self-hosting trivial and keeps the CSP
tight (no `font-src` widening for math). Inline `\(...\)` and display
`\[...\]` / `$$...$$` delimiters are unchanged from the v2 setup; rendering
output is visually equivalent (crisp SVG glyphs).

## A note on the `cdn.jsdelivr.net` strings inside `tex-mml-svg.js`

The MathJax bundle embeds two `cdn.jsdelivr.net` URLs for the Speech Rule
Engine's accessibility "mathmaps" (used by the opt-in MathJax *Explorer* /
screen-reader menu). They are **not** fetched during normal rendering — the
SVG bundle preloads everything it needs and makes zero network requests to
typeset math. They would only be requested if a visitor manually enabled the
Explorer from MathJax's context menu, and our `connect-src 'self'` /
`script-src 'self'` CSP blocks them, so that feature degrades gracefully
(math still renders; speech rules just don't load). No action needed.

## Refreshing / bumping a version

```bash
curl -fsSL -o literature/static/literature/vendor/tex-mml-svg.js \
    https://cdn.jsdelivr.net/npm/mathjax@<VER>/es5/tex-mml-svg.js
curl -fsSL -o literature/static/literature/vendor/echarts.min.js \
    https://cdn.jsdelivr.net/npm/echarts@<VER>/dist/echarts.min.js
# then update the version + SHA-256 columns above:
sha256sum literature/static/literature/vendor/*.js
```

Verify in a browser afterwards: the admin console must show **no** CSP
violations, math in an abstract renders, and a tag/author page sparkline draws.
