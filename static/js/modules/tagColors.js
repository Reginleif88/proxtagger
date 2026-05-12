/**
 * Tag color helpers.
 *
 * Reads the cluster-wide override map from window.PROXTAGGER_TAG_COLORS
 * (injected server-side) and falls back to a deterministic algorithm copied
 * from Proxmox's widget-toolkit so chips look identical to the Proxmox UI
 * for tags without an override.
 *
 * Source for the derived algorithm:
 *   proxmox-widget-toolkit / src/Utils.js
 *   functions: stringToRGB, getTextContrastClass.
 */

const overrides = () => (window.PROXTAGGER_TAG_COLORS || {});

/**
 * Java-style string hash (`hash * 31 + char`) with the same `+ "prox"` salt
 * Proxmox uses to spread short strings.
 */
function stringHash(s) {
    let hash = 0;
    if (!s) return hash;
    const salted = s + "prox";
    for (let i = 0; i < salted.length; i++) {
        hash = salted.charCodeAt(i) + ((hash << 5) - hash);
        hash = hash & hash; // coerce to 32-bit int
    }
    return hash;
}

/** Return [r, g, b] in 0..255 floats, matching widget-toolkit stringToRGB. */
function stringToRGB(s) {
    const hash = stringHash(s);
    const alpha = 0.7;
    const bg = 255;
    return [
        (hash & 255) * alpha + bg * (1 - alpha),
        ((hash >> 8) & 255) * alpha + bg * (1 - alpha),
        ((hash >> 16) & 255) * alpha + bg * (1 - alpha),
    ];
}

/** Return 'light' (use white text) or 'dark' (use black text), matching widget-toolkit. */
function getTextContrastClass(rgb) {
    const blkThrs = 0.022;
    const blkClmp = 1.414;

    let r = (rgb[0] / 255) ** 2.4;
    let g = (rgb[1] / 255) ** 2.4;
    let b = (rgb[2] / 255) ** 2.4;

    let bg = r * 0.2126729 + g * 0.7151522 + b * 0.072175;
    bg = bg > blkThrs ? bg : bg + (blkThrs - bg) ** blkClmp;

    const contrastLight = bg ** 0.65 - 1;
    const contrastDark = bg ** 0.56 - 0.046134502;

    return Math.abs(contrastLight) >= Math.abs(contrastDark) ? 'light' : 'dark';
}

function rgbToHex(rgb) {
    return rgb
        .map(c => {
            const n = Math.max(0, Math.min(255, Math.round(c)));
            return n.toString(16).padStart(2, '0');
        })
        .join('');
}

function pickFgFromBgHex(bgHex) {
    const r = parseInt(bgHex.slice(0, 2), 16);
    const g = parseInt(bgHex.slice(2, 4), 16);
    const b = parseInt(bgHex.slice(4, 6), 16);
    return getTextContrastClass([r, g, b]) === 'light' ? 'ffffff' : '000000';
}

/** Compute a deterministic color for a tag with no explicit override. */
export function deriveColor(tag) {
    const rgb = stringToRGB(tag || '');
    const bg = rgbToHex(rgb);
    const fg = getTextContrastClass(rgb) === 'light' ? 'ffffff' : '000000';
    return { bg, fg, source: 'derived' };
}

/**
 * Return ``{bg, fg, source}`` for a tag.
 * source is 'override' if set in the cluster color-map, else 'derived'.
 * bg/fg are 6-digit hex strings (no leading '#').
 */
export function getTagColor(tag) {
    const map = overrides();
    const entry = map[tag];
    if (entry && entry.bg) {
        const bg = String(entry.bg).replace(/^#/, '').toLowerCase();
        const fgRaw = entry.fg ? String(entry.fg).replace(/^#/, '').toLowerCase() : null;
        const fg = fgRaw || pickFgFromBgHex(bg);
        return { bg, fg, source: 'override' };
    }
    return deriveColor(tag);
}

/**
 * Apply a tag's color to a chip element. Strips any Bootstrap bg-* utility
 * (which uses !important) and sets inline styles instead.
 */
export function applyTagColor(el, tag) {
    const { bg, fg } = getTagColor(tag);
    el.classList.remove(
        'bg-primary', 'bg-secondary', 'bg-success', 'bg-danger',
        'bg-warning', 'bg-info', 'bg-light', 'bg-dark'
    );
    el.style.backgroundColor = '#' + bg;
    el.style.color = '#' + fg;
}

/** CSS classes for a Bootstrap close button matching the chip's foreground. */
export function closeBtnClass(fg) {
    return fg === 'ffffff' ? 'btn-close btn-close-white' : 'btn-close';
}
