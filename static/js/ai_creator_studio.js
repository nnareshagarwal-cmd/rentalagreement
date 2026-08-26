/**
 * ai_creator_studio.js — AI Creator Studio Frontend Orchestrator
 * ===============================================================
 * Powers the conversational AI agreement interviewer, two-way state sync,
 * readiness checklist, in-chat Aadhaar extraction, and live legal preview.
 */

let currentAgreementState = {
  agreement_type: 'simple_rental',
  jurisdiction: 'KA',
  scenario: 'family',
  fields: {}
};

let fieldRegistry = [];
let sectionLabels = {};
let sectionOrder = [];
/**
 * Escape HTML to prevent XSS and rendering errors
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
window.escapeHtml = escapeHtml;

document.addEventListener('DOMContentLoaded', async () => {
  // 1. Read URL params
  const params = new URLSearchParams(window.location.search);
  if (params.get('type')) currentAgreementState.agreement_type = params.get('type');
  if (params.get('state')) currentAgreementState.jurisdiction = params.get('state');
  if (params.get('scenario')) currentAgreementState.scenario = params.get('scenario');

  // If ?fresh=1 was passed, wipe any local draft
  if (params.get('fresh') === '1') {
    localStorage.removeItem('agreementai_studio_draft');
  }

  // Update header template pill
  const pillText = document.getElementById('templatePillText');
  if (pillText) {
    const isLL = currentAgreementState.agreement_type.includes('leave') || currentAgreementState.agreement_type.includes('license');
    pillText.textContent = isLL ? 'Leave & License Agreement · Maharashtra' : 'Rent Agreement · Pan-India';
  }

  // 2. Fetch field registry for the structured control panel drawer
  await fetchFieldRegistry();

  // 3. Check for existing local draft or send init message
  const savedDraft = params.get('fresh') === '1' ? null : localStorage.getItem('agreementai_studio_draft');
  if (savedDraft) {
    try {
      const parsed = JSON.parse(savedDraft);
      if (parsed && parsed.fields && Object.keys(parsed.fields).length > 0) {
        currentAgreementState = parsed;
      }
    } catch (e) {
      console.warn('[Studio] Failed to parse saved draft:', e);
    }
  }

  // 4. Initial sync with backend
  await initStudioChat();
});

/**
 * Initial sync with backend to get starting readiness, preview, and next question
 */
async function initStudioChat() {
  try {
    const res = await fetch('/api/ai/creator-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: '',
        agreement_state: currentAgreementState
      })
    });
    if (res.ok) {
      const data = await res.json();
      applyStateResponse(data);
    }
  } catch (e) {
    console.warn('[Studio] initStudioChat error:', e);
  }
}

/**
 * Fetch field registry and render the Structured Drawer Form
 */
async function fetchFieldRegistry() {
  try {
    const res = await fetch('/api/field-registry');
    if (res.ok) {
      const data = await res.json();
      fieldRegistry = data.fields || [];
      sectionLabels = data.section_labels || {};
      sectionOrder = data.section_order || [];
      renderDrawerForm();
    }
  } catch (e) {
    console.warn('[Studio] Field registry fetch failed:', e);
  }
}

/**
 * Render the Control Panel Drawer with all registry fields
 */
function renderDrawerForm() {
  const container = document.getElementById('drawerFormFields');
  if (!container) return;
  container.innerHTML = '';

  fieldRegistry.forEach(f => {
    const group = document.createElement('div');
    group.className = 'form-group-studio';

    const label = document.createElement('label');
    label.textContent = `${f.emoji || ''} ${f.label || f.key}`;
    label.htmlFor = `drawer_${f.key}`;

    let input;
    if (f.type === 'select') {
      input = document.createElement('select');
      input.id = `drawer_${f.key}`;
      const defaultOpt = document.createElement('option');
      defaultOpt.value = '';
      defaultOpt.textContent = '-- Select --';
      input.appendChild(defaultOpt);
      (f.options || []).forEach(opt => {
        const o = document.createElement('option');
        o.value = opt;
        o.textContent = opt;
        input.appendChild(o);
      });
    } else if (f.type === 'textarea') {
      input = document.createElement('textarea');
      input.id = `drawer_${f.key}`;
      input.rows = f.rows || 3;
    } else {
      input = document.createElement('input');
      input.type = f.type === 'date' ? 'date' : 'text';
      input.id = `drawer_${f.key}`;
      if (f.placeholder) input.placeholder = f.placeholder;
    }

    // Sync from current state
    const currentEntry = currentAgreementState.fields[f.key];
    if (currentEntry && currentEntry.value) {
      input.value = currentEntry.value;
    }

    // Attach two-way change listener
    input.addEventListener('change', (e) => {
      handleDrawerFieldChange(f.key, e.target.value);
    });

    group.appendChild(label);
    group.appendChild(input);
    container.appendChild(group);
  });
}

/**
 * Two-way sync: Update state when user edits a field directly in the drawer
 */
async function handleDrawerFieldChange(key, value) {
  currentAgreementState.fields[key] = {
    key: key,
    value: value,
    status: 'confirmed',
    source: 'user_explicit',
    confidence: 1.0,
    confirmed_at: new Date().toISOString()
  };

  // Re-sync with backend to update calculations and preview
  await syncStateWithBackend();
}

/**
 * Syncs the current state with backend to recalculate readiness and preview
 */
async function syncStateWithBackend() {
  try {
    const res = await fetch('/api/ai/creator-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: '',
        agreement_state: currentAgreementState
      })
    });
    if (res.ok) {
      const data = await res.json();
      applyStateResponse(data);
    }
  } catch (e) {
    console.warn('[Studio] Sync error:', e);
  }
}

/**
 * Initialize studio conversation with initial greeting and chips
 */
async function initStudioChat() {
  try {
    const res = await fetch('/api/ai/creator-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: '',
        agreement_state: currentAgreementState
      })
    });
    if (res.ok) {
      const data = await res.json();

      // Replace the placeholder "Setting up..." bubble with the real greeting
      if (data.assistant_message) {
        const initBubble = document.getElementById('initWelcomeBubble');
        if (initBubble) {
          const bubbleContent = initBubble.querySelector('.chat-bubble');
          if (bubbleContent) {
            bubbleContent.style.color = '';
            bubbleContent.style.fontStyle = '';
            bubbleContent.innerHTML = formatMarkdown(data.assistant_message);
          }
        }
      }

      applyStateResponse(data);

      // Render the Aadhaar Fast-Track Kickstart Card if parties are not yet confirmed
      renderKickstartCard();
    }
  } catch (e) {
    console.warn('[Studio] Init chat error:', e);
    // Show a friendly fallback in the init bubble
    const initBubble = document.getElementById('initWelcomeBubble');
    if (initBubble) {
      const bubbleContent = initBubble.querySelector('.chat-bubble');
      if (bubbleContent) {
        bubbleContent.style.color = '';
        bubbleContent.style.fontStyle = '';
        bubbleContent.innerHTML = '👋 <strong>Let\'s create your Rent Agreement!</strong><br>Upload Aadhaar IDs or tell me a few details to begin.';
      }
    }
    renderKickstartCard();
  }
}

/**
 * Render the Aadhaar Fast-Track ID Kickstart Card in chat
 */
function renderKickstartCard() {
  const container = document.getElementById('studioChatMessages');
  if (!container) return;

  // Remove existing kickstart card if present
  const existing = document.getElementById('idKickstartCard');
  if (existing) existing.remove();

  // If both parties already have confirmed names, don't show kickstart card
  const hasOwner = Boolean(currentAgreementState.fields?.owner1_name?.value);
  const hasTenant = Boolean(currentAgreementState.fields?.tenant1_name?.value);
  if (hasOwner && hasTenant) return;

  const card = document.createElement('div');
  card.className = 'id-kickstart-card';
  card.id = 'idKickstartCard';

  card.innerHTML = `
    <div class="id-kickstart-header">
      <div class="id-kickstart-icon">🚀</div>
      <div>
        <div class="id-kickstart-title">Aadhaar Fast-Track Auto-Fill</div>
        <div class="id-kickstart-sub">Upload Landlord & Tenant IDs to auto-fill 80% of legal details instantly</div>
      </div>
    </div>

    <div class="id-dropzone-grid">
      <!-- Owner ID Dropzone -->
      <div class="id-dropzone ${hasOwner ? 'verified' : ''}" id="ownerDropzone" onclick="triggerPartyUpload('owner')">
        ${renderDropzoneInner('owner', hasOwner)}
      </div>

      <!-- Tenant ID Dropzone -->
      <div class="id-dropzone ${hasTenant ? 'verified' : ''}" id="tenantDropzone" onclick="triggerPartyUpload('tenant')">
        ${renderDropzoneInner('tenant', hasTenant)}
      </div>
    </div>

    <div class="id-manual-footer">
      <span>Don't have IDs handy?</span>
      <button type="button" class="id-manual-btn" onclick="dismissKickstartAndType()">Type details manually in chat &rarr;</button>
    </div>
  `;

  // Attach Drag & Drop listeners
  setTimeout(() => {
    setupDropzoneEvents('owner', card.querySelector('#ownerDropzone'));
    setupDropzoneEvents('tenant', card.querySelector('#tenantDropzone'));
  }, 50);

  container.appendChild(card);
  container.scrollTop = container.scrollHeight;
}

