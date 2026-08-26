/**
 * preview_sync.js — Smart Live Preview Synchronization Engine (Sprint 2.2C)
 * ===========================================================================
 * Direct Field Key -> Document Clause / Paragraph Map
 *
 * Synchronizes form fields on the left with preview document paragraphs on the right.
 * Works deterministically for both Simple Rental and Leave & License agreements.
 * Includes UX Experiment: Active Field Preview Pill.
 */

let lastScrolledParagraph = null;
let highlightTimer = null;

/**
 * Configuration Flag for UX Experiment - Active Field Preview Pill
 * Set to false or add body.disable-preview-pill to turn off easily.
 */
export let ENABLE_ACTIVE_FIELD_PILL = true;
let activePillElement = null;

/**
 * Remove active pill highlight from preview document.
 */
export function removeActiveFieldPill() {
    if (activePillElement) {
        activePillElement.classList.remove('sk-preview-value-pill');
        activePillElement = null;
    }
    document.querySelectorAll('.sk-preview-value-pill').forEach(el => {
        el.classList.remove('sk-preview-value-pill');
    });
}

/**
 * Apply pill styling to the single dynamic value element matching fieldEl.
 * @param {HTMLElement} fieldEl 
 */
export function applyActiveFieldPill(fieldEl) {
    if (!ENABLE_ACTIVE_FIELD_PILL) return;
    if (!fieldEl) return;

    removeActiveFieldPill(); // Ensure ONLY ONE pill is ever visible

    const previewPane = document.getElementById('previewPane') || document.getElementById('previewContent');
    if (!previewPane) return;

    const fieldKey = (fieldEl.id || fieldEl.name || '').toLowerCase();
    const val = (fieldEl.value || '').trim();

    const targetParagraph = getTargetParagraphForFieldKey(fieldKey, previewPane);
    if (!targetParagraph) return;

    // Locate dynamic value bold element(s) inside targetParagraph
    const bElements = Array.from(targetParagraph.querySelectorAll('b, strong')).filter(b => {
        const txt = b.textContent.trim();
        return txt !== 'BETWEEN' && txt !== 'AND';
    });
    if (bElements.length === 0) return;

    let pillTarget = null;

    // Strategy A: Match with field's current value inside b elements
    if (val.length >= 2) {
        const valUpper = val.toUpperCase();
        pillTarget = bElements.find(b => {
            const txt = b.textContent.trim().toUpperCase();
            return txt === valUpper || (valUpper.length >= 4 && txt.includes(valUpper));
        });
    }

    // Strategy B: Preamble Line Matching for Owner / Tenant Particulars
    if (!pillTarget && (fieldKey.includes('owner') || fieldKey.includes('tenant'))) {
        if (fieldKey.includes('name')) {
            pillTarget = bElements.find(b => {
                const p = b.parentElement;
                return p && (p.textContent.includes('Name:') || b.previousSibling?.textContent?.includes('Name:'));
            }) || bElements[0];
        } else if (fieldKey.includes('age')) {
            pillTarget = bElements.find(b => {
                const p = b.parentElement;
                return p && (p.textContent.includes('Age:') || b.previousSibling?.textContent?.includes('Age:'));
            });
        } else if (fieldKey.includes('careof') || fieldKey.includes('father') || fieldKey.includes('husband')) {
            pillTarget = bElements.find(b => {
                const p = b.parentElement;
                return p && (p.textContent.includes('/o:') || p.textContent.includes('S/o:') || p.textContent.includes('H/o:') || p.textContent.includes('W/o:'));
            });
        } else if (fieldKey.includes('occupation')) {
            pillTarget = bElements.find(b => {
                const p = b.parentElement;
                return p && (p.textContent.includes('Occupation:') || b.previousSibling?.textContent?.includes('Occupation:'));
            });
        } else if (fieldKey.includes('address')) {
            pillTarget = bElements.find(b => {
                const p = b.parentElement;
                return p && (p.textContent.includes('Address:') || b.previousSibling?.textContent?.includes('Address:'));
            });
        }
    }

    // Strategy B2: Date Field Exact Element Matching for start_date, end_date, lockin_end_date
    if (!pillTarget && (fieldKey.includes('date') || fieldKey === 'p1' || fieldKey === 'p16' || fieldKey === 'p17')) {
        const dateBElements = bElements.filter(b => {
            const txt = (b && b.textContent ? b.textContent : '').toLowerCase();
            return txt.includes('day of') || 
                   /\b(january|february|march|april|may|june|july|august|september|october|november|december)\b/.test(txt) || 
                   /\b20\d{2}\b/.test(txt);
        });

        if (dateBElements.length > 0) {
            if (fieldKey.includes('start_date') || fieldKey === 'p16') {
                pillTarget = dateBElements[0];
            } else if (fieldKey.includes('lockin_end_date')) {
                pillTarget = dateBElements[dateBElements.length - 1];
            } else if (fieldKey.includes('end_date') || fieldKey === 'p17') {
                pillTarget = dateBElements.length >= 2 ? dateBElements[1] : dateBElements[0];
            } else if (fieldKey === 'agreement_date' || fieldKey === 'p1') {
                pillTarget = dateBElements[0];
            }
        }
    }

    // Strategy B3: Penalty Deduction Exact Element Matching (e.g. "60 days")
    if (!pillTarget && (fieldKey.includes('penalty') || fieldKey === 'p22')) {
        pillTarget = bElements.find(b => {
            const txt = (b && b.textContent ? b.textContent : '').trim().toLowerCase();
            if (txt.includes('day of')) return false; // Exclude date runs like "6th day of August"
            if (val && (txt === val.toLowerCase() || txt.startsWith(val.toLowerCase()))) return true;
            return /\b\d+\s*days?\b/i.test(txt) || txt.includes('deduct');
        });
    }

    // Strategy B4: Property Address & Property Block / Type Matching
    if (!pillTarget && (fieldKey.includes('property') || fieldKey.includes('block') || fieldKey.includes('society') || fieldKey === 'p12')) {
        pillTarget = bElements.find(b => {
            const txt = b.textContent.trim();
            return txt.length > 3 && !txt.includes('Name:') && !txt.includes('Age:') && !txt.includes('Occupation:');
        }) || bElements[0];
    }

    // Strategy B5: Same as Property Address Checkbox Matching
    if (!pillTarget && (fieldKey.includes('same_as') || fieldKey.includes('sameas') || fieldKey.includes('same_as_rental'))) {
        pillTarget = bElements.find(b => {
            const p = b.parentElement;
            return p && (p.textContent.includes('Address:') || b.previousSibling?.textContent?.includes('Address:'));
        }) || bElements[bElements.length - 1];
    }

    // Strategy B6: Rent Increase Type & Value Matching
    if (!pillTarget && (fieldKey.includes('increase') || fieldKey.includes('escalation') || fieldKey === 'p18')) {
        pillTarget = bElements.find(b => {
            const txt = b.textContent.trim();
            return txt.includes('%') || /\b\d+\s*%/i.test(txt) || txt.toLowerCase().includes('percent') || txt.toLowerCase().includes('escalation') || /\b\d+\b/.test(txt);
        }) || bElements[0];
    }

    // Strategy C: Fallback to dynamic value b element (excluding clause numbers & section titles)
    if (!pillTarget) {
        pillTarget = bElements.find(b => {
            const txt = (b && b.textContent ? b.textContent : '').trim();
            const isClauseNum = /^\d+\.$/.test(txt);
            const isHeading = txt.endsWith(':') || txt.toUpperCase() === 'GRANT OF LICENCE' || txt === 'BETWEEN' || txt === 'AND';
            return !isClauseNum && !isHeading;
        }) || bElements[bElements.length - 1];
    }

    if (pillTarget && pillTarget.classList) {
        pillTarget.classList.add('sk-preview-value-pill');
        activePillElement = pillTarget;
    }
}

