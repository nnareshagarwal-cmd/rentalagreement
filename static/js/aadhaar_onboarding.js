const partyData = { owner: null, tenant: null };
let agreementType = 'simple_rental';

function escapeHtml(value = '') { return String(value).replace(/[&<>"']/g, char => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;', "'":'&#039;' }[char])); }

function renderReviewCard(party, extracted) {
  const result = document.getElementById(`${party}Result`);
  // Combine address parts into a single field
  const addrParts = [extracted.address_line1, extracted.locality, extracted.city, extracted.state, extracted.pincode].filter(Boolean);
  extracted.full_address = addrParts.join(', ');
  const fields = [['full_name','Full name'],['relation_name','Father / husband name'],['date_of_birth','Date of birth'],['aadhaar_masked','Aadhaar number'],['full_address','Address']];
  result.innerHTML = `<span class="review-chip">✓ Extracted - review before continuing</span><div class="review-fields">${fields.map(([key,label]) => `<label class="${key === 'full_address' ? 'wide' : ''}">${label}<input data-field="${key}" value="${escapeHtml(extracted[key] || '')}"></label>`).join('')}</div>`;
  result.querySelectorAll('input').forEach(input => input.addEventListener('input', () => { partyData[party][input.dataset.field] = input.value; }));
}

async function processUpload(party, file) {
  const result = document.getElementById(`${party}Result`);
  if (!file) return;
  if (file.size > 16 * 1024 * 1024) { result.innerHTML = '<p class="upload-status">Please choose a file smaller than 16 MB.</p>'; return; }

  // ── Animated extraction experience ──
  const steps = [
    { icon: '🔐', text: 'Securing your document…' },
    { icon: '📄', text: 'Reading Aadhaar details…' },
    { icon: '🏠', text: 'Preparing for your agreement…' },
    { icon: '✨', text: 'Almost there…' },
  ];
  let stepIndex = 0;

  result.innerHTML = `
    <div class="extract-loader">
      <div class="extract-scanner">
        <div class="scanner-doc">
          <div class="scanner-line"></div>
          <div class="doc-lines"><span></span><span></span><span></span><span></span></div>
        </div>
      </div>
      <div class="extract-step">
        <span class="extract-step-icon">${steps[0].icon}</span>
        <span class="extract-step-text">${steps[0].text}</span>
      </div>
      <div class="extract-progress"><div class="extract-progress-bar"></div></div>
      <div class="extract-dots"><span class="dot active"></span><span class="dot"></span><span class="dot"></span><span class="dot"></span></div>
    </div>`;

  const stepInterval = setInterval(() => {
    stepIndex = Math.min(stepIndex + 1, steps.length - 1);
    const icon = result.querySelector('.extract-step-icon');
    const text = result.querySelector('.extract-step-text');
    const dots = result.querySelectorAll('.extract-dots .dot');
    if (icon && text) {
      icon.style.animation = 'none'; icon.offsetHeight; icon.style.animation = '';
      text.style.animation = 'none'; text.offsetHeight; text.style.animation = '';
      icon.textContent = steps[stepIndex].icon;
      text.textContent = steps[stepIndex].text;
      icon.classList.add('pop');
      setTimeout(() => icon.classList.remove('pop'), 400);
    }
    dots.forEach((d, i) => d.classList.toggle('active', i <= stepIndex));
  }, 2000);

  const payload = new FormData(); payload.append('file', file);
  try {
    const response = await fetch('/api/ocr/aadhaar', { method:'POST', body:payload });
    const data = await response.json();
    clearInterval(stepInterval);
    if (!response.ok || !data.success || !data.extracted) throw new Error(data.error || 'Extraction failed');
    partyData[party] = data.extracted;
    renderReviewCard(party, data.extracted);
    document.getElementById('continueButton').disabled = !(partyData.owner && partyData.tenant);
  } catch (error) {
    clearInterval(stepInterval);
    result.innerHTML = `<p class="upload-status upload-error">⚠ ${escapeHtml(error.message || 'Could not extract this document. Please try another clear image or PDF.')}</p>`;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.agreement-option').forEach(button => button.addEventListener('click', () => { document.querySelectorAll('.agreement-option').forEach(item => item.classList.remove('active')); button.classList.add('active'); agreementType = button.dataset.agreement; }));
  document.querySelectorAll('[data-upload]').forEach(input => input.addEventListener('change', event => processUpload(event.target.dataset.upload, event.target.files[0])));
  document.getElementById('continueButton').addEventListener('click', () => { sessionStorage.setItem('agreementAI.aadhaarParties', JSON.stringify({ agreementType, owner:partyData.owner, tenant:partyData.tenant })); window.location.href = agreementType === 'leave_license' ? '/agreements/leave-and-license?aadhaar=1' : '/agreements/simple-rental?aadhaar=1'; });
});
