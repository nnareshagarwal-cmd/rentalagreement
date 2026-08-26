/**
 * safekeys_wizard.js — 6-Step Section Visibility Controller (Sprint 2.2A Refined)
 * ==================================================================================
 * Pure visibility orchestrator that maps existing registry section cards into 6 clean
 * step views while preserving multi-party count controls, form data, & backend endpoints.
 *
 * Imports isSectionAllowedByMultiParty from multi_party.js (one-way dependency).
 * Listens for 'multiPartyChanged' CustomEvent to re-evaluate visibility when
 * owner/tenant counts change.
 */

import { isSectionAllowedByMultiParty, getOwnerCount, getTenantCount, updatePartyNavigation } from './form/multi_party.js';
import { syncPreviewToStep } from './preview_sync.js';

export const WIZARD_STEP_MAP = {
    1: ['meta', 'agreement_dates'],
    2: ['property'],
    3: ['owner_1', 'owner_2', 'owner_3', 'owner_4', 'owner_5', 'owner_6'],
    4: ['tenant_1', 'tenant_2', 'tenant_3', 'tenant_4', 'tenant_5', 'tenant_6', 'bachelor'],
    5: ['financial'],
    6: ['ALL'] // Step 6 Review & Generate shows full form review summary
};

export const STEP_LABELS = {
    1: '📋 Agreement & Dates',
    2: '🏠 Property',
    3: '👤 Owners',
    4: '🔑 Tenants',
    5: '💰 Financial',
    6: '📄 Review & Generate'
};

let currentStep = 1;

export function initSafekeysWizard() {
    const formFields = document.getElementById('formFields');
    if (!formFields) return;

    // Sync header title text and document title based on agreement type URL
    const path = window.location.pathname;
    const titleTextEl = document.getElementById('formHeaderTitleText');
    if (titleTextEl) {
        if (path.includes('leave-and-license')) {
            titleTextEl.textContent = 'Leave and License Agreement Form';
            document.title = 'Leave and License Agreement Form';
        } else if (path.includes('simple-rental') || path.includes('rental')) {
            titleTextEl.textContent = 'Rental Agreement Form';
            document.title = 'Rental Agreement Form';
        }
    }

    // Create Stepper Bar if not already present
    let stepperContainer = document.getElementById('skWizardStepper');
    if (!stepperContainer) {
        stepperContainer = document.createElement('div');
        stepperContainer.id = 'skWizardStepper';
        stepperContainer.className = 'sk-wizard-stepper';
        formFields.parentNode.insertBefore(stepperContainer, formFields);
    }

    let reviewSummary = document.getElementById('skReviewSummary');
    if (!reviewSummary) {
        reviewSummary = document.createElement('section');
        reviewSummary.id = 'skReviewSummary';
        reviewSummary.className = 'sk-review-summary';
        reviewSummary.hidden = true;
        formFields.parentNode.insertBefore(reviewSummary, formFields);
    }

    renderStepperBar(stepperContainer);
    attachNavigationButtons();

    // Added/removed owners and tenants change which section cards are eligible
    // for the current wizard step. Reapply the step rules immediately so newly
    // added party forms are displayed instead of retaining a previous `display:none`.
    document.addEventListener('multiPartyChanged', () => updateStepVisibility(currentStep));

    // Setup scroll shadow listener for sticky workspace header
    const stickyHeader = document.getElementById('stickyWorkspaceHeader');
    if (stickyHeader) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 10) {
                stickyHeader.classList.add('is-scrolled');
            } else {
                stickyHeader.classList.remove('is-scrolled');
            }
        });
    }

    // Setup real-time error state removal for Lock-in inputs
    const lockinCb = document.getElementById('lockin');
    const lockinMonthsInput = document.getElementById('lockin_months');
    const penaltyInput = document.getElementById('penalty_deduction');

    if (lockinCb) {
        lockinCb.addEventListener('change', () => {
            if (!lockinCb.checked) {
                if (lockinMonthsInput) lockinMonthsInput.classList.remove('is-invalid');
                if (penaltyInput) penaltyInput.classList.remove('is-invalid');
            }
        });
    }

    [lockinMonthsInput, penaltyInput].forEach(inputEl => {
        if (inputEl) {
            inputEl.addEventListener('input', () => {
                if (inputEl.value.trim()) {
                    inputEl.classList.remove('is-invalid');
                }
            });
        }
    });

    updateStepVisibility(currentStep);
}