/**
 * Check whether an element is currently within the visible vertical bounds of its scroll container.
 * @param {HTMLElement} el 
 * @param {HTMLElement} container 
 * @returns {boolean}
 */
export function isElementVisibleInContainer(el, container) {
    if (!el || !container) return false;
    const elRect = el.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();

    // Buffer check to keep elements comfortably inside optimal viewport zone
    const isAbove = elRect.bottom < containerRect.top + 20;
    const isBelow = elRect.bottom > containerRect.bottom - 60;

    return !isAbove && !isBelow;
}

/**
 * Smoothly scroll container so that target paragraph rests comfortably in upper-middle view.
 * @param {HTMLElement} el 
 * @param {HTMLElement} container 
 * @param {number} offset 
 */
export function scrollToTargetParagraph(el, container, offset = -40) {
    if (!el || !container) return;
    const elRect = el.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    const relativeTop = (elRect.top - containerRect.top) + container.scrollTop;

    // Position top of paragraph at 25% down from container top for comfortable viewing
    const targetScrollTop = Math.max(0, relativeTop - (container.clientHeight * 0.25) + offset);

    container.scrollTo({
        top: targetScrollTop,
        behavior: 'smooth'
    });
}

/**
 * Briefly highlight a target paragraph (1.5s pulse animation).
 * @param {HTMLElement} paragraphEl 
 */
