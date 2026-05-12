/**
 * Tag Colors management page controller.
 *
 * Renders one row per known tag (existing tags + any tags that have an
 * override but no longer appear on a VM, so stale overrides can be cleaned
 * up). Tracks dirty state, posts the full color map on Save, refreshes
 * window.PROXTAGGER_TAG_COLORS on success, and re-renders rows in place.
 */

import { showToast, escapeHtml } from './utils.js';
import { getTagColor, deriveColor, applyTagColor, closeBtnClass } from './tagColors.js';

let allTags = [];
// Working copy of the override map. Entries here that match the deterministic
// derived color are still treated as "override" (the user may want them
// pinned). Removing a row deletes the entry entirely.
let workingMap = {};
let savedMap = {};

function isDirty() {
    if (Object.keys(workingMap).length !== Object.keys(savedMap).length) return true;
    for (const k of Object.keys(workingMap)) {
        const a = workingMap[k], b = savedMap[k];
        if (!b) return true;
        if (a.bg !== b.bg || (a.fg || null) !== (b.fg || null)) return true;
    }
    return false;
}

function setSaveButtonState() {
    const btn = document.getElementById('saveColorsBtn');
    if (!btn) return;
    btn.disabled = !isDirty();
}

function showStatus(kind, message) {
    const el = document.getElementById('saveStatus');
    if (!el) return;
    el.className = `alert alert-${kind}`;
    el.textContent = message;
    el.classList.remove('d-none');
}

function hideStatus() {
    const el = document.getElementById('saveStatus');
    if (el) el.classList.add('d-none');
}

function renderPreview(tag, td) {
    const chip = document.createElement('span');
    chip.className = 'badge tag-chip';
    chip.textContent = tag;
    applyTagColor(chip, tag);
    td.innerHTML = '';
    td.appendChild(chip);
}

function rowFor(tag) {
    const tr = document.createElement('tr');
    tr.dataset.tag = tag;

    const tagTd = document.createElement('td');
    tagTd.innerHTML = `<code>${escapeHtml(tag)}</code>`;

    const previewTd = document.createElement('td');

    const bgTd = document.createElement('td');
    const bgInput = document.createElement('input');
    bgInput.type = 'color';
    bgInput.className = 'form-control form-control-color';
    bgInput.title = `Background for "${tag}"`;
    bgTd.appendChild(bgInput);

    const fgTd = document.createElement('td');
    const fgInput = document.createElement('input');
    fgInput.type = 'color';
    fgInput.className = 'form-control form-control-color';
    fgInput.title = `Text color for "${tag}"`;
    fgTd.appendChild(fgInput);

    const sourceTd = document.createElement('td');
    const sourceBadge = document.createElement('span');
    sourceBadge.className = 'badge';
    sourceTd.appendChild(sourceBadge);

    const resetTd = document.createElement('td');
    resetTd.className = 'text-end pe-3';
    const resetBtn = document.createElement('button');
    resetBtn.type = 'button';
    resetBtn.className = 'btn btn-sm btn-outline-secondary';
    resetBtn.title = 'Remove override and use Proxmox default color';
    resetBtn.innerHTML = '<i class="bi bi-arrow-counterclockwise"></i>';
    resetTd.appendChild(resetBtn);

    tr.appendChild(tagTd);
    tr.appendChild(previewTd);
    tr.appendChild(bgTd);
    tr.appendChild(fgTd);
    tr.appendChild(sourceTd);
    tr.appendChild(resetTd);

    function syncControls() {
        const c = getTagColor(tag);
        bgInput.value = '#' + c.bg;
        fgInput.value = '#' + c.fg;
        if (c.source === 'override') {
            sourceBadge.className = 'badge bg-info text-dark';
            sourceBadge.textContent = 'override';
            resetBtn.disabled = false;
        } else {
            sourceBadge.className = 'badge bg-light text-dark border';
            sourceBadge.textContent = 'derived';
            resetBtn.disabled = true;
        }
        renderPreview(tag, previewTd);
    }

    function commit(bgHex, fgHex) {
        workingMap[tag] = { bg: bgHex.replace(/^#/, '').toLowerCase(),
                            fg: fgHex.replace(/^#/, '').toLowerCase() };
        // Update the live overrides map so getTagColor sees it for preview.
        window.PROXTAGGER_TAG_COLORS = workingMap;
        syncControls();
        setSaveButtonState();
        hideStatus();
    }

    bgInput.addEventListener('input', () => commit(bgInput.value, fgInput.value));
    fgInput.addEventListener('input', () => commit(bgInput.value, fgInput.value));

    resetBtn.addEventListener('click', () => {
        delete workingMap[tag];
        window.PROXTAGGER_TAG_COLORS = workingMap;
        syncControls();
        setSaveButtonState();
        hideStatus();
    });

    syncControls();
    return tr;
}

function renderTable() {
    const tbody = document.getElementById('tagColorsTbody');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (!allTags.length) {
        const tr = document.createElement('tr');
        tr.innerHTML = '<td colspan="6" class="text-center text-muted py-4">No tags found.</td>';
        tbody.appendChild(tr);
        return;
    }
    allTags.forEach(tag => tbody.appendChild(rowFor(tag)));
}

async function save() {
    const btn = document.getElementById('saveColorsBtn');
    btn.disabled = true;
    showStatus('info', 'Saving…');
    try {
        const resp = await fetch('/api/tag-colors', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ colors: workingMap })
        });
        const data = await resp.json().catch(() => ({}));
        if (resp.ok && data.success) {
            savedMap = JSON.parse(JSON.stringify(data.colors || {}));
            workingMap = JSON.parse(JSON.stringify(savedMap));
            window.PROXTAGGER_TAG_COLORS = workingMap;
            renderTable();
            setSaveButtonState();
            showStatus('success', 'Tag colors saved.');
            showToast('Tag colors saved', 'success');
        } else if (resp.status === 403 || data.code === 'permission_denied') {
            document.getElementById('permissionAlert').classList.remove('d-none');
            showStatus('warning', data.error || 'Permission denied.');
        } else {
            showStatus('danger', data.error || `Save failed (HTTP ${resp.status}).`);
        }
    } catch (e) {
        showStatus('danger', `Save failed: ${e.message || e}`);
    } finally {
        setSaveButtonState();
    }
}

function resetAll() {
    if (!Object.keys(workingMap).length) return;
    workingMap = {};
    window.PROXTAGGER_TAG_COLORS = workingMap;
    renderTable();
    setSaveButtonState();
    hideStatus();
}

function init() {
    if (!document.getElementById('tagColorsTable')) return;
    allTags = (window.PROXTAGGER_ALL_TAGS || []).slice();
    savedMap = JSON.parse(JSON.stringify(window.PROXTAGGER_TAG_COLORS || {}));
    workingMap = JSON.parse(JSON.stringify(savedMap));

    renderTable();
    setSaveButtonState();

    document.getElementById('saveColorsBtn').addEventListener('click', save);
    document.getElementById('resetAllBtn').addEventListener('click', resetAll);

    window.addEventListener('beforeunload', (e) => {
        if (isDirty()) {
            e.preventDefault();
            e.returnValue = '';
        }
    });
}

document.addEventListener('DOMContentLoaded', init);
