/**
 * preview.js — Debounced Preview Engine, Expand/Collapse & Hide Controls
 * =======================================================================
 */

let previewDebounceTimer = null;

export function buildFormDataPayload() {
    const form = document.getElementById('agreementForm');
    if (!form) return {};
    const formData = new FormData(form);
    const data = {};
    for (let [k, v] of formData.entries()) {
        data[k] = v;
    }

    const path = window.location.pathname.toLowerCase();
    const isLeaveLicense = path.includes('leave') || path.includes('license');
    data['agreement_type'] = isLeaveLicense ? 'Leave&License' : 'simple_rental';

    return data;
}

import { syncPreviewToField } from './preview_sync.js';

export async function refreshLivePreview(targetField = null) {
    const payload = buildFormDataPayload();
    try {
        const res = await fetch('/api/rental/preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            const result = await res.json();
            const previewEl = document.getElementById('previewContent');
            if (previewEl && result.html) {
                previewEl.innerHTML = result.html;

                // Sync preview to active/target field after HTML update
                const fieldToSync = targetField || document.activeElement;
                if (fieldToSync && (fieldToSync.tagName === 'INPUT' || fieldToSync.tagName === 'TEXTAREA' || fieldToSync.tagName === 'SELECT')) {
                    syncPreviewToField(fieldToSync);
                }
            }
        }
    } catch (e) {
        console.warn('[Preview] Live refresh error:', e);
    }
}

export function triggerDebouncedPreview(targetField = null) {
    clearTimeout(previewDebounceTimer);
    previewDebounceTimer = setTimeout(() => refreshLivePreview(targetField), 300);
}

export function setupPreviewControls() {
    const toggleExpandPreviewBtn = document.getElementById('toggleExpandPreviewBtn');
    const toggleHidePreviewBtn = document.getElementById('toggleHidePreviewBtn');
    const headerTogglePreviewBtn = document.getElementById('headerTogglePreviewBtn');

    if (toggleExpandPreviewBtn) {
        toggleExpandPreviewBtn.addEventListener('click', () => {
            document.body.classList.toggle('preview-expanded');
            const expandText = document.getElementById('expandText');
            const expandIcon = document.getElementById('expandIcon');
            const isExpanded = document.body.classList.contains('preview-expanded');
            if (expandText) expandText.textContent = isExpanded ? 'Compress Document' : 'Expand Document';
            if (expandIcon) expandIcon.textContent = isExpanded ? '▶' : '◀';
        });
    }

    const togglePreviewVisibility = () => {
        document.body.classList.toggle('preview-hidden');
        const isHidden = document.body.classList.contains('preview-hidden');
        document.body.dataset.userPreviewHidden = isHidden ? 'true' : 'false';
        if (headerTogglePreviewBtn) {
            headerTogglePreviewBtn.innerHTML = isHidden ? '<span>👁️</span> Preview' : '<span>✖</span> Hide Preview';
        }
    };

    if (toggleHidePreviewBtn) {
        toggleHidePreviewBtn.addEventListener('click', togglePreviewVisibility);
    }
    if (headerTogglePreviewBtn) {
        headerTogglePreviewBtn.addEventListener('click', togglePreviewVisibility);
    }
}
