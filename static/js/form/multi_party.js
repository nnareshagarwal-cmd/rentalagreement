/**
 * multi_party.js — Dynamic "+ Add Owner" & "+ Add Tenant" & "🗑️ Remove" Controls
 * ==============================================================================
 * Directly manages section visibility via DOM. No circular imports.
 */

import { triggerDebouncedPreview } from '../preview.js';
import { syncPreviewToField } from '../preview_sync.js';

let currentOwnerCount = 1;
let currentTenantCount = 1;

function isLeaveLicense() {
    const path = window.location.pathname.toLowerCase();
    return path.includes('leave') || path.includes('license');
}

export function getOwnerCount() { return currentOwnerCount; }
export function getTenantCount() { return currentTenantCount; }

export function isSectionAllowedByMultiParty(sectionKey) {
    if (!sectionKey || typeof sectionKey !== 'string') return true;
    if (sectionKey.startsWith('owner_')) {
        const num = parseInt(sectionKey.replace('owner_', ''), 10);
        return !isNaN(num) ? num <= currentOwnerCount : true;
    }
    if (sectionKey.startsWith('tenant_')) {
        const num = parseInt(sectionKey.replace('tenant_', ''), 10);
        return !isNaN(num) ? num <= currentTenantCount : true;
    }
    if (sectionKey === 'bachelor') {
        const sel = document.getElementById('tenant_type');
        return sel ? (sel.value || '').trim() === 'Bachelor' : false;
    }
    return true;
}

/** Directly show/hide a section's header + content by data-section-key */
function setSectionVisible(sectionKey, visible) {
    if (!visible) {
        const header = document.querySelector(`.section-header[data-section-key="${sectionKey}"]`);
        const content = document.querySelector(`.section-content[data-section-key="${sectionKey}"]`);
        if (header) header.style.setProperty('display', 'none', 'important');
        if (content) content.style.setProperty('display', 'none', 'important');
    }
    document.dispatchEvent(new CustomEvent('multiPartyChanged'));
}

function clearPartySectionFields(prefix, index) {
    const content = document.querySelector(`.section-content[data-section-key="${prefix}_${index}"]`);
    if (!content) return;
    content.querySelectorAll('input, select, textarea').forEach(input => {
        if (input.type === 'checkbox' || input.type === 'radio') {
            input.checked = false;
        } else {
            input.value = '';
        }
    });
}

export function setOwnerCount(cnt) {
    currentOwnerCount = Math.max(1, Math.min(6, parseInt(cnt || '1', 10)));
    applyOwnerVisibility();
}

export function setTenantCount(cnt) {
    currentTenantCount = Math.max(1, Math.min(6, parseInt(cnt || '1', 10)));
    applyTenantVisibility();
}

/** Apply visibility: show owners 1..count, hide count+1..6. Move Add button. */
function applyOwnerVisibility() {
    const countInput = document.getElementById('owner_count');
    if (countInput) {
        countInput.value = String(currentOwnerCount);
        countInput.dispatchEvent(new Event('change', { bubbles: true }));
    }

    for (let i = 2; i <= 6; i++) {
        setSectionVisible(`owner_${i}`, i <= currentOwnerCount);
    }

    // Position the Add button inside the last visible owner's content
    const ownerBtnLabel = isLeaveLicense() ? '➕ Add Licensor' : '➕ Add Owner';
    let addBtnContainer = document.getElementById('addOwnerBtnContainer');

    if (!addBtnContainer) {
        addBtnContainer = document.createElement('div');
        addBtnContainer.id = 'addOwnerBtnContainer';
        addBtnContainer.style.cssText = 'grid-column: 1 / -1; display: flex; justify-content: flex-end; margin-top: 10px;';
        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'add-party-btn';
        addBtn.innerHTML = ownerBtnLabel;
        addBtn.style.cssText = 'display: inline-flex; align-items: center; gap: 8px; background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); color: white; border: none; padding: 10px 18px; border-radius: 8px; font-size: 13px; font-weight: 700; cursor: pointer; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25); transition: all 0.2s ease;';
        addBtn.addEventListener('click', () => {
            if (currentOwnerCount < 6) {
                currentOwnerCount++;
                applyOwnerVisibility();
                triggerDebouncedPreview();
            }
        });
        addBtnContainer.appendChild(addBtn);
    } else {
        const addBtn = addBtnContainer.querySelector('.add-party-btn');
        if (addBtn) addBtn.innerHTML = ownerBtnLabel;
    }

    if (currentOwnerCount >= 6) {
        addBtnContainer.style.display = 'none';
    } else {
        addBtnContainer.style.display = 'flex';
    }

    const lastKey = `owner_${currentOwnerCount}`;
    const lastContent = document.querySelector(`.section-content[data-section-key="${lastKey}"]`);
    if (lastContent) lastContent.appendChild(addBtnContainer);

    updatePartyNavigation('owner');
    setupPartyObserver();

    // Notify wizard to re-sync (non-circular: just a DOM event)
    document.dispatchEvent(new CustomEvent('multiPartyChanged'));
}

