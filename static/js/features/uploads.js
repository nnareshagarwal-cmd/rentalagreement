/**
 * uploads.js — Aadhaar AI OCR Upload & Automatic Form Auto-Fill
 * ==============================================================
 */

export function attachAadhaarOcrHandlers(partyType = 'owner1', onAutoFillComplete) {
    const sectionCard = document.querySelector(`[data-section-key="${partyType}"]`);
    if (!sectionCard) return;

    const contentDiv = sectionCard.querySelector('.section-content');
    if (!contentDiv) return;

    const existingBtn = sectionCard.querySelector('.aadhaar-ocr-btn');
    if (existingBtn) return;

    const ocrContainer = document.createElement('div');
    ocrContainer.className = 'form-group wide';
    ocrContainer.style.cssText = 'background: #f0f9ff; border: 1px dashed #0284c7; padding: 12px; border-radius: 8px; margin-bottom: 15px;';
    
    ocrContainer.innerHTML = `
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap;">
            <div>
                <span style="font-weight: 700; font-size: 13px; color: #0369a1;">🪪 Upload Aadhaar Card (AI Auto-Fill)</span>
                <p style="margin: 2px 0 0 0; font-size: 11px; color: #0284c7;">Upload front/back Aadhaar card image to auto-populate Name, Age, Care-of, and Address instantly.</p>
            </div>
            <label class="aadhaar-ocr-btn" style="background: #0284c7; color: white; padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px;">
                📷 Choose Image
                <input type="file" class="aadhaar-ocr-input" accept="image/*" style="display: none;" />
            </label>
        </div>
        <div class="ocr-status-msg" style="display: none; margin-top: 8px; font-size: 11px; font-weight: 600; color: #0369a1;"></div>
    `;

    contentDiv.insertBefore(ocrContainer, contentDiv.firstChild);

    const fileInput = ocrContainer.querySelector('.aadhaar-ocr-input');
    const statusMsg = ocrContainer.querySelector('.ocr-status-msg');

    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        statusMsg.style.display = 'block';
        statusMsg.textContent = '⚡ Extracting details using Gemini AI OCR...';

        const formData = new FormData();
        formData.append('file', file);

        try {
            const res = await fetch('/api/ocr/aadhaar', {
                method: 'POST',
                body: formData
            });

            const data = await res.json();
            if (data.success && data.extracted) {
                const ext = data.extracted;
                autoFillPartyFields(partyType, ext);
                statusMsg.style.color = '#15803d';
                statusMsg.textContent = '✓ Aadhaar details auto-filled successfully!';
                if (onAutoFillComplete) onAutoFillComplete();
            } else {
                throw new Error('OCR extraction failed');
            }
        } catch (err) {
            statusMsg.style.color = '#b91c1c';
            statusMsg.textContent = '⚠️ OCR extraction failed. Please enter details manually.';
            console.error('[OCR Error]', err);
        }
    });
}

function autoFillPartyFields(partyType, extracted) {
    const isOwner = partyType.startsWith('owner');
    const pfxKey = `${partyType}_prefix`;
    const nameKey = `${partyType}_name`;
    const ageKey = `${partyType}_age`;
    const careofKey = `${partyType}_careof`;
    const careofNameKey = `${partyType}_careofname`;
    const addrKey = `${partyType}_address`;

    if (extracted.full_name) {
        const nameEl = document.getElementById(nameKey) || (isOwner ? document.getElementById('P2') : document.getElementById('P7'));
        if (nameEl) nameEl.value = extracted.full_name;
    }

    if (extracted.relation_name) {
        const cnameEl = document.getElementById(careofNameKey) || (isOwner ? document.getElementById('P4') : document.getElementById('P9'));
        if (cnameEl) cnameEl.value = extracted.relation_name;
    }

    if (extracted.relation_type) {
        const careofEl = document.getElementById(careofKey) || (isOwner ? document.getElementById('P24') : document.getElementById('P25'));
        if (careofEl) {
            const rel = extracted.relation_type.toUpperCase();
            if (rel.includes('W')) careofEl.value = 'Husband Name';
            else careofEl.value = 'Father Name';
        }
    }

    if (extracted.date_of_birth) {
        const dob = new Date(extracted.date_of_birth);
        if (!isNaN(dob.getTime())) {
            const age = new Date().getFullYear() - dob.getFullYear();
            const ageEl = document.getElementById(ageKey) || (isOwner ? document.getElementById('P3') : document.getElementById('P8'));
            if (ageEl) ageEl.value = String(age);
        }
    }

    const fullAddr = [extracted.address_line1, extracted.locality, extracted.city, extracted.state, extracted.pincode]
        .filter(Boolean)
        .join(', ');

    if (fullAddr) {
        const addrEl = document.getElementById(addrKey) || (isOwner ? document.getElementById('P6') : document.getElementById('P11'));
        if (addrEl) addrEl.value = fullAddr.toUpperCase();
    }

    // Trigger change event to update preview
    const nameEl = document.getElementById(nameKey) || (isOwner ? document.getElementById('P2') : document.getElementById('P7'));
    if (nameEl) nameEl.dispatchEvent(new Event('input', { bubbles: true }));
}
