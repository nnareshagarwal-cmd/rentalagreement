/**
 * renderer.js — Registry-Driven Generic Form Renderer (Exact Backup Styling)
 * ===========================================================================
 * Restores original 3-column grid layout with gradient purple section header banners:
 * background: linear-gradient(90deg, #667eea 0%, #764ba2 100%)
 */

export function createFieldElement(fieldDef, value = '') {
    const group = document.createElement('div');
    group.className = 'form-group';
    group.id = `form-group-${fieldDef.key}`;
    
    if (fieldDef.wide) {
        group.classList.add('wide-field');
        group.style.gridColumn = 'span 2';
    }
    if (fieldDef.type === 'hidden') {
        group.style.display = 'none';
    }

    if (fieldDef.type !== 'hidden') {
        const label = document.createElement('label');
        label.setAttribute('for', fieldDef.key);
        label.style.cursor = fieldDef.type === 'checkbox' ? 'pointer' : 'default';
        label.innerHTML = `${fieldDef.emoji} ${fieldDef.label} ${fieldDef.required ? '*' : ''}`;

        if (fieldDef.key.includes('owner') && fieldDef.key.includes('address')) {
            label.style.display = 'flex';
            label.style.alignItems = 'center';
            label.style.justifyContent = 'space-between';
            
            const sameAsWrapper = document.createElement('label');
            sameAsWrapper.style.cssText = 'font-size:11px; font-weight:normal; color:#4f46e5; cursor:pointer; display:inline-flex; align-items:center; gap:4px; margin:0;';
            
            const sameAsCheckbox = document.createElement('input');
            sameAsCheckbox.type = 'checkbox';
            sameAsCheckbox.id = `same_as_rental_${fieldDef.key}`;
            sameAsCheckbox.style.cursor = 'pointer';
            
            sameAsWrapper.appendChild(sameAsCheckbox);
            sameAsWrapper.appendChild(document.createTextNode('Same as Rental Property Address'));
            
            label.appendChild(sameAsWrapper);
        }

        group.appendChild(label);
    }

    let inputEl;

    switch (fieldDef.type) {
        case 'textarea':
            inputEl = document.createElement('textarea');
            inputEl.rows = fieldDef.rows || 3;
            inputEl.setAttribute('spellcheck', 'true');
            break;
        case 'select':
        case 'select_dynamic':
            inputEl = document.createElement('select');
            if (fieldDef.options) {
                fieldDef.options.forEach(opt => {
                    const option = document.createElement('option');
                    option.value = opt;
                    option.textContent = opt;
                    if (opt === value) option.selected = true;
                    inputEl.appendChild(option);
                });
            }
            break;
        case 'checkbox':
            inputEl = document.createElement('input');
            inputEl.type = 'checkbox';
            inputEl.checked = value === true || value === 'true' || value === 'Yes' || value === 'on';
            inputEl.style.cursor = 'pointer';
            break;
        default:
            inputEl = document.createElement('input');
            inputEl.type = fieldDef.type || 'text';
            break;
    }

    inputEl.id = fieldDef.key;
    inputEl.name = fieldDef.key;
    if (/^(owner|tenant)\d+_phone$/.test(fieldDef.key)) {
        inputEl.type = 'tel';
        inputEl.inputMode = 'numeric';
        inputEl.maxLength = 12; // 10 digits plus the two display hyphens
        inputEl.pattern = '[0-9]{4}-[0-9]{3}-[0-9]{3}';
        inputEl.placeholder = '1234-567-890';
        inputEl.title = 'Enter a 10-digit phone number in the format 1234-567-890';
    }
    if (fieldDef.type !== 'checkbox' && value !== undefined && value !== null) {
        inputEl.value = (typeof value === 'string' && fieldDef.type !== 'date' && fieldDef.key !== 'annexure') ? value.toUpperCase() : value;
    }
    if (fieldDef.required) inputEl.required = true;
    if (fieldDef.readonly && fieldDef.type !== 'checkbox') inputEl.readOnly = true;

    group.appendChild(inputEl);

    if (fieldDef.hint) {
        const hintEl = document.createElement('small');
        hintEl.className = 'field-hint';
        hintEl.style.cssText = 'display:block; font-size:11px; color:#64748b; margin-top:2px;';
        hintEl.textContent = fieldDef.hint;
        group.appendChild(hintEl);
    }

    return group;
}

export function renderSectionHeader(sectionKey, sectionTitle) {
    const header = document.createElement('div');
    header.className = 'section-header';
    header.style.gridColumn = '1 / -1';
    header.dataset.sectionKey = sectionKey;

    const titleGroup = document.createElement('div');
    titleGroup.className = 'section-title-group';
    titleGroup.style.cssText = 'display: flex; align-items: center; gap: 8px; font-weight: 700;';

    const chevron = document.createElement('span');
    chevron.className = 'section-toggle-icon';
    chevron.style.cssText = 'display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; transition: transform 200ms cubic-bezier(0.4, 0, 0.2, 1);';
    chevron.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>';

    const titleText = document.createElement('span');
    titleText.className = 'section-title-text';
    titleText.textContent = sectionTitle;

    titleGroup.appendChild(chevron);
    titleGroup.appendChild(titleText);
    header.appendChild(titleGroup);

    const sectionContent = document.createElement('div');
    sectionContent.className = 'section-content';
    sectionContent.style.gridColumn = '1 / -1';
    sectionContent.style.display = 'grid';
    sectionContent.style.gridTemplateColumns = 'repeat(3, 1fr)';
    sectionContent.style.gap = '20px';
    sectionContent.dataset.sectionKey = sectionKey;

    header.addEventListener('click', () => {
        const isCollapsed = header.classList.toggle('collapsed');
        if (isCollapsed) {
            sectionContent.style.display = 'none';
            chevron.style.transform = 'rotate(-90deg)';
        } else {
            sectionContent.style.display = 'grid';
            chevron.style.transform = 'rotate(0deg)';
        }
    });

    return { header, sectionContent };
}
