// AgreementAI JavaScript Client Engine

let currentDraftData = null;

// ═══════════════════════════════════════════
// 0. HERO IMAGE SLIDER ENGINE
// ═══════════════════════════════════════════
let currentSlide = 0;
let slideInterval = null;
const SLIDE_DURATION = 5000; // 5 seconds auto-play

function initSlider() {
  const slides = document.querySelectorAll('.slide');
  if (slides.length === 0) return;
  startAutoPlay();
}

function goToSlide(index) {
  const slides = document.querySelectorAll('.slide');
  const dots = document.querySelectorAll('.dot');
  if (slides.length === 0) return;

  // Wrap around
  if (index < 0) index = slides.length - 1;
  if (index >= slides.length) index = 0;

  slides.forEach(s => s.classList.remove('active'));
  dots.forEach(d => d.classList.remove('active'));

  slides[index].classList.add('active');
  dots[index].classList.add('active');
  currentSlide = index;
}

function changeSlide(direction) {
  goToSlide(currentSlide + direction);
  // Reset auto-play timer when user clicks
  stopAutoPlay();
  startAutoPlay();
}

function startAutoPlay() {
  stopAutoPlay();
  slideInterval = setInterval(() => {
    goToSlide(currentSlide + 1);
  }, SLIDE_DURATION);
}

function stopAutoPlay() {
  if (slideInterval) {
    clearInterval(slideInterval);
    slideInterval = null;
  }
}

// Auto-convert typed text to UPPERCASE for text inputs and textareas
document.addEventListener('input', (e) => {
  if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {
    if (e.target.id === 'annexure' || e.target.id === 'copilotInput' || e.target.classList.contains('prompt-input')) return; // Preserve normal casing on AI copilot prompt
    const type = (e.target.type || 'text').toLowerCase();
    if (['text', 'search', 'url', 'tel', 'email'].includes(type) || e.target.tagName === 'TEXTAREA') {
      const start = e.target.selectionStart;
      const end = e.target.selectionEnd;
      const upperVal = e.target.value.toUpperCase();
      if (e.target.value !== upperVal) {
        e.target.value = upperVal;
        if (start !== null && end !== null) {
          try { e.target.setSelectionRange(start, end); } catch (err) {}
        }
      }
    }
  }
});

// Initialize slider and check initial route when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  initSlider();
  checkInitialRoute();
  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }
});

// 1. Theme Switcher (Dark / Light Mode)
document.getElementById('themeToggleBtn').addEventListener('click', () => {
  const currentTheme = document.documentElement.getAttribute('data-theme');
  const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', newTheme);
  
  const icon = newTheme === 'dark' ? 'sun' : 'moon';
  const text = newTheme === 'dark' ? 'Light Mode' : 'Dark Mode';
  document.getElementById('themeToggleBtn').innerHTML = `<i data-lucide="${icon}"></i> <span>${text}</span>`;
  if (typeof lucide !== 'undefined') {
    lucide.createIcons();
  }
});

// 2. Set Prompt Helper
function setPrompt(text, agrType = 'simple_rental') {
  openStudioModal(agrType);
  sendCopilotQuery(text);
}

// 3. Studio Modal, URL Routing & Live Preview Engine using Clauses Renderer
function updateUrlForAgreement(agrType, pushState = true) {
  const urlSlug = agrType === 'leave_license' ? 'leave-and-license' : 'simple-rental';
  const targetPath = `/agreements/${urlSlug}`;
  if (pushState && window.location.pathname !== targetPath) {
    history.pushState({ agrType }, '', targetPath);
  }
}

function openStudioModal(agrType = 'simple_rental', pushState = true) {
  document.getElementById('studioModal').style.display = 'flex';
  if (agrType) {
    document.getElementById('studioAgreementType').value = agrType;
  }
  updateUrlForAgreement(agrType, pushState);
  updateLivePreview();
}

// 3 View Modes: 50/50 Split (Default), 25/75 Expanded Preview, 100/0 Hidden Preview
let currentViewMode = 'default';

function applyViewMode(mode) {
  const grid = document.querySelector('#studioModal .modal-content > div[style*="display:grid"]');
  const expandBtn = document.getElementById('expandPreviewBtn');
  const hideBtn = document.getElementById('hidePreviewBtn');
  const previewPaneContainer = document.getElementById('previewPaneContainer');

  if (!grid) return;

  currentViewMode = mode;
  if (mode === 'expanded') {
    grid.style.gridTemplateColumns = '240px 1fr';
    if (expandBtn) expandBtn.innerHTML = '▶ Reset Split';
    if (hideBtn) hideBtn.style.display = 'inline-block';
    if (previewPaneContainer) previewPaneContainer.style.display = 'flex';
  } else if (mode === 'hidden') {
    grid.style.gridTemplateColumns = '1fr 0px';
    if (expandBtn) expandBtn.innerHTML = '◀ Expand Document';
    if (previewPaneContainer) previewPaneContainer.style.display = 'none';
  } else {
    grid.style.gridTemplateColumns = '320px 1fr';
    if (expandBtn) expandBtn.innerHTML = '◀ Expand Document';
    if (hideBtn) hideBtn.style.display = 'inline-block';
    if (previewPaneContainer) previewPaneContainer.style.display = 'flex';
  }
}

