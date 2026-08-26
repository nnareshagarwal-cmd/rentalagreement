/**
 * rental_form_core.js — AgreementAI Core Orchestrator (Phase 3)
 * ===============================================================
 * Thin orchestrator that:
 *  1. Fetches /api/field-registry and initializes generic form cards
 *  2. Attaches multi-party visibility controls (multi_party.js)
 *  3. Connects Aadhaar AI OCR card upload handlers (uploads.js)
 *  4. Manages user authentication sessions (auth.js)
 *  5. Triggers debounced live preview rendering (preview.js)
 */

import { renderSectionHeader, createFieldElement } from './form/renderer.js';
import { setupMultiPartyControls, updateBachelorSectionVisibility, setOwnerCount, setTenantCount } from './form/multi_party.js';
import { numToWords, formatIndianCurrency, calculateEndDate, calculateLockInEndDate } from './form/calculations.js';
import { checkAuthSession } from './features/auth.js';
import { attachAadhaarOcrHandlers } from './features/uploads.js';
import { refreshLivePreview, triggerDebouncedPreview, setupPreviewControls } from './preview.js';
import { initSafekeysWizard } from './safekeys_wizard.js';

let fieldRegistry = [];
let sectionLabels = {};
let sectionOrder = [];

document.addEventListener('DOMContentLoaded', async () => {
    console.log('[AgreementAI] Initializing Phase 3 Core Orchestrator...');

    setupPreviewControls();
    await checkAuthSession();

    try {
        const res = await fetch('/api/field-registry');
        const data = await res.json();
        fieldRegistry = data.fields || [];
        sectionLabels = data.section_labels || {};
        sectionOrder = data.section_order || [];

        renderRegistryForm();
        initSafekeysWizard();    // Initialize 6-step section visibility controller
        restoreFormFromLocal();  // Hydrate saved data from localStorage
    } catch (e) {
        console.error('[AgreementAI] Registry fetch failed:', e);
    }

    const form = document.getElementById('agreementForm');
    if (form) {
        form.addEventListener('change', (e) => {
            if (e.target && e.target.id && e.target.id.endsWith('_prefix')) {
                const prefixId = e.target.id.replace('_prefix', '');
                const nameInput = document.getElementById(`${prefixId}_name`);
                const selectedPfx = e.target.value;
                if (nameInput) {
                    const currentVal = (nameInput.value || '').trim();
                    if (!currentVal) {
                        nameInput.value = `${selectedPfx} `;
                    } else {
                        const prefixes = ['Mr.', 'Mrs.', 'Miss.', 'Dr.', 'Mr', 'Mrs', 'Miss', 'Dr'];
                        let cleanName = currentVal;
                        prefixes.forEach(p => {
                            if (cleanName.startsWith(p)) {
                                cleanName = cleanName.substring(p.length).trim();
                            }
                        });
                        nameInput.value = `${selectedPfx} ${cleanName}`;
                    }
                }
            }
            if (e.target && e.target.id && e.target.id.startsWith('same_as_rental_owner')) {
                const ownerAddrKey = e.target.id.replace('same_as_rental_', '');
                const ownerAddrInput = document.getElementById(ownerAddrKey);
                const propAddrInput = document.getElementById('property_address') || document.getElementById('P12');
                if (ownerAddrInput && propAddrInput) {
                    if (e.target.checked) {
                        ownerAddrInput.value = propAddrInput.value;
                    }
                }
            }
            if (e.target && (e.target.id === 'property_address' || e.target.id === 'P12')) {
                e.target.dataset.userModified = 'true';
            }
            if (e.target && (e.target.id === 'security_deposit' || e.target.id === 'P19')) {
                e.target.dataset.autoCalculated = 'false';
            }
            if (e.target && e.target.id && e.target.id.includes('_careof')) {
                e.target.dataset.userModified = 'true';
            }
            handleCalculations();
            debouncedLocalSave();
            triggerDebouncedPreview();
        });

        form.addEventListener('input', (e) => {
            if (e.target && (e.target.id === 'monthly_rent' || e.target.id === 'security_deposit' || e.target.id === 'P13' || e.target.id === 'P19')) {
                const cursorPos = e.target.selectionStart;
                const origLen = e.target.value.length;
                const rawDigits = e.target.value.replace(/\D/g, '');
                if (rawDigits) {
                    const formatted = formatIndianCurrency(rawDigits);
                    e.target.value = formatted;
                    const newLen = formatted.length;
                    const newPos = Math.max(0, cursorPos + (newLen - origLen));
                    try { e.target.setSelectionRange(newPos, newPos); } catch (err) {}
                }
            }
            if (e.target && (e.target.id === 'property_address' || e.target.id === 'P12')) {
                e.target.dataset.userModified = 'true';
            }
            if (e.target && (e.target.id === 'security_deposit' || e.target.id === 'P19')) {
                e.target.dataset.autoCalculated = 'false';
            }
            if (e.target && e.target.id && e.target.id.includes('_careof')) {
                e.target.dataset.userModified = 'true';
            }
            handleCalculations();
            debouncedLocalSave();
            triggerDebouncedPreview();
        });
    }

    handleCalculations();
    refreshLivePreview();

    // ── Save Button Handler ────────────────────────────────────────────────
    const saveBtn = document.getElementById('saveBtn');
    if (saveBtn) {
        saveBtn.addEventListener('click', handleSave);
    }

    // ── Generate Document Button Handler ───────────────────────────────────
    const generateBtn = document.getElementById('generateBtn');
    if (generateBtn) {
        generateBtn.addEventListener('click', async () => {
            const originalLabel = generateBtn.innerHTML;
            generateBtn.disabled = true;
            generateBtn.textContent = 'Generating DOCX…';

            try {
                await refreshLivePreview();

                const response = await fetch('/api/rental/download-docx', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(getFormData()),
                });
                if (!response.ok) {
                    let errMsg = 'Could not generate the document. Please try again.';
                    try {
                        const errData = await response.json();
                        if (errData && errData.error) errMsg = errData.error;
                    } catch (_) {}
                    throw new Error(errMsg);
                }

                const fileBlob = await response.blob();
                const downloadUrl = URL.createObjectURL(fileBlob);
                const link = document.createElement('a');
                const disposition = response.headers.get('Content-Disposition') || '';
                const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
                link.href = downloadUrl;
                link.download = filenameMatch ? filenameMatch[1] : 'Rental_Agreement.docx';
                document.body.appendChild(link);
                link.click();
                link.remove();
                URL.revokeObjectURL(downloadUrl);

                showMessage('Document generated and downloaded successfully!', 'success');
            } catch (error) {
                console.error('[AgreementAI] Document generation failed:', error);
                showMessage(error.message || 'Could not generate the document. Please try again.', 'error');
            } finally {
                generateBtn.disabled = false;
                generateBtn.innerHTML = originalLabel;
            }
        });
    }

    // ── Download / PDF buttons ─────────────────────────────────────────────
    const generatePdfBtn = document.getElementById('generatePdfBtn');
    if (generatePdfBtn) {
        generatePdfBtn.addEventListener('click', () => window.triggerPdfDownload(generatePdfBtn));
    }

    const requestEsignBtn = document.getElementById('requestEsignBtn');
    if (requestEsignBtn) {
        requestEsignBtn.addEventListener('click', () => window.triggerEsignRequest(requestEsignBtn));
    }
});

