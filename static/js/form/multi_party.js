/**
 * multi_party.js — Dynamic "+ Add Owner" & "+ Add Tenant" & "🗑️ Remove" Controls
 * ==============================================================================
 * Dynamically adjusts party labels based on Agreement Type:
 * - Simple Rental: "Add Owner" & "Add Tenant"
 * - Leave & License: "Add Licensor" & "Add Licensee"
 */

import { triggerDebouncedPreview } from '../preview.js';

let currentOwnerCount = 1;
let currentTenantCount = 1;

function isLeaveLicense() {
    const path = window.location.pathname.toLowerCase();
    return path.includes('leave') || path.includes('license');
}

export function setOwnerCount(cnt) {
    currentOwnerCount = Math.max(1, Math.min(6, parseInt(cnt || '1', 10)));
    updateOwnerVisibility();
}

export function setTenantCount(cnt) {
    currentTenantCount = Math.max(1, Math.min(6, parseInt(cnt || '1', 10)));
    updateTenantVisibility();
}

export function setupMultiPartyControls() {
    setupOwnerMultiParty();
    setupTenantMultiParty();
}

function setupOwnerMultiParty() {
    for (let i = 2; i <= 6; i++) {
        const header = document.querySelector(`.section-header[data-section-key="owner_${i}"]`);
        if (header && !header.querySelector('.remove-party-btn')) {
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'remove-party-btn';
            removeBtn.innerHTML = '🗑️ Remove';
            removeBtn.style.cssText = 'margin-left: auto; background: #fee2e2; color: #dc2626; border: 1px solid #fca5a5; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; cursor: pointer;';
            
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                removeOwner(i);
            });
            header.appendChild(removeBtn);
        }
    }

    updateOwnerVisibility();
}

function removeOwner(index) {
    if (currentOwnerCount >= index) {
        currentOwnerCount = index - 1;
        updateOwnerVisibility();
        triggerDebouncedPreview();
    }
}

function addOwner() {
    if (currentOwnerCount < 6) {
        currentOwnerCount++;
        updateOwnerVisibility();
        triggerDebouncedPreview();
    }
}

function updateOwnerVisibility() {
    const countInput = document.getElementById('owner_count');
    if (countInput) countInput.value = String(currentOwnerCount);

    for (let i = 2; i <= 6; i++) {
        const isVisible = i <= currentOwnerCount;
        const header = document.querySelector(`.section-header[data-section-key="owner_${i}"]`);
        const content = document.querySelector(`.section-content[data-section-key="owner_${i}"]`);

        if (header) header.style.display = isVisible ? 'flex' : 'none';
        if (content) {
            content.style.display = isVisible ? 'grid' : 'none';
            if (isVisible) {
                content.style.gridTemplateColumns = 'repeat(3, 1fr)';
                content.style.gap = '20px';
            }
        }
    }

    const lastActiveKey = currentOwnerCount === 1 ? 'owner_1' : `owner_${currentOwnerCount}`;
    const lastContent = document.querySelector(`.section-content[data-section-key="${lastActiveKey}"]`);

    let addBtnContainer = document.getElementById('addOwnerBtnContainer');
    const ownerBtnLabel = isLeaveLicense() ? '➕ Add Licensor' : '➕ Add Owner';

    if (!addBtnContainer) {
        addBtnContainer = document.createElement('div');
        addBtnContainer.id = 'addOwnerBtnContainer';
        addBtnContainer.style.cssText = 'grid-column: 1 / -1; display: flex; justify-content: flex-end; margin-top: 10px;';
        
        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'add-party-btn';
        addBtn.innerHTML = ownerBtnLabel;
        addBtn.style.cssText = 'display: inline-flex; align-items: center; gap: 8px; background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%); color: white; border: none; padding: 10px 18px; border-radius: 8px; font-size: 13px; font-weight: 700; cursor: pointer; box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25); transition: all 0.2s ease;';
        
        addBtn.addEventListener('click', addOwner);
        addBtnContainer.appendChild(addBtn);
    } else {
        const addBtn = addBtnContainer.querySelector('.add-party-btn');
        if (addBtn) addBtn.innerHTML = ownerBtnLabel;
    }

    if (currentOwnerCount >= 6) {
        addBtnContainer.style.display = 'none';
    } else {
        addBtnContainer.style.display = 'flex';
        if (lastContent) lastContent.appendChild(addBtnContainer);
    }
}