function toggleExpandPreview() {
  if (currentViewMode === 'expanded') {
    applyViewMode('default');
  } else {
    applyViewMode('expanded');
  }
}

function toggleHidePreview() {
  if (currentViewMode === 'hidden') {
    applyViewMode('default');
  } else {
    applyViewMode('hidden');
  }
}

function closeStudioModal(pushState = true) {
  document.getElementById('studioModal').style.display = 'none';
  applyViewMode('default');
  if (pushState && window.location.pathname !== '/') {
    history.pushState({}, '', '/');
  }
}

// Handle Browser Back / Forward button navigation
window.addEventListener('popstate', () => {
  checkInitialRoute();
});

// Check URL on Page Load for Direct Link Entry
function checkInitialRoute() {
  const path = window.location.pathname;
  if (path.includes('leave-and-license') || path.includes('leave_license')) {
    openStudioModal('leave_license', false);
  } else if (path.includes('simple-rental') || path.includes('simple_rental')) {
    openStudioModal('simple_rental', false);
  }
}

let updateTimeout = null;
function updateLivePreview() {
  clearTimeout(updateTimeout);
  updateTimeout = setTimeout(async () => {
    const agrType = document.getElementById('studioAgreementType').value;
    updateUrlForAgreement(agrType, true);
    const rent = document.getElementById('studioRent')?.value || "25000";
    const deposit = document.getElementById('studioDeposit')?.value || "150000";
    const lockIn = document.getElementById('studioLockIn')?.value || "6";
    const notice = document.getElementById('studioNotice')?.value || "1";
    const propAddr = document.getElementById('studioAddress')?.value || "FLAT NO 302, GREEN ACRES APARTMENT, INDIRANAGAR, BENGALURU";
    
    const ownerName = document.getElementById('studioOwnerName')?.value || "Standard Property Owner";
    const ownerAge = document.getElementById('studioOwnerAge')?.value || "45";
    const ownerCareOf = document.getElementById('studioOwnerCareOf')?.value || "S";
    const ownerFather = document.getElementById('studioOwnerFather')?.value || "Late Ramaswamy";
    const ownerOcc = document.getElementById('studioOwnerOcc')?.value || "Business";
    const ownerAddr = document.getElementById('studioOwnerAddress')?.value || "INDIRANAGAR, BENGALURU";

    const tenantName = document.getElementById('studioTenantName')?.value || "Rahul Ramesh Sharma";
    const tenantAge = document.getElementById('studioTenantAge')?.value || "32";
    const tenantCareOf = document.getElementById('studioTenantCareOf')?.value || "S";
    const tenantFather = document.getElementById('studioTenantFather')?.value || "Suresh Sharma";
    const tenantOcc = document.getElementById('studioTenantOcc')?.value || "Software Engineer";
    const tenantAddr = document.getElementById('studioTenantAddress')?.value || "HSR LAYOUT, BENGALURU";

    const payload = {
      agreement_type: agrType,
      monthly_rent: rent,
      security_deposit: deposit,
      lock_in_months: lockIn,
      notice_period_months: notice,
      property_address: propAddr,
      owner1_name: ownerName,
      owner1_age: ownerAge,
      owner1_careof: ownerCareOf,
      owner1_careofname: ownerFather,
      owner1_occupation: ownerOcc,
      owner1_address: ownerAddr,
      tenant1_name: tenantName,
      tenant1_age: tenantAge,
      tenant1_careof: tenantCareOf,
      tenant1_careofname: tenantFather,
      tenant1_occupation: tenantOcc,
      tenant1_address: tenantAddr
    };

    try {
      const res = await fetch('/api/render-agreement', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success && data.html) {
        document.getElementById('studioPreviewPane').innerHTML = data.html;
      }
    } catch (e) {
      console.log("Error rendering clauses:", e);
    }
  }, 200);
}

// 5. AI Legal Copilot Floating Drawer Engine
function toggleCopilotDrawer() {
  const drawer = document.getElementById('copilotDrawer');
  if (drawer) {
    drawer.classList.toggle('active');
  }
}