/** Apply visibility: show tenants 1..count, hide count+1..6. Move Add button. */
function applyTenantVisibility() {
    const countInput = document.getElementById('tenant_count');
    if (countInput) {
        countInput.value = String(currentTenantCount);
        countInput.dispatchEvent(new Event('change', { bubbles: true }));
    }

    for (let i = 2; i <= 6; i++) {
        setSectionVisible(`tenant_${i}`, i <= currentTenantCount);
    }

    const tenantBtnLabel = isLeaveLicense() ? '➕ Add Licensee' : '➕ Add Tenant';
    let addBtnContainer = document.getElementById('addTenantBtnContainer');

    if (!addBtnContainer) {
        addBtnContainer = document.createElement('div');
        addBtnContainer.id = 'addTenantBtnContainer';
        addBtnContainer.style.cssText = 'grid-column: 1 / -1; display: flex; justify-content: flex-end; margin-top: 10px;';
        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'add-party-btn';
        addBtn.innerHTML = tenantBtnLabel;
        addBtn.style.cssText = 'display: inline-flex; align-items: center; gap: 8px; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; border: none; padding: 10px 18px; border-radius: 8px; font-size: 13px; font-weight: 700; cursor: pointer; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25); transition: all 0.2s ease;';
        addBtn.addEventListener('click', () => {
            if (currentTenantCount < 6) {
                currentTenantCount++;
                applyTenantVisibility();
                triggerDebouncedPreview();
            }
        });
        addBtnContainer.appendChild(addBtn);
    } else {
        const addBtn = addBtnContainer.querySelector('.add-party-btn');
        if (addBtn) addBtn.innerHTML = tenantBtnLabel;
    }

    if (currentTenantCount >= 6) {
        addBtnContainer.style.display = 'none';
    } else {
        addBtnContainer.style.display = 'flex';
    }

    const lastKey = `tenant_${currentTenantCount}`;
    const lastContent = document.querySelector(`.section-content[data-section-key="${lastKey}"]`);
    if (lastContent) lastContent.appendChild(addBtnContainer);

    updatePartyNavigation('tenant');
    setupPartyObserver();

    document.dispatchEvent(new CustomEvent('multiPartyChanged'));
}

export function setupMultiPartyControls() {
    // Attach Remove buttons to owner 2-6 headers
    for (let i = 2; i <= 6; i++) {
        const header = document.querySelector(`.section-header[data-section-key="owner_${i}"]`);
        if (header && !header.querySelector('.remove-party-btn')) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'remove-party-btn';
            btn.innerHTML = '🗑️ Remove';
            btn.style.cssText = 'margin-left: auto; background: #fee2e2; color: #dc2626; border: 1px solid #fca5a5; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; cursor: pointer; z-index: 10; position: relative;';
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                // Clear fields from this index onward and reduce count
                for (let j = i; j <= 6; j++) clearPartySectionFields('owner', j);
                currentOwnerCount = Math.max(1, i - 1);
                applyOwnerVisibility();
                triggerDebouncedPreview();
            });
            header.appendChild(btn);
        }
    }

    // Attach Remove buttons to tenant 2-6 headers
    for (let i = 2; i <= 6; i++) {
        const header = document.querySelector(`.section-header[data-section-key="tenant_${i}"]`);
        if (header && !header.querySelector('.remove-party-btn')) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'remove-party-btn';
            btn.innerHTML = '🗑️ Remove';
            btn.style.cssText = 'margin-left: auto; background: #fee2e2; color: #dc2626; border: 1px solid #fca5a5; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; cursor: pointer; z-index: 10; position: relative;';
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
                for (let j = i; j <= 6; j++) clearPartySectionFields('tenant', j);
                currentTenantCount = Math.max(1, i - 1);
                applyTenantVisibility();
                triggerDebouncedPreview();
            });
            header.appendChild(btn);
        }
    }

    // Initial state: show only 1 owner and 1 tenant
    applyOwnerVisibility();
    applyTenantVisibility();
}

export function updateBachelorSectionVisibility() {
    const allowed = isSectionAllowedByMultiParty('bachelor');
    setSectionVisible('bachelor', allowed);
    document.dispatchEvent(new CustomEvent('multiPartyChanged'));
}

let partyObserver = null;
let isProgrammaticScrolling = false;
let scrollGuardTimeout = null;

/** Keep a party pill visible without allowing the browser to move the form's
 * vertical scroll container. `Element.scrollIntoView()` can scroll every
 * scrollable ancestor, which caused the editor to jump upward. */
function scrollPartyPillHorizontally(navContainer, pill) {
    if (!navContainer || !pill) return;

    const navRect = navContainer.getBoundingClientRect();
    const pillRect = pill.getBoundingClientRect();
    const pillCenter = pillRect.left - navRect.left + navContainer.scrollLeft + (pillRect.width / 2);
    const targetLeft = Math.max(0, pillCenter - (navContainer.clientWidth / 2));

    navContainer.scrollTo({ left: targetLeft, behavior: 'smooth' });
}