function getFormData() {
    const formData = {};
    fieldRegistry.forEach(fieldDef => {
        const el = document.getElementById(fieldDef.key);
        if (!el) return;
        if (fieldDef.type === 'checkbox') {
            formData[fieldDef.key] = el.checked ? 'Y' : 'N';
        } else {
            formData[fieldDef.key] = el.value || '';
        }
    });
    return formData;
}

window.triggerEsignRequest = function(btnElement) {
    const payload = getFormData();
    if (window.safeKeysEsign) {
        window.safeKeysEsign.initiateEsignFromForm(payload);
        return;
    }
    if (typeof SafeKeysEsignController !== 'undefined') {
        window.safeKeysEsign = new SafeKeysEsignController();
        window.safeKeysEsign.initiateEsignFromForm(payload);
        return;
    }
    // Dynamic loader fallback
    const script = document.createElement('script');
    script.src = `/static/js/safekeys_esign.js?v=${Date.now()}`;
    script.onload = () => {
        if (typeof SafeKeysEsignController !== 'undefined') {
            window.safeKeysEsign = new SafeKeysEsignController();
            window.safeKeysEsign.initiateEsignFromForm(payload);
        } else if (window.safeKeysEsign) {
            window.safeKeysEsign.initiateEsignFromForm(payload);
        }
    };
    script.onerror = () => {
        console.error('[AgreementAI] Failed to load safekeys_esign.js');
        showMessage('Unable to initialize digital signature module. Please refresh the page.', 'error');
    };
    document.head.appendChild(script);
};