function renderDropzoneInner(role, isVerified) {
  const isOwner = role === 'owner';
  const prefix = isOwner ? 'owner1_' : 'tenant1_';
  const roleLabel = isOwner ? 'Landlord / Owner' : 'Tenant / Licensee';
  const roleIcon = isOwner ? '🏠' : '👤';

  if (isVerified) {
    const name = currentAgreementState.fields?.[`${prefix}name`]?.value || '';
    const age = currentAgreementState.fields?.[`${prefix}age`]?.value || '';
    const careof = currentAgreementState.fields?.[`${prefix}careof`]?.value || 'Father Name';
    const careofname = currentAgreementState.fields?.[`${prefix}careofname`]?.value || '';
    const address = currentAgreementState.fields?.[`${prefix}address`]?.value || '';

    const relTag = careof === 'Husband Name' ? 'W/o' : 'S/o';

    return `
      <div class="id-verified-header">
        <span style="font-size:12px; font-weight:600; color:#e2e8f0;">${roleIcon} ${roleLabel}</span>
        <span class="id-verified-badge">✓ Verified</span>
      </div>
      <div class="id-verified-name">${escapeHtml(name)}</div>
      <div class="id-verified-detail">
        ${age ? `<span>${escapeHtml(age)} yrs</span> • ` : ''}
        ${careofname ? `<span>${relTag} ${escapeHtml(careofname)}</span>` : ''}
      </div>
      ${address ? `<div class="id-verified-addr" title="${escapeHtml(address)}">📍 ${escapeHtml(address)}</div>` : ''}
      <span class="id-verified-reupload" onclick="event.stopPropagation(); triggerPartyUpload('${role}')">Replace ID</span>
    `;
  }

  return `
    <div class="id-dropzone-icon">${roleIcon}</div>
    <div class="id-dropzone-role">${roleLabel} ID</div>
    <div class="id-dropzone-prompt">Drop Aadhaar Card or Click</div>
    <div class="id-dropzone-format">Front/Back Image or PDF</div>
  `;
}

function triggerPartyUpload(role) {
  const input = role === 'owner' ? document.getElementById('ownerAadhaarInput') : document.getElementById('tenantAadhaarInput');
  if (input) input.click();
}

function setupDropzoneEvents(role, el) {
  if (!el) return;
  el.addEventListener('dragover', (e) => {
    e.preventDefault();
    el.classList.add('dragover');
  });
  el.addEventListener('dragleave', () => {
    el.classList.remove('dragover');
  });
  el.addEventListener('drop', (e) => {
    e.preventDefault();
    el.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processKickstartFile(role, e.dataTransfer.files[0]);
    }
  });
}

function handleKickstartFileInput(event, role) {
  const file = event.target.files && event.target.files[0];
  if (file) {
    processKickstartFile(role, file);
    event.target.value = ''; // reset so same file can be re-uploaded
  }
}

async function processKickstartFile(role, file) {
  const dropzone = document.getElementById(role === 'owner' ? 'ownerDropzone' : 'tenantDropzone');
  if (dropzone) {
    dropzone.classList.add('loading');
    dropzone.innerHTML = `
      <div class="id-dropzone-icon">⚡</div>
      <div class="id-dropzone-role">Scanning ${role === 'owner' ? 'Owner' : 'Tenant'} ID...</div>
      <div class="id-dropzone-prompt" style="color:#c084fc;">Extracting legal name, age & address...</div>
    `;
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/ocr/aadhaar', {
      method: 'POST',
      body: formData
    });
    const result = await res.json();

    if (res.ok && result.success && result.extracted) {
      const data = result.extracted;
      const prefix = role === 'owner' ? 'owner1_' : 'tenant1_';

      if (!currentAgreementState.fields) currentAgreementState.fields = {};

      if (data.full_name) {
        currentAgreementState.fields[`${prefix}name`] = { value: data.full_name, source: 'aadhaar_ocr', status: 'confirmed' };
      }
      if (data.age) {
        currentAgreementState.fields[`${prefix}age`] = { value: String(data.age), source: 'aadhaar_ocr', status: 'confirmed' };
      }
      if (data.careof) {
        currentAgreementState.fields[`${prefix}careof`] = { value: data.careof, source: 'aadhaar_ocr', status: 'confirmed' };
      }
      if (data.relation_name) {
        currentAgreementState.fields[`${prefix}careofname`] = { value: data.relation_name, source: 'aadhaar_ocr', status: 'confirmed' };
      }
      if (data.full_address) {
        currentAgreementState.fields[`${prefix}address`] = { value: data.full_address, source: 'aadhaar_ocr', status: 'confirmed' };
      }

      // Re-render dropzone state
      if (dropzone) {
        dropzone.classList.remove('loading');
        dropzone.classList.add('verified');
        dropzone.innerHTML = renderDropzoneInner(role, true);
      }

      // Re-sync with backend (updates live preview on right)
      await syncStateWithBackend();

      const roleTitle = role === 'owner' ? 'Landlord / Owner' : 'Tenant';
      const addrSnippet = data.full_address ? `\n\n📍 **Permanent Address:** ${escapeHtml(data.full_address)}` : '';

      // Bubble 1: Aadhaar verified receipt
      appendChatBubble('assistant', `✨ **${roleTitle} ID verified!** (${escapeHtml(data.full_name)})${addrSnippet}`);

      // Bubble 2: Interactive Profile & Contact Card
      appendChatBubble(
        'assistant',
        `Please select occupation and provide contact details for **${escapeHtml(data.full_name)}**:`,
        [],
        null,
        {
          type: 'party_profile',
          party_role: role,
          party_name: data.full_name,
          occupations: [
            'PRIVATE EMPLOYEE', 'BUSINESS', 'PROFESSIONAL',
            'GOVERNMENT EMPLOYEE', 'SELF EMPLOYED', 'HOUSEWIFE', 'RETIRED'
          ]
        }
      );
    } else {
      if (dropzone) {
        dropzone.classList.remove('loading');
        dropzone.innerHTML = renderDropzoneInner(role, false);
      }
      alert('⚠️ ' + (result.error || 'Could not read Aadhaar details. Please try a clearer image.'));
    }
  } catch (err) {
    if (dropzone) {
      dropzone.classList.remove('loading');
      dropzone.innerHTML = renderDropzoneInner(role, false);
    }
    console.warn('[Kickstart OCR error]', err);
    alert('⚠️ OCR processing error. Please check your internet connection.');
  }
}

function dismissKickstartAndType() {
  const card = document.getElementById('idKickstartCard');
  if (card) card.remove();
  const input = document.getElementById('studioChatInput');
  if (input) input.focus();
}

window.triggerPartyUpload = triggerPartyUpload;
window.handleKickstartFileInput = handleKickstartFileInput;
window.dismissKickstartAndType = dismissKickstartAndType;

/**
 * Render the 2-Step Property Search Card in chat:
 * Step 1: Search Society / Building via Google Places
 * Step 2: Enter Flat No / Block / Wing
 */