export function highlightParagraph(paragraphEl) {
    if (!paragraphEl) return;

    document.querySelectorAll('.sk-preview-highlight').forEach(el => {
        el.classList.remove('sk-preview-highlight');
    });

    if (highlightTimer) {
        clearTimeout(highlightTimer);
        highlightTimer = null;
    }

    void paragraphEl.offsetWidth; // Force reflow for animation restart
    paragraphEl.classList.add('sk-preview-highlight');

    highlightTimer = setTimeout(() => {
        paragraphEl.classList.remove('sk-preview-highlight');
    }, 1500);
}

/**
 * Direct mapping between form field key and document clause / paragraph element.
 * Works for both Simple Rental and Leave & License formats.
 * @param {string} fieldKey 
 * @param {HTMLElement} previewPane 
 * @returns {HTMLElement|null}
 */
export function getTargetParagraphForFieldKey(fieldKey, previewPane) {
    const key = (fieldKey || '').toLowerCase();

    // Notice Period has a precise, stable clause in both document templates.
    if (key === 'notice_period' || key === 'p23') {
        return previewPane.querySelector('[data-clause-id="clause_36"]') ||
            previewPane.querySelector('[data-clause-id="notice_period"]');
    }

    // Collect ALL clause blocks and preamble paragraphs in document order
    const blocks = Array.from(previewPane.querySelectorAll('.clause-block, p.clause-text, p, div')).filter(b => b.textContent && b.textContent.trim().length > 0);
    if (blocks.length === 0) return null;

    // 1. Lock-in & Penalty fields (lockin, lockin_months, lockin_end_date, penalty_deduction, p22)
    if (key.includes('lockin') || key.includes('lock_in') || key.includes('penalty') || key === 'p22') {
        return blocks.find(b => 
            b.dataset?.clauseId === 'lock_in' || 
            b.dataset?.clauseId === 'lockin' || 
            b.dataset?.clauseId === 'clause_29' ||
            b.textContent.toUpperCase().includes('LOCK IN') ||
            b.textContent.toUpperCase().includes('LOCK-IN') ||
            b.textContent.toLowerCase().includes('minimum tenure') ||
            b.textContent.toLowerCase().includes('moves out before') ||
            b.textContent.toLowerCase().includes('deducted')
        ) || null;
    }

    // 2. Rent Increase / Escalation fields (increase_percent, rent_increase_type, rent_increase_value, p18)
    if (key.includes('increase') || key.includes('escalation') || key === 'p18') {
        return blocks.find(b => 
            b.dataset?.clauseId === 'escalation' || 
            b.dataset?.clauseId === 'renewal' || 
            b.dataset?.clauseId === 'grant_of_licence' || 
            b.dataset?.clauseId === 'clause_26' ||
            b.textContent.toLowerCase().includes('escalation') ||
            b.textContent.toLowerCase().includes('increment') ||
            b.textContent.toLowerCase().includes('increase of') ||
            b.textContent.toLowerCase().includes('option for renewal') ||
            b.textContent.toLowerCase().includes('renewed') ||
            b.textContent.toLowerCase().includes('present rent')
        ) || blocks.find(b => b.textContent.toLowerCase().includes('11 months')) || null;
    }

    // 3. Rent / Financial fields (monthly_rent, rent_words)
    if (key.includes('rent') || key.includes('monthly_rent') || key === 'p13' || key === 'p14') {
        return blocks.find(b => 
            b.dataset?.clauseId === 'license_charges___compensation' || 
            b.dataset?.clauseId === 'clause_25' || 
            b.dataset?.clauseId === 'payment_of_license_charges' ||
            b.textContent.toUpperCase().includes('MONTHLY RENT') ||
            b.textContent.toUpperCase().includes('ADVANCE MONTHLY RENT') ||
            b.textContent.toUpperCase().includes('LICENSE CHARGES') ||
            b.textContent.toUpperCase().includes('COMPENSATION')
        ) || null;
    }

    // 4. Security Deposit fields (security_deposit, deposit_words)
    if (key.includes('deposit') || key === 'p19' || key === 'p20') {
        return blocks.find(b => 
            b.dataset?.clauseId === 'security_deposit' || 
            b.dataset?.clauseId === 'clause_27' ||
            b.textContent.toUpperCase().includes('SECURITY DEPOSIT') ||
            b.textContent.toLowerCase().includes('interest free amount')
        ) || null;
    }

    // 4a. Annexure
    if (key.includes('annexure')) {
        return blocks.find(b => b.dataset?.clauseId === 'annexure') || null;
    }

    // 5. Maintenance
    if (key.includes('maintenance')) {
        return blocks.find(b => 
            b.dataset?.clauseId === 'apartment_complex_or_society_maintenance' || 
            b.dataset?.clauseId === 'clause_30' ||
            b.textContent.toUpperCase().includes('MAINTENANCE')
        ) || null;
    }

    // 6a. Today's Date (agreement_date / P1) -> Preamble at the top of document
    if (key === 'agreement_date' || key === 'p1') {
        return blocks.find(b => b.textContent.includes('THIS') && (b.textContent.includes('AGREEMENT') || b.textContent.includes('EXECUTED') || b.textContent.includes('LICENCE'))) || blocks[0];
    }

    // 6b. Start / End Date & Tenure -> Targets main clause (GRANT OF LICENCE or term of agreement)
    if (key.includes('start_date') || key.includes('end_date') || key === 'p16' || key === 'p17') {
        return blocks.find(b => 
            b.dataset?.clauseId === 'grant_of_licence' || 
            b.dataset?.clauseId === 'clause_26'
        ) || blocks.find(b => 
            b.textContent.toUpperCase().includes('GRANT OF LICENCE') ||
            b.textContent.toLowerCase().includes('term of rental agreement') ||
            b.textContent.toLowerCase().includes('term of 11 months') ||
            b.textContent.toLowerCase().includes('commencing from')
        ) || null;
    }

    // 7. Property Address & Details (property_type, property_block, property_no, society_name, property_city, property_address)
    if (key.includes('property') || key.includes('society') || key.includes('block') || (key.includes('address') && !key.includes('owner') && !key.includes('tenant')) || key === 'p12') {
        return blocks.find(b => 
            b.textContent.includes('located at') || 
            b.textContent.includes('bearing address') || 
            b.textContent.includes('SAID PREMISES') ||
            b.textContent.includes('possessed of the premises') ||
            b.textContent.includes('lawful and legal owner')
        ) || blocks.find(b => b.textContent.includes('premises')) || blocks[0];
    }

    // 7b. Same as Rental Property Address Checkboxes
    if (key.includes('same_as') || key.includes('sameas')) {
        if (key.includes('owner')) {
            const ownerNum = parseInt(key.match(/owner(\d+)/)?.[1] || '1', 10);
            const betweenIndex = blocks.findIndex(b => b.textContent.trim().toUpperCase() === 'BETWEEN');
            const andIndex = blocks.findIndex(b => b.textContent.trim().toUpperCase() === 'AND');

            const ownerParticulars = blocks.filter((b, idx) => {
                const txt = b.textContent;
                const isHeader = txt.trim() === 'BETWEEN' || txt.trim() === 'AND';
                const afterBetween = betweenIndex !== -1 ? idx > betweenIndex : true;
                const beforeAnd = andIndex !== -1 ? idx < andIndex : true;
                return !isHeader && afterBetween && beforeAnd && (txt.includes('Name:') || txt.includes('Address:') || txt.includes('Occupation:'));
            });
            return ownerParticulars[ownerNum - 1] || ownerParticulars[0] || blocks[0];
        }
        if (key.includes('tenant')) {
            const tenantNum = parseInt(key.match(/tenant(\d+)/)?.[1] || '1', 10);
            const andIndex = blocks.findIndex(b => b.textContent.trim().toUpperCase() === 'AND');

            const tenantParticulars = blocks.filter((b, idx) => {
                const txt = b.textContent;
                const isHeader = txt.trim() === 'BETWEEN' || txt.trim() === 'AND';
                const afterAnd = andIndex !== -1 ? idx > andIndex : true;
                return !isHeader && afterAnd && (txt.includes('Name:') || txt.includes('Address:') || txt.includes('Occupation:'));
            });
            return tenantParticulars[tenantNum - 1] || tenantParticulars[0] || blocks[1] || blocks[0];
        }
    }

    // 10. Bachelor Specific Fields
    if (key.includes('bachelor') || key.includes('gender') || key.includes('poc')) {
        return blocks.find(b => 
            b.dataset.clauseId === 'single_point_of_contact' ||
            b.dataset.clauseId === 'opposite_gender' ||
            b.dataset.clauseId === 'clause_32' ||
            b.dataset.clauseId === 'clause_33' ||
            b.textContent.toUpperCase().includes('ROOMMATES') ||
            b.textContent.toUpperCase().includes('POINT OF CONTACT')
        ) || null;
    }

    return null;
}