window.triggerPdfDownload = async function(btnElement) {
    let originalLabel = '';
    if (btnElement) {
        btnElement.disabled = true;
        originalLabel = btnElement.innerHTML;
        btnElement.textContent = 'Preparing PDF…';
    }

    try {
        const payload = getFormData();
        const response = await fetch('/api/rental/download-pdf', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        if (!response.ok) {
            let errMsg = 'Could not generate the PDF document. Please try again.';
            try {
                const errData = await response.json();
                if (errData && errData.error) errMsg = errData.error;
            } catch (_) {}
            throw new Error(errMsg);
        }

        const fileBlob = await response.blob();
        const downloadUrl = URL.createObjectURL(fileBlob);
        const link = document.createElement('a');
        const disposition = response.headers.get('Content-Disposition') || '';
        const filenameMatch = disposition.match(/filename="?([^";]+)"?/i);
        link.href = downloadUrl;
        link.download = filenameMatch ? filenameMatch[1] : 'Rental_Agreement.pdf';
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(downloadUrl);

        showMessage('PDF generated successfully!', 'success');
    } catch (error) {
        console.error('[AgreementAI] PDF download failed:', error);
        showMessage(error.message || 'Could not generate the PDF document. Please try again.', 'error');
    } finally {
        if (btnElement) {
            btnElement.disabled = false;
            btnElement.innerHTML = originalLabel;
        }
    }
};

function renderRegistryForm() {
    const formFieldsDiv = document.getElementById('formFields');
    if (!formFieldsDiv) return;
    formFieldsDiv.innerHTML = '';

    const grouped = {};
    fieldRegistry.forEach(f => {
        const sec = f.section || 'meta';
        if (!grouped[sec]) grouped[sec] = [];
        grouped[sec].push(f);
    });

    const orderedSections = sectionOrder.length > 0 ? sectionOrder : Object.keys(grouped);
    const path = window.location.pathname.toLowerCase();
    const isLeaveLicense = path.includes('leave') || path.includes('license');

    orderedSections.forEach(secKey => {
        if (secKey === 'meta') return;
        if (grouped[secKey] && grouped[secKey].length > 0) {
            let title = sectionLabels[secKey] || secKey.toUpperCase();
            if (isLeaveLicense) {
                title = title.replace(/\bOwner\b/gi, 'Licensor').replace(/\bTenant\b/gi, 'Licensee');
            }
            const { header, sectionContent } = renderSectionHeader(secKey, title);

            grouped[secKey].forEach(fieldDef => {
                const val = '';
                const fieldEl = createFieldElement(fieldDef, val);
                sectionContent.appendChild(fieldEl);
            });

            formFieldsDiv.appendChild(header);
            formFieldsDiv.appendChild(sectionContent);
        }
    });

    ['owner_1', 'owner_2', 'tenant_1', 'tenant_2'].forEach(sec => {
        attachAadhaarOcrHandlers(sec, () => {
            handleCalculations();
            triggerDebouncedPreview();
        });
    });

    setupMultiPartyControls();
}