function renderPropertySearchCard() {
  const container = document.getElementById('studioChatMessages');
  if (!container) return;

  // Remove any existing property card
  const existing = document.getElementById('propertySearchCard');
  if (existing) existing.remove();

  const card = document.createElement('div');
  card.className = 'property-search-card';
  card.id = 'propertySearchCard';

  card.innerHTML = `
    <div class="property-step-header">
      <div class="property-step-icon">🏢</div>
      <div>
        <div class="property-step-title">Step 1: Search your Society / Building</div>
        <div class="property-step-sub">Start typing the apartment, society, or building name</div>
      </div>
    </div>

    <div class="property-search-wrapper" id="propertySocietySection">
      <span class="property-search-icon">🔍</span>
      <input type="text" class="property-search-input" id="propertySocietyInput"
        placeholder="e.g. SMR Vinay City, Prestige Shantiniketan, DLF Phase 3..."
        autocomplete="off" />
      <div class="property-results-list" id="propertySocietyResults"></div>
    </div>

    <div id="propertyFlatSection" style="display:none;"></div>

    <div class="property-manual-link">
      <a onclick="dismissPropertyCardAndType()">Not in a society? Type full address manually</a>
    </div>
  `;

  container.appendChild(card);
  container.scrollTop = container.scrollHeight;

  // Wire up the society search
  setTimeout(() => setupPropertySocietySearch(), 50);
}

// State for the property search card
let _propertySocietyData = null; // selected Google Places result
let _propertySocietyDebounce = null;
let _propertySocietyActiveIdx = -1;
let _propertySocietySuggestions = [];

function setupPropertySocietySearch() {
  const input = document.getElementById('propertySocietyInput');
  const resultsList = document.getElementById('propertySocietyResults');
  if (!input || !resultsList) return;

  input.focus();

  input.addEventListener('input', () => {
    clearTimeout(_propertySocietyDebounce);
    const query = (input.value || '').trim();

    if (query.length < 2) {
      resultsList.style.display = 'none';
      resultsList.innerHTML = '';
      _propertySocietySuggestions = [];
      _propertySocietyActiveIdx = -1;
      return;
    }

    _propertySocietyDebounce = setTimeout(async () => {
      try {
        const res = await fetch(`/api/places/autocomplete?query=${encodeURIComponent(query)}`);
        if (!res.ok) return;
        const data = await res.json();
        _propertySocietySuggestions = data.suggestions || [];
        _propertySocietyActiveIdx = -1;

        if (_propertySocietySuggestions.length === 0) {
          resultsList.style.display = 'none';
          resultsList.innerHTML = '';
          return;
        }

        resultsList.innerHTML = '';
        _propertySocietySuggestions.forEach((item, idx) => {
          const row = document.createElement('div');
          row.className = 'property-result-item';
          row.setAttribute('data-idx', idx);
          row.innerHTML = `
            <span class="property-result-icon">📍</span>
            <div>
              <div class="property-result-title">${escapeHtml(item.title || item.description || '')}</div>
              ${item.subtitle ? `<div class="property-result-subtitle">${escapeHtml(item.subtitle)}</div>` : ''}
            </div>
          `;
          row.addEventListener('click', () => selectPropertySociety(item));
          resultsList.appendChild(row);
        });
        resultsList.style.display = 'block';
      } catch (err) {
        console.warn('[PropertySearch] Error:', err);
      }
    }, 280);
  });

  // Keyboard navigation
  input.addEventListener('keydown', (e) => {
    if (resultsList.style.display === 'none' || _propertySocietySuggestions.length === 0) return;

    const items = resultsList.querySelectorAll('.property-result-item');
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      _propertySocietyActiveIdx = (_propertySocietyActiveIdx + 1) % items.length;
      items.forEach((it, i) => it.classList.toggle('selected', i === _propertySocietyActiveIdx));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      _propertySocietyActiveIdx = (_propertySocietyActiveIdx - 1 + items.length) % items.length;
      items.forEach((it, i) => it.classList.toggle('selected', i === _propertySocietyActiveIdx));
    } else if (e.key === 'Enter') {
      if (_propertySocietyActiveIdx >= 0 && _propertySocietyActiveIdx < _propertySocietySuggestions.length) {
        e.preventDefault();
        selectPropertySociety(_propertySocietySuggestions[_propertySocietyActiveIdx]);
      }
    } else if (e.key === 'Escape') {
      resultsList.style.display = 'none';
    }
  });

  // Click outside to dismiss
  document.addEventListener('click', (e) => {
    if (!resultsList.contains(e.target) && e.target !== input) {
      resultsList.style.display = 'none';
    }
  });
}