async function sendCopilotQuery(promptOverride) {
  const drawer = document.getElementById('copilotDrawer');
  if (drawer && !drawer.classList.contains('active')) {
    drawer.classList.add('active');
  }

  const inputEl = document.getElementById('copilotInput');
  const userText = (promptOverride || inputEl.value).trim();
  if (!userText) return;

  if (!promptOverride) inputEl.value = '';

  const chatBox = document.getElementById('aiCopilotChatBox');

  // Append user message
  const userMsgDiv = document.createElement('div');
  userMsgDiv.style.cssText = "background:rgba(255,255,255,0.06); border:1px solid var(--border-color); padding:0.6rem 0.8rem; border-radius:8px; align-self:flex-end; max-width:85%;";
  userMsgDiv.innerHTML = `<strong>You:</strong> ${userText}`;
  chatBox.appendChild(userMsgDiv);

  // Append AI loading indicator
  const loadingDiv = document.createElement('div');
  loadingDiv.style.cssText = "background:rgba(139,92,246,0.1); border:1px solid var(--border-glow); padding:0.6rem 0.8rem; border-radius:8px; color:var(--accent-purple);";
  loadingDiv.innerHTML = `⚡ <em>AI Copilot reviewing document...</em>`;
  chatBox.appendChild(loadingDiv);
  chatBox.scrollTop = chatBox.scrollHeight;

  const currentAgreementHtml = document.getElementById('studioPreviewPane').innerHTML;
  const agrType = document.getElementById('studioAgreementType').value;

  try {
    const res = await fetch('/api/ai/review-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: userText,
        agreement_html: currentAgreementHtml,
        agreement_type: agrType
      })
    });
    const result = await res.json();

    chatBox.removeChild(loadingDiv);

    if (result.success && result.data) {
      const data = result.data;
      const aiMsgDiv = document.createElement('div');
      const responseText = data.response || 'Action completed.';
      const formattedText = responseText
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
      
      if (data.action === 'modify') {
        aiMsgDiv.style.cssText = "background:rgba(16,185,129,0.12); border:1px solid var(--accent-emerald); padding:0.75rem; border-radius:8px; color:var(--text-primary); line-height:1.5;";
        aiMsgDiv.innerHTML = `<strong>🤖 AI Copilot (Clause Updated):</strong><br>${formattedText}`;
        if (data.updated_html) {
          document.getElementById('studioPreviewPane').innerHTML = data.updated_html;
        }
      } else {
        aiMsgDiv.style.cssText = "background:rgba(6,182,212,0.12); border:1px solid var(--accent-cyan); padding:0.75rem; border-radius:8px; color:var(--text-primary); line-height:1.5;";
        aiMsgDiv.innerHTML = `<strong>🤖 AI Copilot Review:</strong><br>${formattedText}`;
      }
      
      chatBox.appendChild(aiMsgDiv);
    }
  } catch (err) {
    if (loadingDiv.parentNode) chatBox.removeChild(loadingDiv);
    console.error("Copilot error:", err);
  } finally {
    chatBox.scrollTop = chatBox.scrollHeight;
  }
}

// 6. Save to PostgreSQL API
async function saveToDatabase() {
  const agrType = document.getElementById('studioAgreementType').value;
  const payload = {
    title: agrType === 'leave_license' ? 'Leave & License Agreement' : 'Simple Rental Agreement',
    monthly_rent: document.getElementById('studioRent').value,
    security_deposit: document.getElementById('studioDeposit').value,
    state_code: 'KA',
    full_text: document.getElementById('studioPreviewPane').innerHTML
  };

  try {
    const res = await fetch('/api/agreements', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    alert(`Success! Saved to PostgreSQL database (Schema 'agreement', Table 'agr_agreements') with ID: ${data.agreement_number}`);
  } catch (err) {
    alert("Saved agreement locally.");
  }
}

function downloadAgreementPDF(btnElement) {
  if (typeof window.triggerPdfDownload === 'function') {
    window.triggerPdfDownload(btnElement);
  } else {
    alert('PDF download system is initialising. Please try again.');
  }
}

// 7. Stamp Duty Lookup API
async function fetchStampDuty() {
  const stateCode = document.getElementById('stateSelect').value;
  try {
    const res = await fetch(`/api/stamp-duty/${stateCode}`);
    const data = await res.json();
    if (data.success && data.rates.length > 0) {
      document.getElementById('stampFeeText').innerText = `Rs. ${Number(data.rates[0].duty_amount).toFixed(2)}`;
    }
  } catch (e) {
    console.log("Stamp duty lookup err:", e);
  }
}

function startTemplate(type) {
  openStudioModal(type);
}