/**
 * Synchronize preview pane to the specified field element.
 * @param {HTMLElement} fieldEl 
 */
export function syncPreviewToField(fieldEl) {
    const previewPane = document.getElementById('previewPane');
    if (!previewPane || !fieldEl) return;

    const fieldKey = (fieldEl.id || fieldEl.name || '').toLowerCase();

    // Special behavior for Lock-in Checkbox:
    // If unchecked -> scroll back to top of document preview pane
    if (fieldKey.includes('lockin') && fieldEl.type === 'checkbox') {
        if (!fieldEl.checked) {
            previewPane.scrollTo({ top: 0, behavior: 'smooth' });
            lastScrolledParagraph = null;
            removeActiveFieldPill();
            const topHeader = previewPane.querySelector('.clause-block, h2, p.clause-text');
            if (topHeader) highlightParagraph(topHeader);
            return;
        }
    }

    // Direct mapping lookup
    const targetParagraph = getTargetParagraphForFieldKey(fieldKey, previewPane);
    if (!targetParagraph) return;

    const isVisible = isElementVisibleInContainer(targetParagraph, previewPane);

    // Smooth scroll if paragraph is not in optimal viewport zone or active paragraph changed
    if (!isVisible || lastScrolledParagraph !== targetParagraph) {
        scrollToTargetParagraph(targetParagraph, previewPane);
        lastScrolledParagraph = targetParagraph;
    }

    // Briefly highlight the paragraph (1.5 seconds)
    highlightParagraph(targetParagraph);

    // Apply active field preview pill
    applyActiveFieldPill(fieldEl);
}