/**
 * Business Rule Check:
 * If Lock-in Period is selected, Lock-in Months and Penalty Deduction (days)
 * must have valid non-empty values before proceeding to subsequent sections.
 */
export function validateLockInRequirements() {
    const lockinCheckbox = document.getElementById('lockin');
    if (!lockinCheckbox || !lockinCheckbox.checked) {
        return { valid: true };
    }

    const lockinMonthsEl = document.getElementById('lockin_months');
    const penaltyDeductionEl = document.getElementById('penalty_deduction');

    const monthsVal = lockinMonthsEl ? lockinMonthsEl.value.trim() : '';
    const penaltyVal = penaltyDeductionEl ? penaltyDeductionEl.value.trim() : '';

    // Clear previous error states
    if (lockinMonthsEl) lockinMonthsEl.classList.remove('is-invalid');
    if (penaltyDeductionEl) penaltyDeductionEl.classList.remove('is-invalid');

    if (!monthsVal) {
        if (lockinMonthsEl) {
            lockinMonthsEl.classList.add('is-invalid');
            lockinMonthsEl.focus();
        }
        showWizardNotification('warning', 'Lock-in Months Required', '🔒 Please enter Lock-in Months because Lock-in Period is selected.');
        return { valid: false, field: lockinMonthsEl };
    }

    if (!penaltyVal) {
        if (penaltyDeductionEl) {
            penaltyDeductionEl.classList.add('is-invalid');
            penaltyDeductionEl.focus();
        }
        showWizardNotification('warning', 'Penalty Deduction Required', '⚠️ Please enter Penalty Deduction (days) because Lock-in Period is selected.');
        return { valid: false, field: penaltyDeductionEl };
    }

    return { valid: true };
}