function handleCalculations() {
    // 1. Set Today's Date by default
    const todayStr = new Date().toISOString().split('T')[0];
    const agrDateInput = document.getElementById('agreement_date') || document.getElementById('P1');
    if (agrDateInput && !agrDateInput.value) {
        agrDateInput.value = todayStr;
    }

    // 2. Lock-in fields visibility based on Lock-in checkbox
    const lockinCb = document.getElementById('lockin') || document.getElementById('P27');
    const lockinEndGroup = document.getElementById('form-group-lockin_end_date') || document.getElementById('form-group-P28');
    const lockinMonthsGroup = document.getElementById('form-group-lockin_months');
    const penaltyGroup = document.getElementById('form-group-penalty_deduction');
    
    const isLockinEnabled = lockinCb && lockinCb.checked;
    if (lockinEndGroup) lockinEndGroup.style.display = isLockinEnabled ? 'block' : 'none';
    if (lockinMonthsGroup) lockinMonthsGroup.style.display = isLockinEnabled ? 'block' : 'none';
    if (penaltyGroup) penaltyGroup.style.display = isLockinEnabled ? 'block' : 'none';

    // 3. Auto-calculate Security Deposit (2x Rent) & Rent Words
    const rentInput = document.getElementById('monthly_rent') || document.getElementById('P13');
    const rentWordsInput = document.getElementById('monthly_rent_words') || document.getElementById('P14');
    const depInput = document.getElementById('security_deposit') || document.getElementById('P19');
    const depWordsInput = document.getElementById('security_deposit_words') || document.getElementById('P20');

    if (rentInput && rentInput.value) {
        const cleanRentStr = rentInput.value.toString().replace(/,/g, '').trim();
        const rentVal = parseFloat(cleanRentStr);

        if (!isNaN(rentVal)) {
            rentWordsInput && (rentWordsInput.value = numToWords(rentVal));

            // Auto-calculate Security Deposit as 2x Rent if not set or if user hasn't overridden with custom non-2x value
            if (depInput && (!depInput.value || depInput.dataset.autoCalculated === 'true' || depInput.dataset.autoCalculated === undefined)) {
                const depositVal = rentVal * 2;
                depInput.value = formatIndianCurrency(depositVal);
                depInput.dataset.autoCalculated = 'true';
            }
        }
    }

    // 4. Auto-calculate Deposit Words
    if (depInput && depWordsInput && depInput.value) {
        const cleanDepStr = depInput.value.toString().replace(/,/g, '').trim();
        const depVal = parseFloat(cleanDepStr);
        if (!isNaN(depVal)) {
            depWordsInput.value = numToWords(depVal);
        }
    }

    // 5. Auto-calculate Agreement End Date
    const startDateInput = document.getElementById('agreement_start_date') || document.getElementById('P16');
    const endDateInput = document.getElementById('agreement_end_date') || document.getElementById('P17');
    if (startDateInput && endDateInput && startDateInput.value && !endDateInput.value) {
        endDateInput.value = calculateEndDate(startDateInput.value, 11);
    }

    // 6. Auto-calculate Lock-in End Date
    const lockinInput = document.getElementById('lockin_months') || document.getElementById('P21');
    const lockinEndInput = document.getElementById('lockin_end_date') || document.getElementById('P28');
    if (startDateInput && lockinInput && lockinEndInput && startDateInput.value && lockinInput.value) {
        lockinEndInput.value = calculateLockInEndDate(startDateInput.value, lockinInput.value);
    }

    // 7. Dynamic Prefix -> Care-Of (Father/Husband) & Relationship auto-rules
    ['owner1', 'owner2', 'owner3', 'owner4', 'owner5', 'owner6',
     'tenant1', 'tenant2', 'tenant3', 'tenant4', 'tenant5', 'tenant6'].forEach(prefixId => {
        const prefixSelect = document.getElementById(`${prefixId}_prefix`);
        const careofSelect = document.getElementById(`${prefixId}_careof`);
        const careofGroup = document.getElementById(`form-group-${prefixId}_careof`);
        const careofNameInput = document.getElementById(`${prefixId}_careofname`);
        const careofNameLabel = document.querySelector(`#form-group-${prefixId}_careofname label`);

        if (prefixSelect && careofSelect) {
            const pVal = (prefixSelect.value || '').trim().toLowerCase().replace('.', '');
            if (pVal === 'mr' || pVal === 'master' || pVal === 'shri' || pVal === 'miss') {
                careofSelect.value = 'Father Name';
                if (careofGroup) careofGroup.style.display = 'none';
            } else if (pVal === 'mrs' || pVal === 'smt') {
                if (careofGroup) careofGroup.style.display = 'block';
                if (!careofSelect.dataset.userModified) {
                    careofSelect.value = 'Husband Name';
                }
            } else {
                if (careofGroup) careofGroup.style.display = 'block';
            }
        }

        if (careofSelect && careofNameLabel) {
            const partyTitle = prefixId.startsWith('owner') ? 'Owner' : 'Tenant';
            const num = prefixId.replace('owner', '').replace('tenant', '');
            const numStr = num === '1' ? '' : ` ${num}`;
            const relType = careofSelect.value === 'Husband Name' ? 'Husband' : 'Father';
            const icon = relType === 'Husband' ? '👨' : '👨';
            careofNameLabel.innerHTML = `${icon} ${partyTitle}${numStr} ${relType} Name`;
        }

        if (careofNameInput) {
            careofNameInput.placeholder = "e.g. Mr. Ramesh Sharma";
            if (!careofNameInput.value && !careofNameInput.dataset.initialized) {
                careofNameInput.value = "Mr. ";
                careofNameInput.dataset.initialized = "true";
            }
        }
    });

    // 8. Property Type rules: Villa & Independent House
    const propTypeSelect = document.getElementById('property_type') || document.getElementById('PROP_TYPE');
    const blockGroup = document.getElementById('form-group-property_block');
    const noGroup = document.getElementById('form-group-property_no');
    
    if (propTypeSelect) {
        const val = (propTypeSelect.value || '').trim().toUpperCase();

        if (blockGroup) {
            if (val === 'VILLA' || val.includes('INDEPENDENT') || val === 'HOUSE') {
                blockGroup.style.display = 'none';
            } else {
                blockGroup.style.display = 'block';
            }
        }

        if (noGroup) {
            const labelEl = noGroup.querySelector('label');
            if (labelEl) {
                if (val === 'VILLA') {
                    labelEl.innerHTML = '🏠 Villa Number';
                } else if (val.includes('INDEPENDENT') || val === 'HOUSE') {
                    labelEl.innerHTML = '🏠 House / Door Number';
                } else {
                    labelEl.innerHTML = '🏠 Flat / Door Number';
                }
            }
        }
    }

    // 8. Auto-build Rental Property Address
    const propType = (propTypeSelect ? propTypeSelect.value : '').trim();
    const propBlock = (document.getElementById('property_block')?.value || '').trim();
    const propNo = (document.getElementById('property_no')?.value || '').trim();
    const societyName = (document.getElementById('society_name')?.value || '').trim();
    const propAddrInput = document.getElementById('property_address') || document.getElementById('P12');

    if (propAddrInput && !propAddrInput.dataset.userModified) {
        const parts = [];
        if (propNo) {
            const valUpper = propType.toUpperCase();
            if (valUpper === 'VILLA' && !propNo.toLowerCase().includes('villa')) {
                parts.push(`Villa No. ${propNo}`);
            } else if ((valUpper.includes('INDEPENDENT') || valUpper === 'HOUSE') && !propNo.toLowerCase().includes('house')) {
                parts.push(`House No. ${propNo}`);
            } else if (!propNo.toLowerCase().includes('flat') && !propNo.toLowerCase().includes('door')) {
                parts.push(`Flat No. ${propNo}`);
            } else {
                parts.push(propNo);
            }
        }
        if (propBlock && (propType.toUpperCase() === 'APARTMENT' || !propType)) {
            if (!propBlock.toLowerCase().includes('block') && !propBlock.toLowerCase().includes('tower')) {
                parts.push(`Block ${propBlock}`);
            } else {
                parts.push(propBlock);
            }
        }
        if (societyName) {
            parts.push(societyName);
        }

        if (parts.length > 0) {
            propAddrInput.value = parts.join(', ');
        }
    }

    // 9. Sync any checked 'Same as Rental Property Address' fields
    ['owner1', 'owner2', 'owner3', 'owner4', 'owner5', 'owner6'].forEach(ownerId => {
        const cb = document.getElementById(`same_as_rental_${ownerId}_address`);
        const ownerAddrInput = document.getElementById(`${ownerId}_address`);
        if (cb && cb.checked && ownerAddrInput && propAddrInput) {
            ownerAddrInput.value = propAddrInput.value;
        }
    });

    // 10. Auto-calculate Opposite Gender for Bachelor section
    const tenantGenderEl = document.getElementById('tenant_gender');
    const oppGenderEl = document.getElementById('opp_gender');
    if (tenantGenderEl && oppGenderEl) {
        const val = (tenantGenderEl.value || '').trim().toLowerCase();
        if (val === 'male') {
            oppGenderEl.value = 'Female';
        } else if (val === 'female') {
            oppGenderEl.value = 'Male';
        } else {
            oppGenderEl.value = '';
        }
    }

    // 11. Toggle Bachelor Section Visibility
    updateBachelorSectionVisibility();

    // 12. Dynamically populate SPOC dropdown options with Tenant Names
    const spocSelect = document.getElementById('tenant_poc');
    if (spocSelect) {
        const tenantNames = [];
        const tenantCountInput = document.getElementById('tenant_count');
        const count = tenantCountInput ? parseInt(tenantCountInput.value || '1', 10) : 1;

        for (let i = 1; i <= count; i++) {
            const nameEl = document.getElementById(`tenant${i}_name`);
            const val = nameEl ? (nameEl.value || '').trim() : '';
            if (val) {
                tenantNames.push(val);
            } else {
                tenantNames.push(`Tenant ${i}`);
            }
        }

        const currentSelected = spocSelect.value;
        spocSelect.innerHTML = '';
        tenantNames.forEach(tName => {
            const opt = document.createElement('option');
            opt.value = tName;
            opt.textContent = tName;
            if (tName === currentSelected) opt.selected = true;
            spocSelect.appendChild(opt);
        });
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// Save Handler — Premium UX with overlay + toast
// ─────────────────────────────────────────────────────────────────────────────

function _ensureSaveOverlay() {
    if (document.getElementById('saveOverlay')) return;
    const overlay = document.createElement('div');
    overlay.id = 'saveOverlay';
    overlay.className = 'save-overlay';
    overlay.innerHTML = `
        <div class="save-overlay-card">
            <div id="saveOverlaySpinner" class="save-overlay-spinner"></div>
            <div id="saveOverlayIcon" class="save-overlay-icon" style="display:none;"></div>
            <div id="saveOverlayTitle" class="save-overlay-title">Saving Agreement…</div>
            <div id="saveOverlaySubtitle" class="save-overlay-subtitle"></div>
            <div id="saveOverlayAgrNum" class="save-overlay-agr-num" style="display:none;"></div>
        </div>
    `;
    document.body.appendChild(overlay);
}

function _ensureToastContainer() {
    if (document.getElementById('toastContainer')) return;
    const container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
}

function _showSaveOverlay(state, opts = {}) {
    _ensureSaveOverlay();
    const overlay   = document.getElementById('saveOverlay');
    const spinner   = document.getElementById('saveOverlaySpinner');
    const icon      = document.getElementById('saveOverlayIcon');
    const title     = document.getElementById('saveOverlayTitle');
    const subtitle  = document.getElementById('saveOverlaySubtitle');
    const agrNum    = document.getElementById('saveOverlayAgrNum');

    overlay.classList.add('active');

    if (state === 'saving') {
        spinner.style.display = 'block';
        icon.style.display = 'none';
        agrNum.style.display = 'none';
        title.textContent = 'Saving Agreement…';
        subtitle.textContent = '';
    } else if (state === 'success') {
        spinner.style.display = 'none';
        icon.style.display = 'flex';
        icon.className = 'save-overlay-icon success';
        icon.textContent = '✓';
        title.textContent = 'Saved Successfully!';
        subtitle.textContent = opts.message || 'Agreement stored in database';
        if (opts.agrNumber) {
            agrNum.textContent = opts.agrNumber;
            agrNum.style.display = 'inline-block';
        }
    } else if (state === 'error') {
        spinner.style.display = 'none';
        icon.style.display = 'flex';
        icon.className = 'save-overlay-icon error';
        icon.textContent = '✕';
        title.textContent = 'Save Failed';
        subtitle.textContent = opts.message || 'Please try again';
        agrNum.style.display = 'none';
    }
}

function _hideSaveOverlay() {
    const overlay = document.getElementById('saveOverlay');
    if (overlay) overlay.classList.remove('active');
}

function showToast(type, title, detail) {
    _ensureToastContainer();
    const container = document.getElementById('toastContainer');

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${type === 'success' ? '✅' : '❌'}</span>
        <div class="toast-body">
            <div class="toast-title">${title}</div>
            ${detail ? `<div class="toast-detail">${detail}</div>` : ''}
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
    `;
    container.appendChild(toast);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

async function handleSave() {
    const saveBtn = document.getElementById('saveBtn');

    try {
        // Show overlay + animate button
        if (saveBtn) {
            saveBtn.classList.add('is-saving');
            saveBtn.innerHTML = '<span style="display:inline-flex;align-items:center;gap:6px;"><span style="width:14px;height:14px;border:2px solid rgba(255,255,255,0.3);border-top:2px solid white;border-radius:50%;display:inline-block;animation:spinSave 0.7s linear infinite;"></span> Saving…</span>';
        }
        _showSaveOverlay('saving');

        // Collect all form data from registry fields
        const formData = {};
        fieldRegistry.forEach(fieldDef => {
            const el = document.getElementById(fieldDef.key);
            if (!el) return;
            if (fieldDef.type === 'checkbox') {
                formData[fieldDef.key] = el.checked ? 'Y' : 'N';
            } else {
                formData[fieldDef.key] = el.value || '';
            }
        });

        // Hidden property_id
        const propIdInput = document.getElementById('property_id');
        if (propIdInput && propIdInput.value) formData.property_id = propIdInput.value;

        // Include rendered preview HTML
        const previewContent = document.getElementById('previewContent');
        if (previewContent) formData.full_text = previewContent.innerHTML;

        // Descriptive title
        const society = formData.society_name || '';
        const ownerName = formData.owner1_name || '';
        const tenantName = formData.tenant1_name || '';
        formData.title = society
            ? `${society} — ${ownerName || 'Owner'} ↔ ${tenantName || 'Tenant'}`
            : `Agreement — ${ownerName || 'Owner'} ↔ ${tenantName || 'Tenant'}`;

        console.log('[AgreementAI] Saving form data:', Object.keys(formData).length, 'fields');

        const res = await fetch('/api/rental/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData),
        });

        const result = await res.json();

        if (result.success) {
            // Overlay → success state
            _showSaveOverlay('success', {
                agrNumber: result.agreement_number,
                message: result.message || 'Agreement stored in database'
            });

            // Button → green success
            if (saveBtn) {
                saveBtn.classList.remove('is-saving');
                saveBtn.classList.add('is-success');
                saveBtn.innerHTML = '<span style="display:inline-flex;align-items:center;gap:6px;">✓ Saved!</span>';
            }

            // Toast notification
            showToast('success', 'Agreement Saved', `Reference: ${result.agreement_number}`);

            // Auto-dismiss overlay after 2s
            setTimeout(() => {
                _hideSaveOverlay();
                if (saveBtn) {
                    saveBtn.classList.remove('is-success');
                    saveBtn.innerHTML = '💾 Save';
                }
            }, 2000);
        } else {
            _showSaveOverlay('error', { message: result.error || 'Unknown error occurred' });
            if (saveBtn) {
                saveBtn.classList.remove('is-saving');
                saveBtn.classList.add('is-error');
                saveBtn.innerHTML = '❌ Failed';
            }
            showToast('error', 'Save Failed', result.error || 'Unknown error');
            setTimeout(() => {
                _hideSaveOverlay();
                if (saveBtn) {
                    saveBtn.classList.remove('is-error');
                    saveBtn.innerHTML = '💾 Save';
                }
            }, 3000);
        }
    } catch (err) {
        console.error('[AgreementAI] Save error:', err);
        _showSaveOverlay('error', { message: err.message || 'Network error — check connection' });
        if (saveBtn) {
            saveBtn.classList.remove('is-saving');
            saveBtn.classList.add('is-error');
            saveBtn.innerHTML = '❌ Failed';
        }
        showToast('error', 'Save Failed', err.message || 'Network error');
        setTimeout(() => {
            _hideSaveOverlay();
            if (saveBtn) {
                saveBtn.classList.remove('is-error');
                saveBtn.innerHTML = '💾 Save';
            }
        }, 3000);
    }
}

function showMessage(text, type = 'info') {
    // Delegate to toast system
    if (type === 'success') {
        showToast('success', text, '');
    } else if (type === 'error') {
        showToast('error', text, '');
    } else {
        showToast('success', text, '');
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// LocalStorage Auto-Persistence — survives refresh, tab close, coming back
// ─────────────────────────────────────────────────────────────────────────────
const LOCAL_STORAGE_KEY = 'agreementai_form_draft';
let _localSaveTimer = null;

function debouncedLocalSave() {
    clearTimeout(_localSaveTimer);
    _localSaveTimer = setTimeout(saveFormToLocal, 500);
}

function saveFormToLocal() {
    try {
        const formData = {};
        fieldRegistry.forEach(fieldDef => {
            const el = document.getElementById(fieldDef.key);
            if (!el) return;
            if (fieldDef.type === 'checkbox') {
                formData[fieldDef.key] = el.checked ? 'Y' : 'N';
            } else {
                formData[fieldDef.key] = el.value || '';
            }
        });
        formData._savedAt = new Date().toISOString();
        localStorage.setItem(LOCAL_STORAGE_KEY, JSON.stringify(formData));
    } catch (e) {
        console.warn('[AgreementAI] localStorage save failed:', e);
    }
}

function restoreFormFromLocal() {
    try {
        const raw = localStorage.getItem(LOCAL_STORAGE_KEY);
        if (!raw) return;
        const saved = JSON.parse(raw);
        if (!saved || typeof saved !== 'object') return;

        console.log('[AgreementAI] Restoring form from localStorage (saved:', saved._savedAt || 'unknown', ')');

        let restoredCount = 0;
        fieldRegistry.forEach(fieldDef => {
            const val = saved[fieldDef.key];
            if (val === undefined || val === null) return;

            const el = document.getElementById(fieldDef.key);
            if (!el) return;

            if (fieldDef.type === 'checkbox') {
                el.checked = (val === 'Y' || val === true);
            } else {
                el.value = val;
            }

            // Mark deposit as user-set if it was previously overridden
            if (fieldDef.key === 'security_deposit' && val) {
                el.dataset.autoCalculated = 'false';
            }

            restoredCount++;
        });

        console.log(`[AgreementAI] Restored ${restoredCount} fields from localStorage`);

        // Restore owner and tenant section visibility based on saved count or non-empty fields
        let savedOwnerCnt = parseInt(saved.owner_count || '1', 10);
        let savedTenantCnt = parseInt(saved.tenant_count || '1', 10);

        for (let i = 6; i >= 2; i--) {
            if (saved[`owner${i}_name`] || saved[`owner${i}_address`]) {
                savedOwnerCnt = Math.max(savedOwnerCnt, i);
            }
            if (saved[`tenant${i}_name`] || saved[`tenant${i}_address`]) {
                savedTenantCnt = Math.max(savedTenantCnt, i);
            }
        }

        setOwnerCount(savedOwnerCnt);
        setTenantCount(savedTenantCnt);

        // Re-run calculations and preview after restoring
        handleCalculations();
        refreshLivePreview();
    } catch (e) {
        console.warn('[AgreementAI] localStorage restore failed:', e);
    }
}