function setupTenantMultiParty() {
    for (let i = 2; i <= 6; i++) {
        const header = document.querySelector(`.section-header[data-section-key="tenant_${i}"]`);
        if (header && !header.querySelector('.remove-party-btn')) {
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'remove-party-btn';
            removeBtn.innerHTML = '🗑️ Remove';
            removeBtn.style.cssText = 'margin-left: auto; background: #fee2e2; color: #dc2626; border: 1px solid #fca5a5; padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 700; cursor: pointer;';
            
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                removeTenant(i);
            });
            header.appendChild(removeBtn);
        }
    }

    updateTenantVisibility();
}

function removeTenant(index) {
    if (currentTenantCount >= index) {
        currentTenantCount = index - 1;
        updateTenantVisibility();
        triggerDebouncedPreview();
    }
}

function addTenant() {
    if (currentTenantCount < 6) {
        currentTenantCount++;
        updateTenantVisibility();
        triggerDebouncedPreview();
    }
}

function updateTenantVisibility() {
    const countInput = document.getElementById('tenant_count');
    if (countInput) countInput.value = String(currentTenantCount);

    for (let i = 2; i <= 6; i++) {
        const isVisible = i <= currentTenantCount;
        const header = document.querySelector(`.section-header[data-section-key="tenant_${i}"]`);
        const content = document.querySelector(`.section-content[data-section-key="tenant_${i}"]`);

        if (header) header.style.display = isVisible ? 'flex' : 'none';
        if (content) {
            content.style.display = isVisible ? 'grid' : 'none';
            if (isVisible) {
                content.style.gridTemplateColumns = 'repeat(3, 1fr)';
                content.style.gap = '20px';
            }
        }
    }

    const lastActiveKey = currentTenantCount === 1 ? 'tenant_1' : `tenant_${currentTenantCount}`;
    const lastContent = document.querySelector(`.section-content[data-section-key="${lastActiveKey}"]`);

    let addBtnContainer = document.getElementById('addTenantBtnContainer');
    const tenantBtnLabel = isLeaveLicense() ? '➕ Add Licensee' : '➕ Add Tenant';

    if (!addBtnContainer) {
        addBtnContainer = document.createElement('div');
        addBtnContainer.id = 'addTenantBtnContainer';
        addBtnContainer.style.cssText = 'grid-column: 1 / -1; display: flex; justify-content: flex-end; margin-top: 10px;';
        
        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'add-party-btn';
        addBtn.innerHTML = tenantBtnLabel;
        addBtn.style.cssText = 'display: inline-flex; align-items: center; gap: 8px; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; border: none; padding: 10px 18px; border-radius: 8px; font-size: 13px; font-weight: 700; cursor: pointer; box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25); transition: all 0.2s ease;';
        
        addBtn.addEventListener('click', addTenant);
        addBtnContainer.appendChild(addBtn);
    } else {
        const addBtn = addBtnContainer.querySelector('.add-party-btn');
        if (addBtn) addBtn.innerHTML = tenantBtnLabel;
    }

    if (currentTenantCount >= 6) {
        addBtnContainer.style.display = 'none';
    } else {
        addBtnContainer.style.display = 'flex';
        if (lastContent) lastContent.appendChild(addBtnContainer);
    }

    updateBachelorSectionVisibility();
}

export function updateBachelorSectionVisibility() {
    const tenantTypeSelect = document.getElementById('tenant_type');
    const bachelorHeader = document.querySelector('.section-header[data-section-key="bachelor"]');
    const bachelorContent = document.querySelector('.section-content[data-section-key="bachelor"]');

    const isBachelor = tenantTypeSelect && (tenantTypeSelect.value || '').trim() === 'Bachelor';

    if (bachelorHeader) {
        bachelorHeader.style.display = isBachelor ? 'flex' : 'none';
    }
    if (bachelorContent) {
        bachelorContent.style.display = isBachelor ? 'grid' : 'none';
        if (isBachelor) {
            bachelorContent.style.gridTemplateColumns = 'repeat(3, 1fr)';
            bachelorContent.style.gap = '20px';
        }
    }
}