function showWizardNotification(type, title, detail) {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <span class="toast-icon">${type === 'success' ? '✅' : '⚠️'}</span>
        <div class="toast-body">
            <div class="toast-title">${title}</div>
            ${detail ? `<div class="toast-detail">${detail}</div>` : ''}
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">✕</button>
    `;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function renderStepperBar(container) {
    container.innerHTML = '';
    for (let step = 1; step <= 6; step++) {
        const pill = document.createElement('button');
        pill.type = 'button';
        pill.className = `sk-wizard-step-pill ${step === currentStep ? 'active' : ''}`;
        pill.dataset.step = step;
        pill.innerHTML = `
            <span class="sk-wizard-step-number">${step}</span>
            <span>${STEP_LABELS[step]}</span>
        `;
        pill.addEventListener('click', () => goToStep(step));
        container.appendChild(pill);
    }
}

export function goToStep(stepNumber) {
    if (stepNumber < 1 || stepNumber > 6) return;

    // Business Rule Check: If Lock-in Period is selected, Lock-in Months and Penalty Deduction (days)
    // must have values before moving to subsequent sections (stepNumber > currentStep).
    if (stepNumber > currentStep) {
        const check = validateLockInRequirements();
        if (!check.valid) {
            if (currentStep !== 1) {
                // Ensure form displays step 1 where Lock-in fields reside
                currentStep = 1;
                updateStepVisibility(1);
            }
            return;
        }
    }

    currentStep = stepNumber;

    // Review is a confirmation workspace. Give its summary the full panel
    // width by default; the header Preview button can reopen the document.
    setPreviewVisibilityForStep(stepNumber);

    // Update active pill styling
    const pills = document.querySelectorAll('.sk-wizard-step-pill');
    pills.forEach(pill => {
        const s = parseInt(pill.dataset.step, 10);
        pill.classList.toggle('active', s === currentStep);
    });

    updateStepVisibility(currentStep);
    updateNavigationButtonStates();

    // Auto-scroll top stepper bar horizontally so active step is visible
    scrollStepperBarToStep(currentStep);

    // Smooth scroll back to top of form container on step change
    const container = document.querySelector('.container');
    if (container) {
        container.scrollTop = 0;
    }

    // Synchronize live document preview pane to active step section
    syncPreviewToStep(currentStep);
}

/**
 * Auto-scroll top stepper bar horizontally so active step button is always visible.
 * @param {number} stepNumber 
 */
function scrollStepperBarToStep(stepNumber) {
    const stepperContainer = document.getElementById('skWizardStepper');
    const activePill = document.querySelector(`.sk-wizard-step-pill[data-step="${stepNumber}"]`);
    if (!stepperContainer || !activePill) return;

    const pillRect = activePill.getBoundingClientRect();
    const containerRect = stepperContainer.getBoundingClientRect();

    // Check if active pill is outside container bounds or close to edge
    const isLeftOff = pillRect.left < containerRect.left + 16;
    const isRightOff = pillRect.right > containerRect.right - 16;

    if (isLeftOff || isRightOff) {
        const relativeLeft = (pillRect.left - containerRect.left) + stepperContainer.scrollLeft;
        const targetScrollLeft = Math.max(0, relativeLeft - (stepperContainer.clientWidth / 2) + (activePill.clientWidth / 2));

        stepperContainer.scrollTo({
            left: targetScrollLeft,
            behavior: 'smooth'
        });
    }
}

export function nextStep() {
    if (currentStep < 6) {
        goToStep(currentStep + 1);
    }
}

export function prevStep() {
    if (currentStep > 1) {
        goToStep(currentStep - 1);
    }
}

export function updateStepVisibility(activeStep = currentStep) {
    document.body.classList.toggle('sk-step-6-active', activeStep === 6);

    const formFields = document.getElementById('formFields');
    const reviewSummary = document.getElementById('skReviewSummary');
    if (activeStep === 6) {
        if (formFields) formFields.style.setProperty('display', 'none', 'important');
        if (reviewSummary) {
            renderReviewSummary(reviewSummary);
            reviewSummary.hidden = false;
        }
        return;
    }

    if (formFields) formFields.style.removeProperty('display');
    if (reviewSummary) reviewSummary.hidden = true;

    const sectionHeaders = document.querySelectorAll('.section-header');
    const sectionContents = document.querySelectorAll('.section-content');

    const allowedSections = WIZARD_STEP_MAP[activeStep] || [];
    const showAll = allowedSections.includes('ALL');

    sectionHeaders.forEach(header => {
        const key = header.dataset.sectionKey;
        if (!key) return;
        const isStepAllowed = showAll || allowedSections.includes(key);
        const isMultiPartyAllowed = isSectionAllowedByMultiParty(key);

        if (isStepAllowed && isMultiPartyAllowed) {
            // Keep this in sync with safekeys-ui.css, which sets header display
            // with !important. Without this, removed party headers stay visible.
            header.style.setProperty('display', 'flex', 'important');
            delete header.dataset.stepHidden;
        } else {
            header.style.setProperty('display', 'none', 'important');
            header.dataset.stepHidden = 'true';
        }
    });

    sectionContents.forEach(content => {
        const key = content.dataset.sectionKey;
        if (!key) return;
        const isStepAllowed = showAll || allowedSections.includes(key);
        const isMultiPartyAllowed = isSectionAllowedByMultiParty(key);

        if (isStepAllowed && isMultiPartyAllowed) {
            delete content.dataset.stepHidden;
            const header = document.querySelector(`.section-header[data-section-key="${key}"]`);
            const isCollapsed = header && header.classList.contains('collapsed');
            content.style.setProperty('display', isCollapsed ? 'none' : 'grid', 'important');
            if (!isCollapsed) {
                content.style.gridTemplateColumns = 'repeat(3, 1fr)';
                content.style.gap = '20px';
            }
        } else {
            content.dataset.stepHidden = 'true';
            content.style.setProperty('display', 'none', 'important');
        }
    });

    // Sync Multi-Party Navigation Bar visibility with active step
    updatePartyNavigation('owner');
    updatePartyNavigation('tenant');
}
window.updateStepVisibility = updateStepVisibility;

function renderReviewSummary(container) {
    const reviewSections = [
        { step: 1, title: 'Agreement & Dates', icon: '📋', keys: ['agreement_dates'] },
        { step: 2, title: 'Property', icon: '🏠', keys: ['property'] },
        { step: 5, title: 'Financial Details', icon: '💰', keys: ['financial'] }
    ];

    for (let index = 1; index <= getOwnerCount(); index++) {
        reviewSections.splice(2 + index - 1, 0, {
            step: 3,
            title: `Owner ${index}`,
            icon: '👤',
            keys: [`owner_${index}`],
            partyType: 'owner',
            partyIndex: index
        });
    }
    const tenantInsertAt = 2 + getOwnerCount();
    for (let index = 1; index <= getTenantCount(); index++) {
        reviewSections.splice(tenantInsertAt + index - 1, 0, {
            step: 4,
            title: `Tenant ${index}`,
            icon: '🔑',
            keys: [`tenant_${index}`],
            partyType: 'tenant',
            partyIndex: index
        });
    }

    container.innerHTML = '';

    const heading = document.createElement('div');
    heading.className = 'sk-review-heading';
    heading.innerHTML = '<div><h2>Review Your Agreement</h2><p>Confirm the details below before generating your document.</p></div>';
    container.appendChild(heading);

    const grid = document.createElement('div');
    grid.className = 'sk-review-grid';

    reviewSections.forEach(section => {
        const card = document.createElement('article');
        card.className = 'sk-review-card';

        const cardHeader = document.createElement('div');
        cardHeader.className = 'sk-review-card-header';
        const title = document.createElement('h3');
        title.textContent = `${section.icon} ${section.title}`;
        const editButton = document.createElement('button');
        editButton.type = 'button';
        editButton.className = 'sk-review-edit-btn';
        editButton.textContent = 'Edit';
        editButton.setAttribute('aria-label', `Edit ${section.title}`);
        editButton.addEventListener('click', () => {
            goToStep(section.step);
            if (section.partyType) scrollToParty(section.partyType, section.partyIndex);
        });
        cardHeader.append(title, editButton);
        card.appendChild(cardHeader);

        const details = document.createElement('dl');
        details.className = 'sk-review-details';
        section.keys.forEach(key => appendSectionSummary(details, key));
        if (!details.children.length) {
            const empty = document.createElement('p');
            empty.className = 'sk-review-empty';
            empty.textContent = 'No details added yet.';
            card.appendChild(empty);
        } else {
            card.appendChild(details);
        }
        grid.appendChild(card);
    });

    grid.appendChild(createAnnexureReviewCard(container));

    container.appendChild(grid);
}

function createAnnexureReviewCard(summaryContainer) {
    const card = document.createElement('article');
    card.className = 'sk-review-card sk-review-annexure-card';

    const cardHeader = document.createElement('div');
    cardHeader.className = 'sk-review-card-header';
    const title = document.createElement('h3');
    title.textContent = '📎 Annexure';
    const editButton = document.createElement('button');
    editButton.type = 'button';
    editButton.className = 'sk-review-edit-btn';
    editButton.textContent = 'Edit';
    editButton.setAttribute('aria-label', 'Edit Annexure');
    cardHeader.append(title, editButton);

    const body = document.createElement('div');
    body.className = 'sk-review-annexure-content';
    const annexureInput = document.getElementById('annexure');
    const annexureText = annexureInput?.value?.trim() || '';
    body.textContent = annexureText ? annexureText.toUpperCase() : 'No annexure details added.';

    editButton.addEventListener('click', () => {
        goToStep(5);
        requestAnimationFrame(() => {
            const field = document.getElementById('annexure');
            if (field) {
                field.scrollIntoView({ behavior: 'smooth', block: 'center' });
                field.focus();
            }
        });
    });

    card.append(cardHeader, body);
    return card;
}

function scrollToParty(type, index) {
    requestAnimationFrame(() => {
        const navId = type === 'owner' ? 'ownerPartyNav' : 'tenantPartyNav';
        const partyPill = document.querySelector(`#${navId} .sk-party-nav-pill[data-party-index="${index}"]`);
        if (partyPill) {
            partyPill.click();
            return;
        }

        const sectionHeader = document.querySelector(`.section-header[data-section-key="${type}_${index}"]`);
        sectionHeader?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
}