async function selectPropertySociety(item) {
  const societySection = document.getElementById('propertySocietySection');
  const resultsList = document.getElementById('propertySocietyResults');
  if (resultsList) resultsList.style.display = 'none';

  // Store the selected society info
  _propertySocietyData = {
    title: item.title || item.description || '',
    description: item.description || '',
    place_id: item.place_id || ''
  };

  // Try to resolve structured components via the Places resolve API
  if (item.place_id) {
    try {
      const res = await fetch(`/api/places/resolve?place_id=${encodeURIComponent(item.place_id)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.resolved) {
          _propertySocietyData.resolved = data.resolved;
        }
      }
    } catch (err) {
      console.warn('[PropertySearch] Resolve error:', err);
    }
  }

  // Replace search box with verified society display
  if (societySection) {
    const displayAddr = _propertySocietyData.description || _propertySocietyData.title;
    societySection.innerHTML = `
      <div class="property-verified-society">
        <span style="font-size:20px;">🏢</span>
        <div class="property-verified-text">
          <div class="property-verified-name">${escapeHtml(_propertySocietyData.title)}</div>
          <div class="property-verified-addr">📍 ${escapeHtml(displayAddr)}</div>
          <span class="property-change-link" onclick="resetPropertySociety()">Change</span>
        </div>
        <span class="property-verified-badge">✓ Found</span>
      </div>
    `;
  }

  // Show Step 2: Flat / Block input
  showPropertyFlatInput();
}

function resetPropertySociety() {
  _propertySocietyData = null;
  const societySection = document.getElementById('propertySocietySection');
  const flatSection = document.getElementById('propertyFlatSection');

  if (societySection) {
    societySection.innerHTML = `
      <span class="property-search-icon">🔍</span>
      <input type="text" class="property-search-input" id="propertySocietyInput"
        placeholder="e.g. SMR Vinay City, Prestige Shantiniketan, DLF Phase 3..."
        autocomplete="off" />
      <div class="property-results-list" id="propertySocietyResults"></div>
    `;
    setTimeout(() => setupPropertySocietySearch(), 50);
  }
  if (flatSection) flatSection.style.display = 'none';
}

function showPropertyFlatInput() {
  const flatSection = document.getElementById('propertyFlatSection');
  if (!flatSection) return;

  // Update the step header
  const stepHeader = document.querySelector('#propertySearchCard .property-step-title');
  if (stepHeader) stepHeader.textContent = 'Step 2: Enter your Flat / House details';
  const stepSub = document.querySelector('#propertySearchCard .property-step-sub');
  if (stepSub) stepSub.textContent = 'Add flat number, block, floor, or wing to complete the address';

  flatSection.style.display = 'block';
  flatSection.className = 'property-flat-section';
  flatSection.innerHTML = `
    <div class="property-step-header" style="margin-bottom:10px;">
      <div class="property-step-icon">🏠</div>
      <div>
        <div class="property-step-title" style="font-size:13px;">Flat No / House No / Block / Wing</div>
        <div class="property-step-sub">e.g. Flat 412, Block-2A  or  House #16, Ground Floor</div>
      </div>
    </div>
    <input type="text" class="property-flat-input" id="propertyFlatInput"
      placeholder="e.g. Flat 412, Block-2A, 4th Floor" autocomplete="off" />
    <button type="button" class="property-confirm-btn" id="propertyConfirmBtn"
      onclick="confirmPropertyAddress()" disabled>
      ✓ Confirm Property Address
    </button>
  `;

  const flatInput = document.getElementById('propertyFlatInput');
  const confirmBtn = document.getElementById('propertyConfirmBtn');

  if (flatInput) {
    flatInput.focus();
    flatInput.addEventListener('input', () => {
      const val = (flatInput.value || '').trim();
      if (confirmBtn) confirmBtn.disabled = val.length < 1;
    });
    flatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !confirmBtn.disabled) {
        e.preventDefault();
        confirmPropertyAddress();
      }
    });
  }

  // Scroll to bottom
  const chatContainer = document.getElementById('studioChatMessages');
  if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
}

async function confirmPropertyAddress() {
  const flatInput = document.getElementById('propertyFlatInput');
  const flatValue = (flatInput ? flatInput.value : '').trim();

  if (!_propertySocietyData) return;

  // Build the full property address
  const societyAddr = _propertySocietyData.description || _propertySocietyData.title || '';
  const fullAddress = flatValue ? `${flatValue}, ${societyAddr}` : societyAddr;

  // Extract components for state
  const resolved = _propertySocietyData.resolved || {};
  const societyName = _propertySocietyData.title || resolved.society_name || '';
  const city = resolved.city || '';
  const state = resolved.state || '';
  const pincode = resolved.pincode || '';

  // Update agreement state
  if (!currentAgreementState.fields) currentAgreementState.fields = {};
  currentAgreementState.fields.property_address = { value: fullAddress, source: 'places_card', status: 'confirmed' };
  if (societyName) currentAgreementState.fields.society_name = { value: societyName, source: 'places_card', status: 'confirmed' };
  if (flatValue) currentAgreementState.fields.flat_no = { value: flatValue, source: 'user_input', status: 'confirmed' };
  if (city) currentAgreementState.fields.city = { value: city, source: 'places_card', status: 'confirmed' };
  if (pincode) currentAgreementState.fields.pincode = { value: pincode, source: 'places_card', status: 'confirmed' };

  // Remove the property card
  const card = document.getElementById('propertySearchCard');
  if (card) card.remove();

  // Send property address confirmation through chat so interview engine smoothly asks next question
  await sendUserMessage(`Rented Property Address: ${fullAddress}`);
}

function dismissPropertyCardAndType() {
  const card = document.getElementById('propertySearchCard');
  if (card) card.remove();
  appendChatBubble('assistant', `No problem! Just type the **complete rented property address** below (including flat number, building, locality, city, and PIN):`);
  const input = document.getElementById('studioChatInput');
  if (input) input.focus();
}

window.renderPropertySearchCard = renderPropertySearchCard;
window.resetPropertySociety = resetPropertySociety;
window.confirmPropertyAddress = confirmPropertyAddress;
window.dismissPropertyCardAndType = dismissPropertyCardAndType;

/**
 * Send user message or clicked chip text to the AI Creator
 */
async function sendUserMessage(customText = null) {
  const input = document.getElementById('studioChatInput');
  const text = (customText || input.value || '').trim();
  if (!text) return;
  if (input) input.value = '';

  // 1. Append user message bubble
  appendChatBubble('user', text);

  // 2. Append loading indicator
  const loadId = appendLoadingBubble();

  try {
    const res = await fetch('/api/ai/creator-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        agreement_state: currentAgreementState
      })
    });

    removeLoadingBubble(loadId);

    if (res.ok) {
      const data = await res.json();
      if (data.assistant_message) {
        // If message has multiple sections separated by '---', render each in a clean separate bubble
        const sections = data.assistant_message.split(/\n\s*---\s*\n/);
        const chips = data.next_interaction?.suggestion_chips || [];
        const infoTip = data.next_interaction?.info_tip || null;
        sections.forEach((sec, idx) => {
          const trimmed = sec.trim();
          if (trimmed) {
            const isLast = idx === sections.length - 1;
            appendChatBubble('assistant', trimmed, isLast ? chips : [], isLast ? infoTip : null);
          }
        });
      }
      applyStateResponse(data);
    } else {
      appendChatBubble('assistant', '⚠️ Sorry, I could not process that message right now. Please try again.');
    }
  } catch (e) {
    removeLoadingBubble(loadId);
    appendChatBubble('assistant', '⚠️ Connection error. Please check your internet and retry.');
  }
}

/**
 * Update UI from backend creator-chat response payload
 */
function applyStateResponse(data) {
  if (!data) return;

  if (data.agreement_state) {
    currentAgreementState = data.agreement_state;
    // Persist draft safely
    localStorage.setItem('agreementai_studio_draft', JSON.stringify(currentAgreementState));
  }

  // Update Readiness Banner & Checklist
  if (data.readiness) {
    updateReadinessUI(data.readiness);
  }

  // Update Suggestion Chips & Datepicker prompt
  if (data.next_interaction) {
    window.lastNextInteraction = data.next_interaction;
    updateChipsUI(data.next_interaction.suggestion_chips || []);

    const isDateFocus = data.next_interaction.focus_area === 'dates' || 
      (data.next_interaction.target_fields || []).some(f => f.includes('date'));
    
    const calBtn = document.getElementById('studioCalendarBtn');
    const chatInput = document.getElementById('studioChatInput');
    if (calBtn) {
      calBtn.classList.toggle('active-step', Boolean(isDateFocus));
    }
    if (chatInput) {
      if (isDateFocus) {
        chatInput.placeholder = '📅 Pick start date from calendar icon or type here...';
      } else {
        chatInput.placeholder = 'Type rental details, paste message, or ask AI...';
      }
    }
  }

  // Update Live Document Preview HTML
  if (data.preview_html) {
    const previewEl = document.getElementById('studioPreviewContent');
    if (previewEl) previewEl.innerHTML = data.preview_html;
  }

  // Update Drawer Inputs
  syncDrawerInputs();

  // Update Download Buttons State
  const genBtn = document.getElementById('generateDocxBtn');
  if (genBtn && data.readiness) {
    genBtn.disabled = !data.readiness.ready_for_generation && !data.readiness.ready_for_review;
  }
}

/**
 * Render the Readiness board cards
 */
function updateReadinessUI(readiness) {
  const headlineEl = document.getElementById('readinessHeadline');
  const badgeEl = document.getElementById('readinessBadge');
  const badgeTextEl = document.getElementById('readinessBadgeText');
  const reqGrid = document.getElementById('requiredCardsGrid');
  const recGrid = document.getElementById('recommendedCardsGrid');

  if (headlineEl) headlineEl.textContent = readiness.headline || 'Agreement Details';

  if (badgeEl && badgeTextEl) {
    if (readiness.ready_for_generation) {
      badgeEl.className = 'readiness-badge';
      badgeTextEl.textContent = '✓ Ready to Generate';
    } else if (readiness.ready_for_review) {
      badgeEl.className = 'readiness-badge pending';
      badgeTextEl.textContent = 'Ready for Review';
    } else {
      badgeEl.className = 'readiness-badge pending';
      badgeTextEl.textContent = `${readiness.missing_count} Remaining`;
    }
  }

  // Render Required Cards
  if (reqGrid) {
    reqGrid.innerHTML = '';

    // 1. Completed required
    (readiness.required_completed || []).forEach(item => {
      const card = document.createElement('div');
      card.className = 'summary-card confirmed';
      card.innerHTML = `
        <div class="summary-card-head"><span>${item.label}</span><span style="color:#34d399;">✓ Verified</span></div>
        <div class="summary-card-val">${formatFieldValue(item.key, item.value)}</div>
      `;
      reqGrid.appendChild(card);
    });

    // 2. Extracted (Needs Confirmation)
    (readiness.required_needs_confirmation || []).forEach(item => {
      const card = document.createElement('div');
      card.className = 'summary-card';
      card.style.borderColor = 'rgba(139, 92, 246, 0.4)';
      card.innerHTML = `
        <div class="summary-card-head"><span>${item.label}</span><span style="color:#c084fc;">🤖 Extracted</span></div>
        <div class="summary-card-val">${formatFieldValue(item.key, item.value)}</div>
        <div style="margin-top:6px; display:flex; gap:6px;">
          <button type="button" class="studio-btn studio-btn-primary" style="padding:4px 10px; font-size:11px;" onclick="confirmSingleField('${item.key}')">Confirm ✓</button>
        </div>
      `;
      reqGrid.appendChild(card);
    });

    // 3. Missing required
    (readiness.required_missing || []).forEach(item => {
      const card = document.createElement('div');
      card.className = 'summary-card missing';
      card.innerHTML = `
        <div class="summary-card-head"><span>${item.label}</span><span style="color:#f87171;">⏳ Missing</span></div>
        <div class="summary-card-val missing-text">Not provided yet</div>
      `;
      reqGrid.appendChild(card);
    });
  }

  // Render Recommended Cards
  if (recGrid) {
    recGrid.innerHTML = '';
    (readiness.recommended_status || []).forEach(item => {
      const card = document.createElement('div');
      card.className = 'summary-card';
      const valStr = item.value ? formatFieldValue(item.key, item.value) : '<span style="color:var(--studio-text-dim); font-style:italic;">Default / Optional</span>';
      card.innerHTML = `
        <div class="summary-card-head"><span>${item.label}</span><span style="color:#94a3b8;">💡 Preset</span></div>
        <div class="summary-card-val">${valStr}</div>
      `;
      recGrid.appendChild(card);
    });
  }
}

/**
 * Escape HTML to prevent XSS and rendering errors
 */
function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Format currency and dates nicely for card display
 */
function formatFieldValue(key, val) {
  if (!val) return '';
  if (key === 'monthly_rent' || key === 'security_deposit') {
    try {
      const num = parseInt(String(val).replace(/,/g, ''), 10);
      if (!isNaN(num)) return `₹${num.toLocaleString('en-IN')}`;
    } catch (e) {}
  }
  return String(val);
}

/**
 * Quick Reply Suggestion Chips (now rendered directly inside chat cards)
 */
function updateChipsUI(chips) {
  const container = document.getElementById('studioChipsContainer');
  if (container) {
    container.innerHTML = '';
    container.style.display = 'none';
  }
}

/**
 * Sync Drawer input values from current state
 */
function syncDrawerInputs() {
  Object.keys(currentAgreementState.fields || {}).forEach(k => {
    const el = document.getElementById(`drawer_${k}`);
    if (el) {
      el.value = currentAgreementState.fields[k].value || '';
    }
  });
}

/**
 * Confirm a single extracted field
 */
async function confirmSingleField(key) {
  try {
    const res = await fetch('/api/ai/confirm-field', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agreement_state: currentAgreementState,
        field_key: key
      })
    });
    if (res.ok) {
      const data = await res.json();
      applyStateResponse(data);
    }
  } catch (e) {
    console.warn('[Studio] Confirm field error:', e);
  }
}

/**
 * Handle In-Chat Aadhaar OCR Upload
 */
async function handleInChatAadhaarUpload(inputEl) {
  if (!inputEl.files || !inputEl.files[0]) return;
  const file = inputEl.files[0];
  inputEl.value = '';

  appendChatBubble('user', `📎 Uploaded ID: ${file.name}`);
  const loadId = appendLoadingBubble();

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/ocr/aadhaar', {
      method: 'POST',
      body: formData
    });
    removeLoadingBubble(loadId);
    const data = await res.json();

    const extracted = data.extracted || data.data;

    if (res.ok && data.success && extracted && extracted.full_name) {
      const addrParts = [extracted.address_line1, extracted.locality, extracted.city, extracted.state, extracted.pincode].filter(Boolean);
      const addr = addrParts.join(', ');
      
      // Calculate age from date_of_birth if available
      let age = '';
      if (extracted.date_of_birth) {
        try {
          const dobYear = parseInt(extracted.date_of_birth.split('-')[0] || extracted.date_of_birth.split('/')[2] || extracted.date_of_birth.slice(-4), 10);
          if (!isNaN(dobYear) && dobYear > 1920 && dobYear <= new Date().getFullYear()) {
            age = String(new Date().getFullYear() - dobYear);
          }
        } catch (e) {}
      }

      // Determine relation type: S/O, D/O -> Father Name, W/O -> Husband Name
      const relType = (extracted.relation_type || '').toUpperCase();
      const careof = (relType.includes('W/O') || relType.includes('WO') || relType.includes('WIFE')) ? 'Husband Name' : 'Father Name';
      const relName = extracted.relation_name || '';

      // Determine if this should populate Owner or Tenant based on which is missing or user_role
      const userRole = (currentAgreementState.user_role || 'owner').toLowerCase();
      const hasOwner = currentAgreementState.fields && currentAgreementState.fields.owner1_name && currentAgreementState.fields.owner1_name.value;
      const hasTenant = currentAgreementState.fields && currentAgreementState.fields.tenant1_name && currentAgreementState.fields.tenant1_name.value;

      let role = 'Owner';
      if (userRole === 'tenant') {
        role = hasTenant ? 'Owner' : 'Tenant';
      } else {
        role = hasOwner ? 'Tenant' : 'Owner';
      }

      const promptParts = [
        `${role} details from uploaded Aadhaar ID:`,
        `Name is ${extracted.full_name},`,
      ];
      if (age) promptParts.push(`age is ${age},`);
      if (relName) {
        promptParts.push(`careof is ${careof}, relation is ${relName},`);
      }
      promptParts.push(`address is ${addr}.`);

      const prompt = promptParts.join(' ');
      await sendUserMessage(prompt);
    } else {
      appendChatBubble('assistant', `⚠️ Could not read Aadhaar ID: ${data.error || 'Please upload a clear front/back image or PDF.'}`);
    }
  } catch (e) {
    removeLoadingBubble(loadId);
    appendChatBubble('assistant', '⚠️ Upload failed. Please check connection and retry.');
  }
}

/**
 * Append chat message bubble to conversation stream (supports inline choice buttons, profile cards, and legal tips)
 */
function appendChatBubble(role, text, chips = [], infoTip = null, profileData = null) {
  const container = document.getElementById('studioChatMessages');
  if (!container) return;

  const msgDiv = document.createElement('div');
  msgDiv.className = `chat-msg ${role}`;

  const avatar = document.createElement('div');
  avatar.className = 'chat-avatar';
  avatar.textContent = role === 'user' ? '👤' : '🤖';

  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';

  if (infoTip && infoTip.title && infoTip.content) {
    bubble.innerHTML = `
      <div class="chat-bubble-header">
        <div class="chat-bubble-text">${formatMarkdown(text)}</div>
        <button type="button" class="chat-info-tip-toggle" onclick="toggleChatInfoTip(this)" title="Click to learn more">
          <span class="info-tip-icon">💡</span>
          <span class="info-tip-text">What is this?</span>
        </button>
      </div>
      <div class="chat-info-tip-box" style="display:none;">
        <div class="info-tip-box-title">💡 ${escapeHtml(infoTip.title)}</div>
        <div class="info-tip-box-content">${escapeHtml(infoTip.content).replace(/\n/g, '<br>')}</div>
      </div>
    `;
  } else {
    bubble.innerHTML = formatMarkdown(text);
  }

  // Render interactive Profile & Contact card if requested by engine
  if (role === 'assistant' && profileData && profileData.type === 'party_profile') {
    const card = document.createElement('div');
    card.className = 'chat-profile-card';
    const partyRole = profileData.party_role || 'owner';

    const currentOcc = (currentAgreementState?.fields?.[`${partyRole}1_occupation`]?.value || 'PRIVATE EMPLOYEE').toUpperCase();
    const currentPh = currentAgreementState?.fields?.[`${partyRole}1_phone`]?.value || '';
    const currentEm = currentAgreementState?.fields?.[`${partyRole}1_email`]?.value || '';

    const isPriv = currentOcc === 'PRIVATE EMPLOYEE';
    const isBiz = currentOcc === 'BUSINESS';
    const isOther = !isPriv && !isBiz;
    const otherVal = isOther ? (currentAgreementState?.fields?.[`${partyRole}1_occupation`]?.value || '') : '';

    card.innerHTML = `
      <div>
        <div class="chat-profile-section-title">💼 Select Occupation</div>
        <div class="chat-occ-chips" id="${partyRole}OccChips">
          <button type="button" class="chat-occ-chip${isPriv ? ' active' : ''}" onclick="selectPartyProfileOcc(this, '${partyRole}', 'PRIVATE EMPLOYEE')">PRIVATE EMPLOYEE</button>
          <button type="button" class="chat-occ-chip${isBiz ? ' active' : ''}" onclick="selectPartyProfileOcc(this, '${partyRole}', 'BUSINESS')">BUSINESS</button>
          <button type="button" class="chat-occ-chip${isOther ? ' active' : ''}" onclick="selectPartyProfileOcc(this, '${partyRole}', 'OTHER')">✏️ Other...</button>
        </div>
        <div class="chat-occ-custom-wrap" id="${partyRole}OccCustomWrap" style="display: ${isOther ? 'block' : 'none'};">
          <input type="text" id="${partyRole}OccCustomInput" placeholder="Enter occupation (e.g. Doctor, Govt Employee, Homemaker...)" value="${escapeHtml(otherVal)}" oninput="handleCustomOccInput('${partyRole}', this.value)">
          <span class="chat-profile-error" id="${partyRole}OccErr">Please enter an occupation</span>
        </div>
        <input type="hidden" id="${partyRole}OccInput" value="${escapeHtml(currentOcc)}">
      </div>

      <div class="chat-profile-inputs-row">
        <div class="chat-profile-field">
          <label>📱 Mobile Number</label>
          <input type="tel" class="chat-profile-input" id="${partyRole}PhoneInput" placeholder="10-digit mobile" maxlength="10" value="${escapeHtml(currentPh)}" oninput="this.value = this.value.replace(/\\D/g, '')">
          <span class="chat-profile-error" id="${partyRole}PhoneErr">Please enter a valid 10-digit mobile number</span>
        </div>
        <div class="chat-profile-field">
          <label>📧 Email Address</label>
          <input type="email" class="chat-profile-input" id="${partyRole}EmailInput" placeholder="name@example.com" value="${escapeHtml(currentEm)}">
          <span class="chat-profile-error" id="${partyRole}EmailErr">Please enter a valid email address</span>
        </div>
      </div>

      <button type="button" class="chat-profile-submit-btn" onclick="submitPartyProfileCard(this, '${partyRole}')">
        <span>✅ Save & Continue</span>
      </button>
    `;
    bubble.appendChild(card);
  }

  // Render interactive inline choice buttons inside assistant question cards
  if (role === 'assistant' && Array.isArray(chips) && chips.length > 0) {
    const btnGroup = document.createElement('div');
    btnGroup.className = 'chat-inline-buttons';
    chips.forEach(chip => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chat-inline-btn';
      btn.innerHTML = `<span class="inline-btn-label">${escapeHtml(chip.label || chip.value || '')}</span>`;
      btn.onclick = () => handleInlineChoiceClick(btn, chip);
      btnGroup.appendChild(btn);
    });
    bubble.appendChild(btnGroup);
  }

  msgDiv.appendChild(avatar);
  msgDiv.appendChild(bubble);
  container.appendChild(msgDiv);

  container.scrollTop = container.scrollHeight;
}

/**
 * Toggle expandable info tip box inside chat bubbles
 */
function toggleChatInfoTip(btn) {
  const bubble = btn.closest('.chat-bubble');
  if (!bubble) return;
  const box = bubble.querySelector('.chat-info-tip-box');
  if (!box) return;
  const isHidden = box.style.display === 'none';
  box.style.display = isHidden ? 'block' : 'none';
  btn.classList.toggle('active', isHidden);
}
window.toggleChatInfoTip = toggleChatInfoTip;

/**
 * Select occupation chip in interactive party profile card
 */
function selectPartyProfileOcc(chipEl, partyRole, occVal) {
  const parent = chipEl.closest('.chat-occ-chips');
  if (!parent) return;
  parent.querySelectorAll('.chat-occ-chip').forEach(c => c.classList.remove('active'));
  chipEl.classList.add('active');

  const card = chipEl.closest('.chat-profile-card');
  if (!card) return;

  const hiddenInput = card.querySelector(`#${partyRole}OccInput`);
  const customWrap = card.querySelector(`#${partyRole}OccCustomWrap`);
  const customInput = card.querySelector(`#${partyRole}OccCustomInput`);
  const occErr = card.querySelector(`#${partyRole}OccErr`);

  if (occErr) occErr.classList.remove('visible');

  if (occVal === 'OTHER') {
    if (customWrap) customWrap.style.display = 'block';
    if (customInput) {
      customInput.focus();
      if (hiddenInput) hiddenInput.value = customInput.value.trim();
    }
  } else {
    if (customWrap) customWrap.style.display = 'none';
    if (hiddenInput) hiddenInput.value = occVal;
  }
}
window.selectPartyProfileOcc = selectPartyProfileOcc;

/**
 * Custom occupation live input handler
 */
function handleCustomOccInput(partyRole, val) {
  const card = document.getElementById(`${partyRole}OccChips`)?.closest('.chat-profile-card');
  if (!card) return;
  const hiddenInput = card.querySelector(`#${partyRole}OccInput`);
  const occErr = card.querySelector(`#${partyRole}OccErr`);
  if (hiddenInput) hiddenInput.value = val.trim();
  if (val.trim() && occErr) occErr.classList.remove('visible');
}
window.handleCustomOccInput = handleCustomOccInput;

/**
 * Submit party profile card (occupation + phone + email)
 */
async function submitPartyProfileCard(btnEl, partyRole) {
  const card = btnEl.closest('.chat-profile-card');
  if (!card) return;

  const occInput = card.querySelector(`#${partyRole}OccInput`);
  const customInput = card.querySelector(`#${partyRole}OccCustomInput`);
  const occCustomWrap = card.querySelector(`#${partyRole}OccCustomWrap`);
  const occErr = card.querySelector(`#${partyRole}OccErr`);

  const phoneInput = card.querySelector(`#${partyRole}PhoneInput`);
  const emailInput = card.querySelector(`#${partyRole}EmailInput`);

  const phoneErr = card.querySelector(`#${partyRole}PhoneErr`);
  const emailErr = card.querySelector(`#${partyRole}EmailErr`);

  let occ = occInput?.value.trim() || 'PRIVATE EMPLOYEE';
  const phone = phoneInput?.value.trim() || '';
  const email = emailInput?.value.trim() || '';

  let isValid = true;

  // If Other wrap is open, ensure custom occupation is typed
  if (occCustomWrap && occCustomWrap.style.display !== 'none') {
    const customVal = customInput?.value.trim();
    if (!customVal) {
      customInput?.classList.add('is-invalid');
      if (occErr) occErr.classList.add('visible');
      isValid = false;
    } else {
      customInput?.classList.remove('is-invalid');
      if (occErr) occErr.classList.remove('visible');
      occ = customVal.toUpperCase();
    }
  }

  // Phone validation (10 digits starting with 6-9)
  if (!/^[6-9]\d{9}$/.test(phone)) {
    phoneInput?.classList.add('is-invalid');
    if (phoneErr) phoneErr.classList.add('visible');
    isValid = false;
  } else {
    phoneInput?.classList.remove('is-invalid');
    if (phoneErr) phoneErr.classList.remove('visible');
  }

  // Email validation
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    emailInput?.classList.add('is-invalid');
    if (emailErr) emailErr.classList.add('visible');
    isValid = false;
  } else {
    emailInput?.classList.remove('is-invalid');
    if (emailErr) emailErr.classList.remove('visible');
  }

  if (!isValid) return;

  // Disable UI in card
  btnEl.disabled = true;
  btnEl.innerHTML = '<span>Saving...</span>';
  card.querySelectorAll('input, button').forEach(el => el.disabled = true);

  // Directly update client state
  if (!currentAgreementState.fields) currentAgreementState.fields = {};
  currentAgreementState.fields[`${partyRole}1_occupation`] = { value: occ, source: 'profile_card', status: 'confirmed' };
  currentAgreementState.fields[`${partyRole}1_phone`] = { value: phone, source: 'profile_card', status: 'confirmed' };
  currentAgreementState.fields[`${partyRole}1_email`] = { value: email, source: 'profile_card', status: 'confirmed' };

  // Dispatch message through chat
  const roleLabel = partyRole === 'owner' ? 'Owner' : 'Tenant';
  const msg = `${roleLabel} profile: ${occ}, mobile ${phone}, email ${email}`;
  await sendUserMessage(msg);
}
window.submitPartyProfileCard = submitPartyProfileCard;

/**
 * Handle clicking an inline button inside a chat card
 */
function handleInlineChoiceClick(btnEl, chip) {
  const value = typeof chip === 'string' ? chip : (chip.value || chip.label || '');
  const action = typeof chip === 'object' ? chip.action : null;

  const parent = btnEl.closest('.chat-inline-buttons');
  if (parent) {
    const allBtns = parent.querySelectorAll('.chat-inline-btn');
    allBtns.forEach(b => {
      b.disabled = true;
      if (b === btnEl) {
        b.classList.add('selected');
      } else {
        b.style.opacity = '0.4';
      }
    });
  }

  if (action === 'upload_aadhaar_owner' || action === 'upload_aadhaar_tenant') {
    const fileInput = document.getElementById('inChatAadhaarInput');
    if (fileInput) fileInput.click();
  } else if (action === 'preview_document') {
    switchStudioTab('preview');
  } else if (action === 'generate_agreement') {
    triggerDocxDownload();
  } else if (action === 'fill_input' || value.endsWith(' ')) {
    const input = document.getElementById('studioChatInput');
    if (input) {
      input.value = value;
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    }
  } else {
    sendUserMessage(value);
  }
}
window.handleInlineChoiceClick = handleInlineChoiceClick;

/**
 * Clear draft and restart fresh
 */
function clearDraftAndRestart() {
  localStorage.removeItem('agreementai_studio_draft');
  const urlParams = new URLSearchParams(window.location.search);
  const type = urlParams.get('type') || 'simple_rental';
  const state = urlParams.get('state') || 'KA';
  window.location.href = `/create?type=${encodeURIComponent(type)}&state=${encodeURIComponent(state)}&fresh=1`;
}
window.clearDraftAndRestart = clearDraftAndRestart;

/**
 * Append loading indicator bubble
 */
function appendLoadingBubble() {
  const container = document.getElementById('studioChatMessages');
  if (!container) return null;

  const loadId = `load_${Date.now()}`;
  const msgDiv = document.createElement('div');
  msgDiv.className = 'chat-msg assistant';
  msgDiv.id = loadId;
  msgDiv.innerHTML = `
    <div class="chat-avatar">🤖</div>
    <div class="chat-bubble" style="color:var(--studio-text-muted); font-style:italic; display:flex; align-items:center; gap:6px;">
      <span>Thinking...</span>
    </div>
  `;
  container.appendChild(msgDiv);
  container.scrollTop = container.scrollHeight;
  return loadId;
}

function removeLoadingBubble(loadId) {
  if (!loadId) return;
  const el = document.getElementById(loadId);
  if (el) el.remove();
}

/**
 * Simple markdown formatter for bold, bullets, and breaks
 */
function formatMarkdown(text) {
  if (!text) return '';
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/^• (.*?)$/gm, '<li style="margin-left:16px;">$1</li>')
    .replace(/\n/g, '<br>');
}

function handleChatInputKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendUserMessage();
  }
}

