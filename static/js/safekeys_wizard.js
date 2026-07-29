/**
 * safekeys_wizard.js — 6-Step Section Visibility Controller (Sprint 2.2)
 * =========================================================================
 * Pure visibility orchestrator that maps existing registry section cards
 * into 6 clean step views without altering form data, validation, or backend logic.
 */

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

    // Create Stepper Bar if not already present
    let stepperContainer = document.getElementById('skWizardStepper');
    if (!stepperContainer) {
        stepperContainer = document.createElement('div');
        stepperContainer.id = 'skWizardStepper';
        stepperContainer.className = 'sk-wizard-stepper';
        formFields.parentNode.insertBefore(stepperContainer, formFields);
    }

    renderStepperBar(stepperContainer);
    updateStepVisibility(currentStep);
    attachNavigationButtons();
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
    currentStep = stepNumber;

    // Update active pill styling
    const pills = document.querySelectorAll('.sk-wizard-step-pill');
    pills.forEach(pill => {
        const s = parseInt(pill.dataset.step, 10);
        pill.classList.toggle('active', s === currentStep);
    });

    updateStepVisibility(currentStep);
    updateNavigationButtonStates();

    // Smooth scroll back to top of form container on step change
    const container = document.querySelector('.container');
    if (container) {
        container.scrollTop = 0;
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

function updateStepVisibility(activeStep) {
    const sectionHeaders = document.querySelectorAll('.section-header');
    const sectionContents = document.querySelectorAll('.section-content');

    const allowedSections = WIZARD_STEP_MAP[activeStep] || [];
    const showAll = allowedSections.includes('ALL');

    sectionHeaders.forEach(header => {
        const key = header.dataset.sectionKey;
        if (showAll || allowedSections.includes(key)) {
            header.style.display = 'flex';
        } else {
            header.style.display = 'none';
        }
    });

    sectionContents.forEach(content => {
        const key = content.dataset.sectionKey;
        if (showAll || allowedSections.includes(key)) {
            // Respect collapse state
            const header = document.querySelector(`.section-header[data-section-key="${key}"]`);
            const isCollapsed = header && header.classList.contains('collapsed');
            content.style.display = isCollapsed ? 'none' : 'grid';
        } else {
            content.style.display = 'none';
        }
    });
}

function attachNavigationButtons() {
    const buttonGroup = document.querySelector('.button-group');
    if (!buttonGroup || document.getElementById('skWizardNavControls')) return;

    const navControls = document.createElement('div');
    navControls.id = 'skWizardNavControls';
    navControls.style.cssText = 'display: flex; gap: 12px; align-items: center; width: 100%; margin-bottom: 16px;';

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