function setPreviewVisibilityForStep(stepNumber) {
    const isReview = stepNumber === 6;
    const isUserHidden = document.body.dataset.userPreviewHidden === 'true';

    const shouldHide = isReview || isUserHidden;
    document.body.classList.toggle('preview-hidden', shouldHide);

    const headerPreviewButton = document.getElementById('headerTogglePreviewBtn');
    if (headerPreviewButton) {
        headerPreviewButton.innerHTML = shouldHide
            ? '<span>👁️</span> Preview'
            : '<span>✖</span> Hide Preview';
    }
}

function appendSectionSummary(details, sectionKey) {
    const section = document.querySelector(`.section-content[data-section-key="${sectionKey}"]`);
    if (!section) return;

    section.querySelectorAll('.form-group').forEach(group => {
        const input = group.querySelector('input, select, textarea');
        const label = group.querySelector(':scope > label');
        if (!input || input.id === 'annexure' || input.type === 'hidden' || group.style.display === 'none') return;

        const term = document.createElement('dt');
        term.textContent = (label?.textContent || input.name || 'Detail').replace(/\s+/g, ' ').trim().replace(/\*$/, '').trim();
        const definition = document.createElement('dd');

        if (input.type === 'checkbox') {
            definition.textContent = input.checked ? 'Yes' : 'No';
        } else if (input.tagName === 'SELECT') {
            definition.textContent = input.options[input.selectedIndex]?.text || '—';
        } else {
            definition.textContent = input.value?.trim() || '—';
        }
        details.append(term, definition);
    });
}