/**
 * Tab Switching (Summary vs Full Preview)
 */
function switchStudioTab(tabName) {
  const sumTab = document.getElementById('studioSummaryTab');
  const prevTab = document.getElementById('studioPreviewTab');
  const sumBtn = document.getElementById('tabSummaryBtn');
  const prevBtn = document.getElementById('tabPreviewBtn');

  if (tabName === 'summary') {
    sumTab.classList.add('active');
    prevTab.classList.remove('active');
    sumBtn.classList.add('active');
    prevBtn.classList.remove('active');
  } else {
    prevTab.classList.add('active');
    sumTab.classList.remove('active');
    prevBtn.classList.add('active');
    sumBtn.classList.remove('active');
  }
}

/**
 * Toggle Structured Form Drawer
 */
function toggleFormDrawer() {
  const drawer = document.getElementById('studioDrawer');
  const backdrop = document.getElementById('studioDrawerBackdrop');
  if (!drawer) return;
  drawer.classList.toggle('active');
  if (backdrop) backdrop.classList.toggle('active');
}

/**
 * Save Agreement Draft
 */
function saveAgreementDraft() {
  localStorage.setItem('agreementai_studio_draft', JSON.stringify(currentAgreementState));
  const ind = document.getElementById('autoSaveIndicator');
  if (ind) {
    ind.textContent = '✓ Draft saved';
    setTimeout(() => { ind.textContent = 'Draft auto-saved'; }, 2000);
  }
}

