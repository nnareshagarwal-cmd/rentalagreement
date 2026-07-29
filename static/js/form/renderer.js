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
    
    if (fieldDef.wide || fieldDef.type === 'textarea') {
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
    if (fieldDef.type !== 'checkbox' && value !== undefined && value !== null) {
        inputEl.value = value;
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

    const icon = document.createElement('span');
    icon.className = 'section-toggle-icon';
    icon.textContent = '▼';

    const title = document.createElement('span');
    title.textContent = sectionTitle;

    header.appendChild(icon);
    header.appendChild(title);

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
            icon.textContent = '▶';
        } else {
            sectionContent.style.display = 'grid';
            icon.textContent = '▼';
        }
    });

    return { header, sectionContent };
}