function setupPartyObserver() {
    if (partyObserver) {
        partyObserver.disconnect();
    }

    const partyHeaders = document.querySelectorAll('.section-header[data-section-key^="owner_"], .section-header[data-section-key^="tenant_"]');
    if (!partyHeaders.length) return;

    const formContainer = document.querySelector('.container');

    partyObserver = new IntersectionObserver((entries) => {
        if (isProgrammaticScrolling) return;

        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const secKey = entry.target.dataset.sectionKey;
                if (!secKey) return;
                const parts = secKey.split('_');
                const type = parts[0];
                const index = parts[1];

                const navId = type === 'owner' ? 'ownerPartyNav' : 'tenantPartyNav';
                const navContainer = document.getElementById(navId);
                if (navContainer) {
                    const pill = navContainer.querySelector(`.sk-party-nav-pill[data-party-index="${index}"]`);
                    if (pill && !pill.classList.contains('active')) {
                        navContainer.querySelectorAll('.sk-party-nav-pill').forEach(p => p.classList.remove('active'));
                        pill.classList.add('active');
                        scrollPartyPillHorizontally(navContainer, pill);
                    }
                }
            }
        });
    }, {
        root: formContainer || null,
        rootMargin: '-60px 0px -60% 0px',
        threshold: 0.1
    });

    partyHeaders.forEach(header => partyObserver.observe(header));
}

export function updatePartyNavigation(type) {
    const isOwner = type === 'owner';
    const count = isOwner ? currentOwnerCount : currentTenantCount;
    const navId = isOwner ? 'ownerPartyNav' : 'tenantPartyNav';
    const firstSectionKey = isOwner ? 'owner_1' : 'tenant_1';
    const singularLabel = isLeaveLicense() ? (isOwner ? 'Licensor' : 'Licensee') : (isOwner ? 'Owner' : 'Tenant');

    let navContainer = document.getElementById(navId);

    const firstHeader = document.querySelector(`.section-header[data-section-key="${firstSectionKey}"]`);
    if (!firstHeader) return;

    if (count <= 1) {
        if (navContainer) navContainer.style.setProperty('display', 'none', 'important');
        return;
    }

    if (!navContainer) {
        navContainer = document.createElement('div');
        navContainer.id = navId;
        navContainer.className = 'sk-party-nav-container';
        // Keep party switching beside the section title so it remains available
        // while the user moves between long party forms.
        firstHeader.appendChild(navContainer);
    }

    // Re-parent navigators created by earlier versions of this UI.
    if (navContainer.parentNode !== firstHeader) firstHeader.appendChild(navContainer);
    firstHeader.classList.add('sk-party-nav-host');

    // The wizard controls section visibility with an !important display rule.
    // Use the computed value and an equally specific inline rule so this bar is
    // present only while its corresponding party step is visible.
    const firstHeaderVisible = window.getComputedStyle(firstHeader).display !== 'none';
    navContainer.style.setProperty(
        'display',
        firstHeaderVisible ? 'inline-flex' : 'none',
        'important'
    );

    navContainer.innerHTML = '';

    for (let i = 1; i <= count; i++) {
        const pill = document.createElement('button');
        pill.type = 'button';
        pill.className = 'sk-party-nav-pill' + (i === 1 ? ' active' : '');
        pill.dataset.partyType = type;
        pill.dataset.partyIndex = String(i);
        pill.textContent = `${singularLabel} ${i}`;

        pill.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            const targetKey = `${type}_${i}`;
            const targetHeader = document.querySelector(`.section-header[data-section-key="${targetKey}"]`);
            const formContainer = document.querySelector('.container') || document.body;

            if (targetHeader) {
                // Instantly mark programmatic scrolling so IntersectionObserver won't override pill state
                isProgrammaticScrolling = true;
                clearTimeout(scrollGuardTimeout);
                scrollGuardTimeout = setTimeout(() => {
                    isProgrammaticScrolling = false;
                }, 1200);

                if (targetHeader.classList.contains('collapsed')) {
                    targetHeader.click();
                }

                // Immediately update active pill UI
                navContainer.querySelectorAll('.sk-party-nav-pill').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');

                // Scroll the actual left-hand form scroller. The page itself is
                // not the scroll container in the split-preview layout.
                requestAnimationFrame(() => {
                    const stickyHeader = document.getElementById('stickyWorkspaceHeader');
                    const stickyHeight = stickyHeader ? stickyHeader.getBoundingClientRect().height : 0;
                    const headerRect = targetHeader.getBoundingClientRect();
                    const containerRect = formContainer.getBoundingClientRect();
                    const relativeTop = headerRect.top - containerRect.top + formContainer.scrollTop;

                    formContainer.scrollTo({
                        top: Math.max(0, relativeTop - stickyHeight - 15),
                        behavior: 'smooth'
                    });
                });

                // Keep the live document aligned with the selected tenant too.
                const targetField = document.getElementById(`${type}${i}_name`);
                if (targetField) syncPreviewToField(targetField);

                // Scroll only the pill row horizontally; never move the form vertically.
                scrollPartyPillHorizontally(navContainer, pill);
            }
        });

        navContainer.appendChild(pill);
    }
}