/**
 * Clear all draft data and restart from the fresh role-selection greeting
 */
function clearDraftAndRestart() {
  try {
    localStorage.removeItem('agreementai_studio_draft');
    sessionStorage.clear();
  } catch (e) {}

  const params = new URLSearchParams(window.location.search);
  const type = params.get('type') || currentAgreementState.agreement_type || 'simple_rental';
  const state = params.get('state') || currentAgreementState.jurisdiction || 'KA';
  
  // Instant clean navigation
  window.location.href = `/create?type=${encodeURIComponent(type)}&state=${encodeURIComponent(state)}&fresh=1`;
}
window.clearDraftAndRestart = clearDraftAndRestart;

/**
 * Trigger DOCX Download
 */
async function triggerDocxDownload() {
  const flatData = {};
  Object.keys(currentAgreementState.fields || {}).forEach(k => {
    flatData[k] = currentAgreementState.fields[k].value;
  });
  flatData['agreement_type'] = currentAgreementState.agreement_type;
  flatData['state_code'] = currentAgreementState.jurisdiction;

  try {
    const res = await fetch('/api/rental/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(flatData)
    });
    if (res.ok) {
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Rental_Agreement_${Date.now()}.docx`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } else {
      alert('Could not generate document. Please ensure all required fields are filled.');
    }
  } catch (e) {
    alert('Download error. Please check your connection.');
  }
}

/**
 * Trigger Leegality Digital eSign from AI Studio
 */
function triggerStudioEsign() {
  const flatData = {};
  Object.keys(currentAgreementState.fields || {}).forEach(k => {
    flatData[k] = currentAgreementState.fields[k].value;
  });
  flatData['agreement_type'] = currentAgreementState.agreement_type;
  flatData['state_code'] = currentAgreementState.jurisdiction;

  if (window.safeKeysEsign) {
    window.safeKeysEsign.initiateEsignFromForm(flatData);
  } else if (typeof SafeKeysEsignController !== 'undefined') {
    window.safeKeysEsign = new SafeKeysEsignController();
    window.safeKeysEsign.initiateEsignFromForm(flatData);
  } else {
    alert('eSign module is initializing. Please try again in a moment.');
  }
}
window.triggerStudioEsign = triggerStudioEsign;

/**
 * Setup Google Places Autocomplete for Property inputs
 */
function setupPlacesAutocomplete() {
  const targetIds = ['drawer_property_address', 'drawer_society_name'];
  
  targetIds.forEach(id => {
    const input = document.getElementById(id);
    if (!input) return;

    // Create dropdown list container if not exists
    let wrapper = input.parentElement;
    if (!wrapper.classList.contains('places-dropdown-wrapper')) {
      const w = document.createElement('div');
      w.className = 'places-dropdown-wrapper';
      input.parentNode.insertBefore(w, input);
      w.appendChild(input);
      wrapper = w;
    }

    let list = wrapper.querySelector('.places-autocomplete-list');
    if (!list) {
      list = document.createElement('div');
      list.className = 'places-autocomplete-list';
      wrapper.appendChild(list);
    }

    let debounceTimer;
    input.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      const q = input.value.trim();
      if (q.length < 3) {
        list.style.display = 'none';
        list.innerHTML = '';
        return;
      }

      debounceTimer = setTimeout(async () => {
        try {
          const res = await fetch(`/api/places/autocomplete?query=${encodeURIComponent(q)}`);
          if (!res.ok) return;
          const data = await res.json();
          const suggestions = data.suggestions || [];
          if (suggestions.length === 0) {
            list.style.display = 'none';
            return;
          }

          list.innerHTML = '';
          suggestions.forEach(item => {
            const row = document.createElement('div');
            row.className = 'places-autocomplete-item';
            row.innerHTML = `
              <div class="places-title">📍 ${escapeHtml(item.title || '')}</div>
              ${item.subtitle ? `<div class="places-subtitle">${escapeHtml(item.subtitle)}</div>` : ''}
            `;
            row.addEventListener('click', async () => {
              list.style.display = 'none';
              try {
                const resolveRes = await fetch(`/api/places/resolve?place_id=${encodeURIComponent(item.place_id)}`);
                if (resolveRes.ok) {
                  const rData = await resolveRes.json();
                  const place = rData.place;
                  if (place) {
                    if (place.society_name) currentAgreementState.fields.society_name = { value: place.society_name, source: 'user_explicit', status: 'confirmed' };
                    if (place.property_address) currentAgreementState.fields.property_address = { value: place.property_address, source: 'user_explicit', status: 'confirmed' };
                    if (place.city) currentAgreementState.fields.city = { value: place.city, source: 'user_explicit', status: 'confirmed' };
                    if (place.pincode) currentAgreementState.fields.pincode = { value: place.pincode, source: 'user_explicit', status: 'confirmed' };
                    if (place.state) currentAgreementState.fields.state = { value: place.state, source: 'user_explicit', status: 'confirmed' };

                    syncDrawerInputs();
                    updateReadinessUI(currentAgreementState.readiness || {});
                    refreshDocumentPreview();
                  }
                }
              } catch (err) {
                console.warn('[Places] Resolve error:', err);
              }
            });
            list.appendChild(row);
          });
          list.style.display = 'block';
        } catch (e) {
          console.warn('[Places] Autocomplete error:', e);
        }
      }, 300);
    });

    document.addEventListener('click', (e) => {
      if (!wrapper.contains(e.target)) {
        list.style.display = 'none';
      }
    });
  });
}

/**
 * Setup Google Places Autocomplete directly on the AI Chat Input Bar
 */
function setupChatAddressAutocomplete() {
  const chatInput = document.getElementById('studioChatInput');
  const dropdown = document.getElementById('addressAutocompleteDropdown');
  if (!chatInput || !dropdown) return;

  let debounceTimer = null;
  let activeIndex = -1;
  let currentSuggestions = [];
  let detectedPrefix = '';

  // Extract flat/door/house prefix if present (e.g. "Flat 402, Block B, ")
  function splitPrefixAndQuery(text) {
    const trimmed = text.trim();
    // Check for unit prefix patterns
    const prefixMatch = text.match(/^(.*?(?:flat|unit|villa|apt|apartment|door|plot|#|house|room|flt)\s*(?:no\.?|#|num\.?|\s:?)?\s*[A-Za-z0-9\-/]+\s*(?:,\s*(?:block|tower|wing|phase)\s*[A-Za-z0-9\-]+)?\s*,\s*)(.*)$/i);
    if (prefixMatch) {
      return {
        prefix: prefixMatch[1],
        query: prefixMatch[2].trim()
      };
    }
    return {
      prefix: '',
      query: trimmed
    };
  }

  function hideDropdown() {
    dropdown.style.display = 'none';
    dropdown.innerHTML = '';
    activeIndex = -1;
    currentSuggestions = [];
  }

  function isAddressStepActive() {
    // Check if the latest question focus area is an address step
    if (window.lastNextInteraction) {
      const focus = window.lastNextInteraction.focus_area || '';
      const fields = window.lastNextInteraction.target_fields || [];
      if (focus.includes('address') || fields.some(f => f.includes('address') || f.includes('property'))) {
        return true;
      }
    }
    // Or if the user types explicit address keywords
    const val = (chatInput.value || '').toLowerCase();
    const addrKeywords = ['flat', 'apartment', 'society', 'nagar', 'colony', 'road', 'street', 'layout', 'enclave', 'towers', 'heights', 'residency', 'villas', 'sector', 'block', 'phase'];
    return addrKeywords.some(kw => val.includes(kw));
  }

  chatInput.addEventListener('input', () => {
    clearTimeout(debounceTimer);
    const rawVal = chatInput.value || '';
    if (rawVal.trim().length < 3 || !isAddressStepActive()) {
      hideDropdown();
      return;
    }

    const { prefix, query } = splitPrefixAndQuery(rawVal);
    detectedPrefix = prefix;

    const searchQuery = query.length >= 2 ? query : rawVal.trim();
    if (searchQuery.length < 2) {
      hideDropdown();
      return;
    }

    debounceTimer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/places/autocomplete?query=${encodeURIComponent(searchQuery)}`);
        if (!res.ok) {
          hideDropdown();
          return;
        }
        const data = await res.json();
        currentSuggestions = data.suggestions || [];
        if (currentSuggestions.length === 0) {
          hideDropdown();
          return;
        }

        dropdown.innerHTML = '';
        activeIndex = -1;

        currentSuggestions.forEach((item, idx) => {
          const row = document.createElement('div');
          row.className = 'autocomplete-item';
          row.setAttribute('data-idx', idx);
          row.innerHTML = `
            <div class="autocomplete-icon">📍</div>
            <div class="autocomplete-text">
              <div class="autocomplete-title">${escapeHtml(item.title || item.description || '')}</div>
              ${item.subtitle ? `<div class="autocomplete-subtitle">${escapeHtml(item.subtitle)}</div>` : ''}
            </div>
          `;

          row.addEventListener('click', () => {
            selectSuggestion(item);
          });

          dropdown.appendChild(row);
        });

        dropdown.style.display = 'block';
      } catch (err) {
        console.warn('[Chat Places] Autocomplete error:', err);
        hideDropdown();
      }
    }, 280);
  });

  function selectSuggestion(item) {
    const selectedDesc = item.description || item.title || '';
    const fullAddress = detectedPrefix ? `${detectedPrefix}${selectedDesc}` : selectedDesc;
    chatInput.value = fullAddress;
    hideDropdown();
    chatInput.focus();
    chatInput.setSelectionRange(chatInput.value.length, chatInput.value.length);
  }

  // Keyboard navigation inside dropdown
  chatInput.addEventListener('keydown', (e) => {
    if (dropdown.style.display === 'none' || currentSuggestions.length === 0) {
      return;
    }

    const items = dropdown.querySelectorAll('.autocomplete-item');
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      activeIndex = (activeIndex + 1) % items.length;
      updateActiveItem(items);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      activeIndex = (activeIndex - 1 + items.length) % items.length;
      updateActiveItem(items);
    } else if (e.key === 'Enter') {
      if (activeIndex >= 0 && activeIndex < currentSuggestions.length) {
        e.preventDefault();
        e.stopImmediatePropagation();
        selectSuggestion(currentSuggestions[activeIndex]);
      }
    } else if (e.key === 'Escape') {
      hideDropdown();
    }
  });

  function updateActiveItem(items) {
    items.forEach((it, i) => {
      if (i === activeIndex) {
        it.classList.add('selected');
        it.scrollIntoView({ block: 'nearest' });
      } else {
        it.classList.remove('selected');
      }
    });
  }

  // Hide on click outside
  document.addEventListener('click', (e) => {
    if (!dropdown.contains(e.target) && e.target !== chatInput) {
      hideDropdown();
    }
  });
}

