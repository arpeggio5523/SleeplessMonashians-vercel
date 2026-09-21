// Regenerate src/dark.css from the colour classes used in src/.
// Run after adding a colour class that has no dark equivalent yet:
//     node scripts/gen-dark.cjs

// Generate dark-mode overrides for exactly the colour classes the UI uses.
const colors = require('tailwindcss/colors');
const fs = require('fs');
const path = require('path');
const SRC = path.join(__dirname, '..', 'src');
const walk = d => fs.readdirSync(d, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(d, e.name)) : /\.(jsx?|tsx?)$/.test(e.name) ? [path.join(d, e.name)] : []);
const RX = /\b(hover:|focus:|group-hover:|disabled:)?(bg|text|border|divide|ring|outline)-(white|black|(neutral|gray|slate|zinc|stone|amber|rose|red|emerald|green|blue|sky|indigo|yellow|orange)-[0-9]{2,3})(\/[0-9]{1,3})?\b/g;
const classes = [...new Set(walk(SRC).flatMap(f => fs.readFileSync(f, 'utf8').match(RX) || []))].sort();
const NEUTRAL = new Set(['neutral', 'gray', 'slate', 'zinc', 'stone']);
const hex2rgb = h => { const n = parseInt(h.slice(1), 16); return [n >> 16 & 255, n >> 8 & 255, n & 255]; };
const rgba = (h, a) => a >= 1 ? h : `rgba(${hex2rgb(h).join(', ')}, ${+a.toFixed(3)})`;

// Neutral surfaces invert; text lightens; borders darken.
const NBG = { white: 900, 50: 950, 100: 900, 200: 800, 300: 700, 400: 600, 500: 500, 600: 500, 700: 600, 800: 600, 900: 700, 950: 800 };
const NTXT = { 900: 100, 800: 200, 700: 300, 600: 400, 500: 400, 400: 500, 300: 600, 200: 700, 100: 800, 50: 900 };
const NBD = { 50: 900, 100: 800, 200: 800, 300: 700, 400: 600, 500: 500, 600: 500, 700: 600, 800: 700, 900: 700 };

function darkValue(prop, fam, shade, alpha) {
  if (fam === 'white') {
    if (prop === 'bg') return rgba(colors.neutral[900], alpha);
    if (prop === 'text') return null;                         // white text on solid buttons stays
    return rgba(colors.neutral[800], alpha);
  }
  if (fam === 'black') return prop === 'text' ? colors.neutral[100] : null;
  const pal = colors[fam];
  if (NEUTRAL.has(fam)) {
    if (prop === 'bg') return rgba(colors.neutral[NBG[shade]], alpha);
    if (prop === 'text') return rgba(colors.neutral[NTXT[shade]], alpha);
    return rgba(colors.neutral[NBD[shade]], alpha);
  }
  // Coloured: pale tints become translucent washes, dark ink becomes light
  // ink, solid fills (500+) are left as they are - they read fine on dark.
  if (prop === 'bg') {
    if (shade >= 500) return null;
    return rgba(pal[500], ({ 50: .10, 100: .16, 200: .26, 300: .34, 400: .45 }[shade]) * alpha);
  }
  if (prop === 'text') return rgba(pal[{ 900: 200, 800: 200, 700: 300, 600: 300, 500: 400, 400: 400, 300: 300, 200: 200, 100: 100, 50: 50 }[shade]], alpha);
  return rgba(pal[500], ({ 50: .20, 100: .28, 200: .38, 300: .5, 400: .6 }[shade] ?? 1) * alpha);
}

const esc = c => c.replace(/([:/])/g, '\\$1');
const PROP = { bg: 'background-color', text: 'color', border: 'border-color', ring: '--tw-ring-color', outline: 'outline-color', divide: 'border-color' };
const rules = [];
for (const c of classes) {
  const m = c.match(/^((?:hover|focus|group-hover|disabled):)?(bg|text|border|divide|ring|outline)-(white|black|[a-z]+)-?(\d{2,3})?(?:\/(\d{1,3}))?$/);
  if (!m) continue;
  const [, variant, prop, fam, shadeS, alphaS] = m;
  const shade = shadeS ? +shadeS : fam;
  const alpha = alphaS ? +alphaS / 100 : 1;
  const v = darkValue(prop, fam, shade === fam ? fam : +shade, alpha);
  if (!v) continue;
  let sel = `.${esc(c)}`;
  if (variant === 'hover:') sel += ':hover';
  if (variant === 'focus:') sel += ':focus';
  if (variant === 'disabled:') sel += ':disabled';
  if (variant === 'group-hover:') sel = `.group:hover ${sel}`;
  if (prop === 'divide') sel += ' > :not([hidden]) ~ :not([hidden])';
  rules.push(`html.dark ${sel} { ${PROP[prop]}: ${v}; }`);
}

const css = `/*
 * dark.css - dark theme, applied when <html> carries the "dark" class.
 *
 * GENERATED from the colour classes the components actually use, with values
 * taken from Tailwind's own palette. It remaps those classes rather than
 * adding dark: variants to every component, so no component markup changes.
 *
 * If a component starts using a colour class that isn't listed here, it
 * simply keeps its light value in dark mode - regenerate to cover it.
 */

html.dark { color-scheme: dark; }
html.dark body { background-color: ${colors.neutral[950]}; color: ${colors.neutral[100]}; }
html.dark ::selection { background-color: ${rgba(colors.blue[500], .35)}; }
html.dark ::placeholder { color: ${colors.neutral[500]}; }
html.dark .shadow-xs, html.dark .shadow-2xs, html.dark .shadow-sm, html.dark .shadow-md, html.dark .shadow-lg {
  --tw-shadow-color: rgba(0, 0, 0, 0.6);
}

${rules.join('\n')}
`;
fs.writeFileSync(path.join(SRC, 'dark.css'), css);
console.log(`${classes.length} classes in use -> ${rules.length} dark rules (${classes.length - rules.length} deliberately unchanged: solid fills and white text on them)`);