/**
 * Attaches blur, focus and input listeners to form fields for active pill styling.
 * @param {HTMLFormElement} form 
 */
let currentActiveField = null;

export function setupFormPreviewSync(form) {
    if (!form) return;

    setupPreviewNavControls();

    form.addEventListener('focusin', (e) => {
        if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT')) {
            currentActiveField = e.target;
            syncPreviewToField(e.target);
        }
    }, true);

    form.addEventListener('focusout', (e) => {
        if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT')) {
            setTimeout(() => {
                const active = document.activeElement;
                if (!active || (active.tagName !== 'INPUT' && active.tagName !== 'TEXTAREA' && active.tagName !== 'SELECT')) {
                    removeActiveFieldPill();
                    currentActiveField = null;
                }
            }, 50);
        }
    }, true);

    form.addEventListener('input', (e) => {
        if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT')) {
            currentActiveField = e.target;
            applyActiveFieldPill(e.target);
        }
    }, true);
}

/**
 * Synchronize document preview pane when user switches wizard steps (1..6).
 * @param {number} stepNumber 
 */
export function syncPreviewToStep(stepNumber) {
    const previewPane = document.getElementById('previewPane') || document.getElementById('previewContent');
    if (!previewPane) return;

    removeActiveFieldPill();

    if (stepNumber === 1) {
        // Step 1: Agreement & Dates -> Top of document
        previewPane.scrollTo({ top: 0, behavior: 'smooth' });
        const topBlock = previewPane.querySelector('.clause-block, h2, p.clause-text');
        if (topBlock) highlightParagraph(topBlock);
        return;
    }

    if (stepNumber === 6) {
        // Step 6: Review & Generate -> Bottom of document
        previewPane.scrollTo({ top: previewPane.scrollHeight, behavior: 'smooth' });
        const lastBlock = previewPane.querySelector('.clause-block:last-child, p.clause-text:last-child');
        if (lastBlock) highlightParagraph(lastBlock);
        return;
    }

    let targetKey = '';
    if (stepNumber === 2) targetKey = 'property';
    else if (stepNumber === 3) targetKey = 'owner1_name';
    else if (stepNumber === 4) targetKey = 'tenant1_name';
    else if (stepNumber === 5) targetKey = 'monthly_rent';

    const targetParagraph = getTargetParagraphForFieldKey(targetKey, previewPane);
    if (targetParagraph) {
        scrollToTargetParagraph(targetParagraph, previewPane);
        highlightParagraph(targetParagraph);
    }
}