// Hook setup into document load
document.addEventListener('DOMContentLoaded', () => {
  setupPlacesAutocomplete();
  setupChatAddressAutocomplete();
});

/**
 * Trigger the hidden HTML5 date picker when calendar icon is clicked
 */
function triggerStudioDatePicker() {
  const picker = document.getElementById('studioDatePickerInput');
  if (!picker) return;

  const today = new Date().toISOString().split('T')[0];
  if (!picker.value) {
    picker.value = today;
  }

  if (typeof picker.showPicker === 'function') {
    try {
      picker.showPicker();
    } catch (e) {
      picker.click();
    }
  } else {
    picker.focus();
    picker.click();
  }
}

/**
 * Handle date chosen from calendar popover
 */
async function handleStudioDateSelected(input) {
  if (!input || !input.value) return;
  const rawDate = input.value; // e.g. "2026-10-01"
  const parts = rawDate.split('-');
  if (parts.length === 3) {
    const formatted = `${parts[2]}-${parts[1]}-${parts[0]}`; // "01-10-2026"
    
    // Check if tenure exists to formulate natural sentence
    const hasTenure = Boolean(currentAgreementState?.fields?.tenure_months?.value);
    let msg = `Start date is ${formatted}`;
    if (!hasTenure) {
      msg = `Start from ${formatted} for 11 months`;
    }
    
    const chatInput = document.getElementById('studioChatInput');
    if (chatInput) {
      chatInput.value = msg;
    }
    
    // Send message to AI engine
    await sendUserMessage(msg);
  }
}