function attachNavigationButtons() {
    const buttonGroup = document.querySelector('.button-group');
    if (!buttonGroup || document.getElementById('skWizardNavControls')) return;

    const navControls = document.createElement('div');
    navControls.id = 'skWizardNavControls';
    navControls.className = 'sk-wizard-nav-controls';

    const prevBtn = document.createElement('button');
    prevBtn.type = 'button';
    prevBtn.id = 'skWizardPrevBtn';
    prevBtn.className = 'sk-btn sk-btn-secondary';
    prevBtn.innerHTML = '← Back';
    prevBtn.addEventListener('click', prevStep);

    const nextBtn = document.createElement('button');
    nextBtn.type = 'button';
    nextBtn.id = 'skWizardNextBtn';
    nextBtn.className = 'sk-btn sk-btn-primary';
    nextBtn.innerHTML = 'Next Step →';
    nextBtn.addEventListener('click', nextStep);

    navControls.appendChild(prevBtn);
    navControls.appendChild(nextBtn);

    buttonGroup.parentNode.insertBefore(navControls, buttonGroup);
    updateNavigationButtonStates();
}

function updateNavigationButtonStates() {
    const prevBtn = document.getElementById('skWizardPrevBtn');
    const nextBtn = document.getElementById('skWizardNextBtn');
    const buttonGroup = document.querySelector('.button-group');

    if (prevBtn) {
        prevBtn.style.display = currentStep === 1 ? 'none' : 'inline-flex';
    }
    if (nextBtn) {
        nextBtn.style.display = currentStep === 6 ? 'none' : 'inline-flex';
    }
    // Step 6 shows final save/generate button group
    if (buttonGroup) {
        buttonGroup.style.display = currentStep === 6 ? 'flex' : 'none';
    }
}