export function setupPreviewNavControls() {
    const previewPane = document.getElementById('previewPane');
    const topBtn = document.getElementById('skNavTopBtn');
    const clauseBtn = document.getElementById('skNavClauseBtn');
    const bottomBtn = document.getElementById('skNavBottomBtn');

    if (!previewPane) return;

    const updateNavVisibility = () => {
        const scrollTop = previewPane.scrollTop;
        const scrollHeight = previewPane.scrollHeight;
        const clientHeight = previewPane.clientHeight;

        if (topBtn) {
            topBtn.style.display = scrollTop > 80 ? 'inline-flex' : 'none';
        }
        if (bottomBtn) {
            bottomBtn.style.display = (scrollTop + clientHeight < scrollHeight - 80) ? 'inline-flex' : 'none';
        }
        if (clauseBtn) {
            const hasActive = currentActiveField && document.body.contains(currentActiveField);
            clauseBtn.style.display = hasActive ? 'inline-flex' : 'none';
        }
    };

    if (topBtn) {
        topBtn.addEventListener('click', () => {
            previewPane.scrollTo({ top: 0, behavior: 'smooth' });
        });
    }

    if (bottomBtn) {
        bottomBtn.addEventListener('click', () => {
            previewPane.scrollTo({ top: previewPane.scrollHeight, behavior: 'smooth' });
        });
    }

    if (clauseBtn) {
        clauseBtn.addEventListener('click', () => {
            if (currentActiveField) {
                syncPreviewToField(currentActiveField);
            }
        });
    }

    previewPane.addEventListener('scroll', updateNavVisibility, { passive: true });

    document.addEventListener('focusin', () => {
        setTimeout(updateNavVisibility, 50);
    }, true);

    document.addEventListener('focusout', () => {
        setTimeout(updateNavVisibility, 100);
    }, true);

    updateNavVisibility();
}