window.triggerStudioDatePicker = triggerStudioDatePicker;
window.handleStudioDateSelected = handleStudioDateSelected;

/**
 * Toggle Structured Form Inspector Drawer
 */
function toggleFormDrawer() {
  const drawer = document.getElementById('studioDrawer');
  const backdrop = document.getElementById('studioDrawerBackdrop');
  if (!drawer) return;
  const isOpen = drawer.classList.contains('open');
  if (isOpen) {
    drawer.classList.remove('open');
    if (backdrop) backdrop.classList.remove('open');
  } else {
    drawer.classList.add('open');
    if (backdrop) backdrop.classList.add('open');
    syncDrawerInputs();
  }
}
window.toggleFormDrawer = toggleFormDrawer;

/**
 * Save progress toast
 */
function saveAgreementDraft() {
  localStorage.setItem('agreementai_studio_draft', JSON.stringify(currentAgreementState));
  appendChatBubble('assistant', '💾 **Progress saved!** Your draft is safely preserved.');
}
window.saveAgreementDraft = saveAgreementDraft;

/**
 * Clear draft and restart from fresh
 */
function clearDraftAndRestart() {
  localStorage.removeItem('agreementai_studio_draft');
  const params = new URLSearchParams(window.location.search);
  const type = params.get('type') || 'simple_rental';
  const state = params.get('state') || 'KA';
  window.location.href = `/create?type=${encodeURIComponent(type)}&state=${encodeURIComponent(state)}&fresh=1`;
}
window.clearDraftAndRestart = clearDraftAndRestart;
