/**
 * static/js/safekeys_esign.js — Digital eSign Integration Controller
 * ===========================================================================
 * Orchestrates digital signature requests, invitation modals, signer-level
 * camera/photo verification toggles, interactive multi-page PDF visual signature
 * placement (matches Leegality / DocuSign workflow), status polling, and signed PDF downloads.
 */

class SafeKeysEsignController {
  constructor() {
    this.currentDocumentId = null;
    this.currentFormData = null;
    this.currentInvitees = [];
    this.autoPlacement = true;
    this.pollInterval = null;

    // Interactive PDF Placement State
    this.pdfDoc = null;
    this.pdfBytes = null;
    this.currentPageNum = 1;
    this.totalPages = 1;
    this.pdfScale = 1.0;
    this.pdfPageWidthPt = 595;
    this.pdfPageHeightPt = 842;
    this.isRendering = false;

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.initModalDom());
    } else {
      this.initModalDom();
    }
  }

  initModalDom() {
    // If an existing modal exists, remove it to ensure fresh DOM
    const oldModal = document.getElementById('skEsignModalOverlay');
    if (oldModal) {
      oldModal.remove();
    }
    if (!document.body) return;

    const modalHtml = `
      <div id="skEsignModalOverlay" class="sk-modal-overlay" style="display: none;">
        <div class="sk-esign-modal" id="skEsignModalContainer">
          <!-- Modal Header -->
          <div class="sk-esign-header">
            <div class="sk-esign-header-info">
              <div class="sk-badge-esign">
                <span class="sk-pulse-dot"></span>
                <span>Aadhaar &amp; Digital eSign</span>
              </div>
              <h3 class="sk-esign-title" id="skModalTitle">Digital Signature Execution</h3>
              <p class="sk-esign-subtitle" id="skModalSubtitle">Legally binding eSignatures compliant with Information Technology Act, 2000</p>
            </div>
            <button type="button" class="sk-modal-close-btn" onclick="safeKeysEsign.closeModal()" title="Close">✕</button>
          </div>

          <!-- Modal Body -->
          <div class="sk-esign-body">
            <!-- Step 1: Signer & Verification Configuration -->
            <div id="skEsignConfigStep" class="sk-config-step" style="display: none;">
              <div class="sk-config-intro">
                Select <strong>signature mode</strong> (Aadhaar / Virtual) and camera verification for each party. Signatures will be placed cleanly on the agreement.
              </div>

              <div class="sk-config-signers-list" id="skConfigSignersList">
                <!-- Dynamically populated per signer -->
              </div>

              <!-- Signature Placement Section -->
              <div class="sk-placement-section">
                <div class="sk-placement-header">
                  <div class="sk-placement-info">
                    <span class="sk-placement-icon">📍</span>
                    <div>
                      <strong class="sk-placement-title">Signature Placement on Document</strong>
                      <p class="sk-placement-desc">Position and adjust signatures directly on the agreement PDF pages.</p>
                    </div>
                  </div>
                  <button type="button" class="sk-btn sk-btn-secondary sk-btn-xs" onclick="safeKeysEsign.openPlacementCanvas()">
                    ✏️ Visual Placement on PDF
                  </button>
                </div>
                <div class="sk-placement-toggle-row">
                  <label class="sk-global-option-item">
                    <input type="checkbox" id="skAutoPlacement" checked onchange="safeKeysEsign.toggleAutoPlacement(this.checked)">
                    <span><strong>Smart Auto-Placement</strong> (Owners Left Column · Tenants Right Column on Execution Page)</span>
                  </label>
                </div>
                <div id="skPlacementSummary" class="sk-placement-summary">
                  <!-- Live coordinates chips populated dynamically -->
                </div>
              </div>

              <!-- Global Security Options -->
              <div class="sk-global-options-box">
                <label class="sk-global-option-item">
                  <input type="checkbox" id="skGlobalLiveliness" checked>
                  <span><strong>AI Smart Liveness Check</strong> (detects live presence and prevents photo spoofing)</span>
                </label>
                <label class="sk-global-option-item">
                  <input type="checkbox" id="skGlobalFaceAuth" checked>
                  <span><strong>Allow Aadhaar Face RD Auth</strong> (direct biometric match against UIDAI records)</span>
                </label>
                <label class="sk-global-option-item">
                  <input type="checkbox" id="skGlobalGps" checked>
                  <span><strong>Record Signer GPS Location</strong> (logs timestamped device coordinates in audit trail)</span>
                </label>
              </div>
            </div>

            <!-- Sub-View: Interactive Multi-Page PDF Visual Placement Canvas -->
            <div id="skPlacementDrawerView" class="sk-placement-modal-view" style="display: none;">
              <!-- Toolbar -->
              <div class="sk-pdf-placement-toolbar">
                <div class="sk-pdf-toolbar-group">
                  <div>
                    <div class="sk-pdf-toolbar-title">
                      <span>📍 Visual Signature Placement</span>
                    </div>
                    <span class="sk-pdf-toolbar-subtitle">Drag and position signature boxes for all signers directly on the document.</span>
                  </div>
                </div>

                <div class="sk-pdf-toolbar-group">
                  <!-- Page Navigation -->
                  <div class="sk-pdf-page-nav">
                    <button type="button" class="sk-pdf-nav-btn" id="skPdfPrevBtn" onclick="safeKeysEsign.changePage(-1)" title="Previous Page">◀</button>
                    <span class="sk-pdf-page-indicator" id="skPdfPageIndicator">Page 1 of 1</span>
                    <button type="button" class="sk-pdf-nav-btn" id="skPdfNextBtn" onclick="safeKeysEsign.changePage(1)" title="Next Page">▶</button>
                  </div>

                  <!-- Zoom Controls -->
                  <button type="button" class="sk-pdf-zoom-btn" onclick="safeKeysEsign.zoom(-0.15)" title="Zoom Out">🔍−</button>
                  <button type="button" class="sk-pdf-zoom-btn" onclick="safeKeysEsign.zoom(0.15)" title="Zoom In">🔍+</button>
                  <button type="button" class="sk-pdf-zoom-btn" onclick="safeKeysEsign.zoom('fit')" title="Fit Width">↔ Fit</button>

                  <!-- Actions -->
                  <button type="button" class="sk-btn sk-btn-secondary sk-btn-xs" onclick="safeKeysEsign.resetDefaultPlacement()">
                    🔄 Reset Layout
                  </button>
                  <button type="button" class="sk-btn sk-btn-primary sk-btn-xs" onclick="safeKeysEsign.closePlacementCanvas()">
                    ✓ Done / Apply
                  </button>
                </div>
              </div>

              <!-- Signers Legend & Add Placements Bar -->
              <div class="sk-pdf-signers-bar" id="skPdfSignersBar">
                <span class="sk-pdf-signers-bar-label">Signers:</span>
                <!-- Signer chips injected dynamically -->
              </div>

              <!-- PDF Document Viewport Area -->
              <div class="sk-pdf-viewport-container" id="skPdfViewportContainer">
                <div class="sk-pdf-loading-overlay" id="skPdfLoadingOverlay">
                  <div class="sk-pdf-loading-spinner"></div>
                  <span style="font-size: 13px; font-weight: 600;">Rendering Document PDF Pages...</span>
                </div>

                <div class="sk-pdf-page-card" id="skPdfPageCard" style="display: none;">
                  <canvas id="skPdfCanvas" class="sk-pdf-page-canvas"></canvas>
                  <div id="skPdfSigLayer" class="sk-pdf-sig-layer"></div>
                </div>
              </div>

              <!-- Quick Snap Presets Tray -->
              <div class="sk-pdf-placement-actions">
                <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                  <span style="font-size: 11px; color: #94A3B8; font-weight: 600;">Quick Snap:</span>
                  <button type="button" class="sk-quick-snap-btn" onclick="safeKeysEsign.snapPlacement('dual_bottom')">
                    ↔ Dual Bottom (Lessors Left · Lessees Right)
                  </button>
                  <button type="button" class="sk-quick-snap-btn" onclick="safeKeysEsign.snapPlacement('bottom_left')">
                    ↙ Bottom Left
                  </button>
                  <button type="button" class="sk-quick-snap-btn" onclick="safeKeysEsign.snapPlacement('bottom_right')">
                    ↘ Bottom Right
                  </button>
                  <button type="button" class="sk-quick-snap-btn" onclick="safeKeysEsign.snapPlacement('margin_initial')">
                    📑 Right Margin Initial
                  </button>
                </div>
                <div style="font-size: 11px; color: #64748B;">
                  Page Coordinates: <code style="color: #34D399; font-weight: 700;">595 × 842 pt (A4)</code>
                </div>
              </div>
            </div>

            <!-- Loading State -->
            <div id="skEsignLoading" class="sk-esign-loading" style="display: none;">
              <div class="sk-spinner"></div>
              <p class="sk-esign-loading-text">Generating document &amp; preparing digital eSign invitations...</p>
            </div>

            <!-- Error State -->
            <div id="skEsignError" class="sk-alert sk-alert-danger" style="display: none;">
              <div style="font-weight: 700; margin-bottom: 4px;">eSign Dispatch Notice</div>
              <div id="skEsignErrorMessage"></div>
              <div style="margin-top: 10px;">
                <button type="button" class="sk-btn sk-btn-secondary sk-btn-sm" onclick="safeKeysEsign.resetToConfig()">
                  ← Back to Signer Settings
                </button>
              </div>
            </div>

            <!-- Step 2: Content Area (Dispatched / Signed Status) -->
            <div id="skEsignContent" style="display: none;">
              <div class="sk-esign-status-bar" id="skEsignStatusBar">
                <div class="sk-status-col">
                  <span class="sk-status-label">Document Status:</span>
                  <span id="skDocStatusBadge" class="sk-status-pill pill-sent">SENT</span>
                </div>
                <div class="sk-status-col">
                  <span class="sk-status-label">Document ID:</span>
                  <code id="skDocIdCode" class="sk-doc-id"></code>
                </div>
              </div>

              <div class="sk-invitees-list" id="skInviteesList">
                <!-- Dynamically populated -->
              </div>

              <!-- Completion Banner -->
              <div id="skEsignCompletedBanner" class="sk-alert sk-alert-success" style="display: none; margin-top: 16px;">
                🎉 <strong>Agreement Fully Executed!</strong> All parties have digitally signed this agreement. You can now download the official signed PDF and audit trail.
              </div>
            </div>
          </div>

          <!-- Modal Footer -->
          <div class="sk-esign-footer" id="skEsignModalFooter">
            <button type="button" class="sk-btn sk-btn-secondary" id="skEsignCancelBtn" onclick="safeKeysEsign.closeModal()">Cancel</button>
            <button type="button" class="sk-btn sk-btn-primary" id="skEsignDispatchBtn" onclick="safeKeysEsign.submitEsignDispatch()" style="display: none;">
              🚀 Send eSign Invitations
            </button>
            <button type="button" class="sk-btn sk-btn-secondary" id="skRefreshStatusBtn" onclick="safeKeysEsign.refreshStatus()" style="display: none;">
              🔄 Refresh Status
            </button>
            <a id="skDownloadSignedPdfBtn" class="sk-btn sk-btn-primary" style="display: none;" target="_blank">
              📥 Download Signed PDF
            </a>
          </div>
        </div>
      </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHtml);
  }

  showModal() {
    this.initModalDom();
    const overlay = document.getElementById('skEsignModalOverlay');
    if (overlay) {
      overlay.style.display = 'flex';
      document.body.style.overflow = 'hidden';
    }
  }

  closeModal() {
    const overlay = document.getElementById('skEsignModalOverlay');
    if (overlay) {
      overlay.style.display = 'none';
      document.body.style.overflow = '';
    }
    const modalContainer = document.getElementById('skEsignModalContainer');
    if (modalContainer) modalContainer.classList.remove('is-expanded');
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }

  extractInviteesFromForm(formData) {
    const invitees = [];
    const pushIfValid = (name, phone, email, role, roleLabel) => {
      if (name && name.trim()) {
        const roleIdx = invitees.filter(i => i.role === role).length;
        const isOwner = role === 'OWNER';
        const x1 = isOwner ? 45 : 345;
        const y1 = 120 + (roleIdx * 75);
        invitees.push({
          name: name.trim(),
          phone: (phone || '').trim(),
          email: (email || '').trim(),
          role: role,
          roleLabel: roleLabel,
          signType: 'AADHAAR', // default Aadhaar eSign
          capturePhoto: true, // default camera live photo capture
          appearances: [
            {
              page: 'L',
              x1: x1,
              y1: y1,
              x2: x1 + 200,
              y2: y1 + 55
            }
          ]
        });
      }
    };

    // Owners 1 to 6
    for (let i = 1; i <= 6; i++) {
      const name = formData[`owner${i}_name`] || (i === 1 ? (formData.owner_name || formData.lessor_name || formData.p5 || formData.P5) : '');
      const phone = formData[`owner${i}_phone`] || (i === 1 ? formData.owner_phone : '');
      const email = formData[`owner${i}_email`] || (i === 1 ? formData.owner_email : '');
      const roleLabel = i === 1 ? 'Primary Lessor (Owner)' : `Co-Lessor (Owner ${i})`;
      pushIfValid(name, phone, email, 'OWNER', roleLabel);
    }

    // Tenants 1 to 6
    for (let i = 1; i <= 6; i++) {
      const name = formData[`tenant${i}_name`] || (i === 1 ? (formData.tenant_name || formData.lessee_name || formData.p8 || formData.P8) : '');
      const phone = formData[`tenant${i}_phone`] || (i === 1 ? formData.tenant_phone : '');
      const email = formData[`tenant${i}_email`] || (i === 1 ? formData.tenant_email : '');
      const roleLabel = i === 1 ? 'Primary Lessee (Tenant)' : `Co-Lessee (Tenant ${i})`;
      pushIfValid(name, phone, email, 'TENANT', roleLabel);
    }

    return invitees;
  }

  // Alias for compatibility with rental_form_core.js and ai_creator_studio.js
  initiateEsignFromForm(formData) {
    this.openEsignModal(formData);
  }

  openEsignModal(formData) {
    this.currentFormData = formData || {};
    this.currentInvitees = this.extractInviteesFromForm(this.currentFormData);

    this.showModal();

    const configStepEl = document.getElementById('skEsignConfigStep');
    const loadingEl = document.getElementById('skEsignLoading');
    const errorEl = document.getElementById('skEsignError');
    const contentEl = document.getElementById('skEsignContent');
    const drawerView = document.getElementById('skPlacementDrawerView');
    const dispatchBtn = document.getElementById('skEsignDispatchBtn');
    const refreshBtn = document.getElementById('skRefreshStatusBtn');
    const modalContainer = document.getElementById('skEsignModalContainer');

    if (modalContainer) modalContainer.classList.remove('is-expanded');
    if (loadingEl) loadingEl.style.display = 'none';
    if (errorEl) errorEl.style.display = 'none';
    if (contentEl) contentEl.style.display = 'none';
    if (drawerView) drawerView.style.display = 'none';
    if (refreshBtn) refreshBtn.style.display = 'none';

    document.getElementById('skModalTitle').innerText = 'Digital Signature Execution';
    document.getElementById('skModalSubtitle').innerText = 'Configure signing mode, camera verification, and placement for each party.';

    if (this.currentInvitees.length === 0) {
      if (errorEl) {
        errorEl.style.display = 'block';
        document.getElementById('skEsignErrorMessage').innerText = 'No valid Landlords or Tenants found in this agreement. Please ensure at least one Owner and Tenant are specified with contact details.';
      }
      if (dispatchBtn) dispatchBtn.style.display = 'none';
      return;
    }

    this.renderSignersConfigList();
    if (configStepEl) configStepEl.style.display = 'flex';
    if (dispatchBtn) dispatchBtn.style.display = 'inline-flex';
  }

  renderSignersConfigList() {
    const listContainer = document.getElementById('skConfigSignersList');
    if (!listContainer) return;
    listContainer.innerHTML = '';

    this.currentInvitees.forEach((inv, idx) => {
      const row = document.createElement('div');
      row.className = 'sk-config-signer-row';
      const signType = inv.signType || 'AADHAAR';
      row.innerHTML = `
        <div class="sk-config-signer-info">
          <span class="sk-config-signer-role">${inv.roleLabel}</span>
          <span class="sk-config-signer-name">${inv.name}</span>
          <div class="sk-config-signer-contact">
            ${inv.phone ? `<span>📱 +91 ${inv.phone}</span>` : ''}
            ${inv.email ? `<span>✉️ ${inv.email}</span>` : ''}
            ${!inv.phone && !inv.email ? `<span style="color:#DC2626;">⚠️ Missing phone and email</span>` : ''}
          </div>
        </div>
        <div class="sk-config-signer-controls">
          <div class="sk-signtype-select-group">
            <label class="sk-control-label" for="skSignType_${idx}">Signature Mode</label>
            <select id="skSignType_${idx}" class="sk-signtype-select" onchange="safeKeysEsign.updateSignerSignType(${idx}, this.value)">
              <option value="AADHAAR" ${signType === 'AADHAAR' ? 'selected' : ''}>🪪 Aadhaar eSign (OTP / Face)</option>
              <option value="VIRTUAL_SIGN" ${signType === 'VIRTUAL_SIGN' ? 'selected' : ''}>✍️ Virtual Sign (OTP + Drawn)</option>
              <option value="ALLOW_EITHER" ${signType === 'ALLOW_EITHER' ? 'selected' : ''}>⚡ Signer's Choice (Either)</option>
            </select>
          </div>
          <div class="sk-camera-toggle-group">
            <span class="sk-camera-label ${inv.capturePhoto ? 'is-active' : 'is-inactive'}" id="skCameraLabel_${idx}">
              ${inv.capturePhoto ? '📷 Camera On' : '⚡ Camera Off'}
            </span>
            <label class="sk-switch" title="Toggle Live Selfie Photo Verification">
              <input type="checkbox" id="skCameraToggle_${idx}" ${inv.capturePhoto ? 'checked' : ''} onchange="safeKeysEsign.updateSignerCamera(${idx}, this.checked)">
              <span class="sk-slider"></span>
            </label>
          </div>
        </div>
      `;
      listContainer.appendChild(row);
    });

    this.updatePlacementSummary();
  }

  updatePlacementSummary() {
    const summaryEl = document.getElementById('skPlacementSummary');
    if (!summaryEl) return;
    summaryEl.innerHTML = '';
    this.currentInvitees.forEach(inv => {
      const apps = inv.appearances && inv.appearances.length > 0 ? inv.appearances : [{ page: 'L', x1: 45, y1: 120 }];
      apps.forEach(app => {
        const chip = document.createElement('span');
        chip.className = 'sk-placement-chip';
        chip.innerHTML = `<span>${inv.role === 'OWNER' ? '🏠' : '👤'} ${inv.name.split(' ')[0]}:</span> <code>Pg ${app.page} (${app.x1}, ${app.y1})</code>`;
        summaryEl.appendChild(chip);
      });
    });
  }

  toggleAutoPlacement(isChecked) {
    this.autoPlacement = isChecked;
    if (isChecked) {
      this.resetDefaultPlacement();
    }
  }

  updateSignerSignType(idx, signType) {
    if (this.currentInvitees[idx]) {
      this.currentInvitees[idx].signType = signType;
    }
  }

  updateSignerCamera(idx, isChecked) {
    if (this.currentInvitees[idx]) {
      this.currentInvitees[idx].capturePhoto = isChecked;
      const labelEl = document.getElementById(`skCameraLabel_${idx}`);
      if (labelEl) {
        labelEl.innerText = isChecked ? '📷 Camera On' : '⚡ Camera Off';
        labelEl.className = `sk-camera-label ${isChecked ? 'is-active' : 'is-inactive'}`;
      }
    }
  }

  /* ─────────────────────────────────────────────────────────────────────────
     Interactive PDF Placement Engine (Matching Leegality / DocuSign Video)
     ───────────────────────────────────────────────────────────────────────── */

  async ensurePdfJs() {
    if (window.pdfjsLib) return window.pdfjsLib;
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js';
      script.onload = () => {
        if (window.pdfjsLib) {
          window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
          resolve(window.pdfjsLib);
        } else {
          reject(new Error('Failed to initialize pdfjsLib'));
        }
      };
      script.onerror = () => reject(new Error('Failed to load PDF.js from CDN'));
      document.head.appendChild(script);
    });
  }

  async openPlacementCanvas() {
    const configStepEl = document.getElementById('skEsignConfigStep');
    const drawerView = document.getElementById('skPlacementDrawerView');
    const dispatchBtn = document.getElementById('skEsignDispatchBtn');
    const modalFooter = document.getElementById('skEsignModalFooter');
    const modalContainer = document.getElementById('skEsignModalContainer');

    if (configStepEl) configStepEl.style.display = 'none';
    if (dispatchBtn) dispatchBtn.style.display = 'none';
    if (modalFooter) modalFooter.style.display = 'none';
    if (drawerView) drawerView.style.display = 'flex';
    if (modalContainer) modalContainer.classList.add('is-expanded');

    await this.loadAndRenderPdfDocument();
  }

  closePlacementCanvas() {
    const configStepEl = document.getElementById('skEsignConfigStep');
    const drawerView = document.getElementById('skPlacementDrawerView');
    const dispatchBtn = document.getElementById('skEsignDispatchBtn');
    const modalFooter = document.getElementById('skEsignModalFooter');
    const modalContainer = document.getElementById('skEsignModalContainer');

    if (drawerView) drawerView.style.display = 'none';
    if (configStepEl) configStepEl.style.display = 'flex';
    if (dispatchBtn) dispatchBtn.style.display = 'inline-flex';
    if (modalFooter) modalFooter.style.display = 'flex';
    if (modalContainer) modalContainer.classList.remove('is-expanded');

    this.updatePlacementSummary();
  }

  async loadAndRenderPdfDocument() {
    const loadingOverlay = document.getElementById('skPdfLoadingOverlay');
    const pageCard = document.getElementById('skPdfPageCard');
    if (loadingOverlay) loadingOverlay.style.display = 'flex';
    if (pageCard) pageCard.style.display = 'none';

    try {
      await this.ensurePdfJs();
      if (window.pdfjsLib) {
        window.pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
      }

      // Fetch rendered PDF from server
      const response = await fetch('/api/rental/generate-pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.currentFormData || {})
      });

      if (!response.ok) {
        throw new Error(`Failed to generate PDF (HTTP ${response.status})`);
      }

      const pdfArrayBuffer = await response.arrayBuffer();
      const loadingTask = window.pdfjsLib.getDocument({ data: pdfArrayBuffer });
      this.pdfDoc = await loadingTask.promise;
      this.totalPages = this.pdfDoc.numPages;

      // Ensure all invitees have a placement on the execution (last) page
      const executionPage = this.totalPages;
      const owners = this.currentInvitees.filter(i => i.role === 'OWNER');
      const tenants = this.currentInvitees.filter(i => i.role !== 'OWNER');

      this.currentInvitees.forEach((inv) => {
        if (!inv.appearances || inv.appearances.length === 0) {
          inv.appearances = [];
        }

        // Normalize any 'L' page token
        inv.appearances.forEach(app => {
          if (app.page === 'L' || app.page === 'last') {
            app.page = executionPage;
          }
        });

        // Ensure at least one appearance on executionPage if none exists
        if (!inv.appearances.some(a => parseInt(a.page, 10) === executionPage)) {
          const isOwner = inv.role === 'OWNER';
          const roleList = isOwner ? owners : tenants;
          const roleIdx = roleList.indexOf(inv);
          const x1 = isOwner ? 45 : 345;
          const y1 = 620 + (Math.max(0, roleIdx) * 65);
          inv.appearances.push({
            page: executionPage,
            x1: x1,
            y1: y1,
            x2: x1 + 200,
            y2: y1 + 55
          });
        }
      });

      // Default active page is the execution (last) page where all signatures are positioned
      this.currentPageNum = executionPage;
      this.renderSignersBar();
      await this.renderCurrentPage();

      if (loadingOverlay) loadingOverlay.style.display = 'none';
      if (pageCard) pageCard.style.display = 'block';
    } catch (err) {
      console.error('[SafeKeys eSign] PDF Render Error:', err);
      if (loadingOverlay) {
        loadingOverlay.innerHTML = `
          <div style="color:#EF4444; font-size:14px; font-weight:700; margin-bottom:8px;">⚠️ Unable to preview PDF pages</div>
          <p style="font-size:12px; color:#94A3B8; max-width:400px; text-align:center;">${err.message || 'Error loading PDF preview. Default coordinate placement will still be applied.'}</p>
          <button type="button" class="sk-btn sk-btn-secondary sk-btn-xs" onclick="safeKeysEsign.closePlacementCanvas()">
            ← Return to Settings
          </button>
        `;
      }
    }
  }

  renderSignersBar() {
    const barEl = document.getElementById('skPdfSignersBar');
    if (!barEl) return;

    barEl.innerHTML = '<span class="sk-pdf-signers-bar-label">All Signers:</span>';

    this.currentInvitees.forEach((inv, idx) => {
      const isOwner = inv.role === 'OWNER';
      const badge = document.createElement('div');
      badge.className = `sk-signer-pill-badge ${isOwner ? 'role-owner' : 'role-tenant'}`;
      badge.title = `Click to add or duplicate signature box for ${inv.name} on Page ${this.currentPageNum}`;
      badge.innerHTML = `
        <span style="font-weight: 800; background: rgba(0,0,0,0.25); border-radius: 4px; padding: 1px 5px;">${idx + 1}</span>
        <span>${isOwner ? '🏠' : '👤'} ${inv.name}</span>
        <span class="sk-pill-add-icon" title="Add another box on this page">+</span>
      `;
      badge.onclick = () => this.addSignerToCurrentPage(idx);
      barEl.appendChild(badge);
    });
  }

  async renderCurrentPage() {
    if (!this.pdfDoc || this.isRendering) return;
    this.isRendering = true;

    try {
      const pageIndicator = document.getElementById('skPdfPageIndicator');
      const prevBtn = document.getElementById('skPdfPrevBtn');
      const nextBtn = document.getElementById('skPdfNextBtn');

      if (pageIndicator) pageIndicator.innerText = `Page ${this.currentPageNum} of ${this.totalPages}`;
      if (prevBtn) prevBtn.disabled = this.currentPageNum <= 1;
      if (nextBtn) nextBtn.disabled = this.currentPageNum >= this.totalPages;

      const page = await this.pdfDoc.getPage(this.currentPageNum);
      const viewportContainer = document.getElementById('skPdfViewportContainer');
      const containerWidth = (viewportContainer ? viewportContainer.clientWidth : 750) - 64;

      // Standard A4 point size
      const unscaledViewport = page.getViewport({ scale: 1.0 });
      this.pdfPageWidthPt = unscaledViewport.width || 595;
      this.pdfPageHeightPt = unscaledViewport.height || 842;

      // Compute display scale
      if (this.pdfScale === 'fit' || !this.pdfScale) {
        this.pdfScale = Math.min(1.3, Math.max(0.7, containerWidth / this.pdfPageWidthPt));
      }

      const viewport = page.getViewport({ scale: this.pdfScale });
      const canvas = document.getElementById('skPdfCanvas');
      const sigLayer = document.getElementById('skPdfSigLayer');
      const pageCard = document.getElementById('skPdfPageCard');

      if (canvas && pageCard && sigLayer) {
        canvas.width = viewport.width;
        canvas.height = viewport.height;
        pageCard.style.width = `${viewport.width}px`;
        pageCard.style.height = `${viewport.height}px`;

        const ctx = canvas.getContext('2d');
        const renderContext = {
          canvasContext: ctx,
          viewport: viewport
        };

        await page.render(renderContext).promise;

        // Render all signature overlay boxes for this page
        this.renderSignaturesOnOverlay(viewport.width, viewport.height);
      }
    } finally {
      this.isRendering = false;
    }
  }

  renderSignaturesOnOverlay(canvasWidth, canvasHeight) {
    const sigLayer = document.getElementById('skPdfSigLayer');
    if (!sigLayer) return;
    sigLayer.innerHTML = '';

    const scaleX = canvasWidth / this.pdfPageWidthPt;
    const scaleY = canvasHeight / this.pdfPageHeightPt;

    this.currentInvitees.forEach((inv, signerIdx) => {
      if (!inv.appearances) return;

      inv.appearances.forEach((app, appIdx) => {
        const appPage = parseInt(app.page, 10) || (app.page === 'L' ? this.totalPages : 1);
        if (appPage !== this.currentPageNum) return;

        const isOwner = inv.role === 'OWNER';
        const boxEl = document.createElement('div');
        boxEl.className = `sk-pdf-signature-box ${isOwner ? 'role-owner' : 'role-tenant'}`;
        boxEl.id = `skSigBox_${signerIdx}_${appIdx}`;

        // Convert point coordinates to canvas pixel coordinates
        const x1Pt = app.x1 !== undefined ? app.x1 : (isOwner ? 45 : 345);
        const y1Pt = app.y1 !== undefined ? app.y1 : (620 + signerIdx * 65);
        const x2Pt = app.x2 !== undefined ? app.x2 : (x1Pt + 200);
        const y2Pt = app.y2 !== undefined ? app.y2 : (y1Pt + 55);

        const leftPx = Math.round(x1Pt * scaleX);
        const topPx = Math.round(y1Pt * scaleY);
        const widthPx = Math.max(150, Math.round((x2Pt - x1Pt) * scaleX));
        const heightPx = Math.max(50, Math.round((y2Pt - y1Pt) * scaleY));

        boxEl.style.left = `${leftPx}px`;
        boxEl.style.top = `${topPx}px`;
        boxEl.style.width = `${widthPx}px`;
        boxEl.style.height = `${heightPx}px`;

        // Numbering badge (1, 2, 3) matching the reference video
        boxEl.innerHTML = `
          <div class="sk-sigbox-header">
            <div style="display:flex; align-items:center; gap:4px;">
              <span style="font-weight:900; font-size:10px; background:${isOwner ? '#059669' : '#2563EB'}; color:#FFFFFF; border-radius:4px; padding:1px 5px;">${signerIdx + 1}</span>
              <span class="sk-sigbox-role-badge">${isOwner ? 'Lessor' : 'Lessee'}</span>
            </div>
            <div style="display:flex; align-items:center; gap:4px;">
              <button type="button" class="sk-sigbox-delete-btn" title="Remove placement from this page" onclick="event.stopPropagation(); safeKeysEsign.removeAppearance(${signerIdx}, ${appIdx})">✕</button>
            </div>
          </div>
          <div class="sk-sigbox-name" title="${inv.name}">✍️ ${inv.name}</div>
          <div class="sk-sigbox-footer">
            <span class="sk-sigbox-coords-text" id="skCoordsText_${signerIdx}_${appIdx}">(${x1Pt}, ${y1Pt}) pt</span>
            <span class="sk-sigbox-drag-handle">📍 Drag anywhere</span>
          </div>
        `;

        sigLayer.appendChild(boxEl);
        this.makeDraggable(boxEl, signerIdx, appIdx, canvasWidth, canvasHeight, scaleX, scaleY);
      });
    });
  }

  makeDraggable(boxEl, signerIdx, appIdx, canvasWidth, canvasHeight, scaleX, scaleY) {
    let isDragging = false;
    let startX = 0;
    let startY = 0;
    let initialLeft = 0;
    let initialTop = 0;

    const onStart = (clientX, clientY) => {
      isDragging = true;
      boxEl.classList.add('is-dragging');
      startX = clientX;
      startY = clientY;
      initialLeft = parseInt(boxEl.style.left, 10) || 0;
      initialTop = parseInt(boxEl.style.top, 10) || 0;
    };

    const onMove = (clientX, clientY) => {
      if (!isDragging) return;
      const dx = clientX - startX;
      const dy = clientY - startY;

      const boxWidth = boxEl.offsetWidth;
      const boxHeight = boxEl.offsetHeight;

      let newLeft = Math.max(0, Math.min(canvasWidth - boxWidth, initialLeft + dx));
      let newTop = Math.max(0, Math.min(canvasHeight - boxHeight, initialTop + dy));

      boxEl.style.left = `${newLeft}px`;
      boxEl.style.top = `${newTop}px`;

      // Live calculate PDF points
      const x1Pt = Math.round(newLeft / scaleX);
      const y1Pt = Math.round(newTop / scaleY);
      const x2Pt = Math.round((newLeft + boxWidth) / scaleX);
      const y2Pt = Math.round((newTop + boxHeight) / scaleY);

      const coordsEl = document.getElementById(`skCoordsText_${signerIdx}_${appIdx}`);
      if (coordsEl) coordsEl.innerText = `(${x1Pt}, ${y1Pt}) pt`;
    };

    const onEnd = () => {
      if (!isDragging) return;
      isDragging = false;
      boxEl.classList.remove('is-dragging');

      const currentLeft = parseInt(boxEl.style.left, 10) || 0;
      const currentTop = parseInt(boxEl.style.top, 10) || 0;
      const boxWidth = boxEl.offsetWidth;
      const boxHeight = boxEl.offsetHeight;

      const x1Pt = Math.round(currentLeft / scaleX);
      const y1Pt = Math.round(currentTop / scaleY);
      const x2Pt = Math.round((currentLeft + boxWidth) / scaleX);
      const y2Pt = Math.round((currentTop + boxHeight) / scaleY);

      // Save updated coordinate to invitee appearance data
      if (this.currentInvitees[signerIdx] && this.currentInvitees[signerIdx].appearances[appIdx]) {
        this.currentInvitees[signerIdx].appearances[appIdx] = {
          page: this.currentPageNum,
          x1: x1Pt,
          y1: y1Pt,
          x2: x2Pt,
          y2: y2Pt
        };
      }
    };

    // Mouse handlers
    boxEl.addEventListener('mousedown', (e) => {
      if (e.target.tagName === 'BUTTON') return;
      onStart(e.clientX, e.clientY);

      const mouseMoveHandler = (ev) => onMove(ev.clientX, ev.clientY);
      const mouseUpHandler = () => {
        onEnd();
        window.removeEventListener('mousemove', mouseMoveHandler);
        window.removeEventListener('mouseup', mouseUpHandler);
      };
      window.addEventListener('mousemove', mouseMoveHandler);
      window.addEventListener('mouseup', mouseUpHandler);
    });

    // Touch handlers for mobile / touch devices
    boxEl.addEventListener('touchstart', (e) => {
      if (e.target.tagName === 'BUTTON') return;
      const touch = e.touches[0];
      onStart(touch.clientX, touch.clientY);

      const touchMoveHandler = (ev) => {
        const t = ev.touches[0];
        onMove(t.clientX, t.clientY);
      };
      const touchEndHandler = () => {
        onEnd();
        window.removeEventListener('touchmove', touchMoveHandler);
        window.removeEventListener('touchend', touchEndHandler);
      };
      window.addEventListener('touchmove', touchMoveHandler);
      window.addEventListener('touchend', touchEndHandler);
    }, { passive: true });
  }

  addSignerToCurrentPage(signerIdx) {
    const inv = this.currentInvitees[signerIdx];
    if (!inv) return;

    if (!inv.appearances) inv.appearances = [];

    const isOwner = inv.role === 'OWNER';
    const samePageCount = inv.appearances.filter(a => parseInt(a.page, 10) === this.currentPageNum).length;
    const x1 = isOwner ? 45 : 345;
    const y1 = 620 + (samePageCount * 65);

    inv.appearances.push({
      page: this.currentPageNum,
      x1: x1,
      y1: y1,
      x2: x1 + 200,
      y2: y1 + 55
    });

    this.renderCurrentPage();
  }

  removeAppearance(signerIdx, appIdx) {
    const inv = this.currentInvitees[signerIdx];
    if (!inv || !inv.appearances) return;

    inv.appearances.splice(appIdx, 1);

    // If no appearances remain for this signer, restore default on last page
    if (inv.appearances.length === 0) {
      const isOwner = inv.role === 'OWNER';
      inv.appearances = [{
        page: this.totalPages,
        x1: isOwner ? 45 : 345,
        y1: 120,
        x2: isOwner ? 245 : 545,
        y2: 175
      }];
    }

    this.renderCurrentPage();
  }

  snapPlacement(preset) {
    const pageNum = this.currentPageNum;
    const owners = this.currentInvitees.filter(i => i.role === 'OWNER');
    const tenants = this.currentInvitees.filter(i => i.role !== 'OWNER');

    if (preset === 'dual_bottom') {
      owners.forEach((inv, oIdx) => {
        inv.appearances = [{
          page: pageNum,
          x1: 45,
          y1: 660 + (oIdx * 60),
          x2: 245,
          y2: 715 + (oIdx * 60)
        }];
      });
      tenants.forEach((inv, tIdx) => {
        inv.appearances = [{
          page: pageNum,
          x1: 345,
          y1: 660 + (tIdx * 60),
          x2: 545,
          y2: 715 + (tIdx * 60)
        }];
      });
    } else if (preset === 'bottom_left') {
      this.currentInvitees.forEach((inv, idx) => {
        inv.appearances = [{
          page: pageNum,
          x1: 45,
          y1: 580 + (idx * 60),
          x2: 245,
          y2: 635 + (idx * 60)
        }];
      });
    } else if (preset === 'bottom_right') {
      this.currentInvitees.forEach((inv, idx) => {
        inv.appearances = [{
          page: pageNum,
          x1: 345,
          y1: 580 + (idx * 60),
          x2: 545,
          y2: 635 + (idx * 60)
        }];
      });
    } else if (preset === 'margin_initial') {
      this.currentInvitees.forEach((inv, idx) => {
        inv.appearances = [{
          page: pageNum,
          x1: 445,
          y1: 40 + (idx * 55),
          x2: 565,
          y2: 85 + (idx * 55)
        }];
      });
    }

    this.renderCurrentPage();
  }

  changePage(delta) {
    const targetPage = this.currentPageNum + delta;
    if (targetPage >= 1 && targetPage <= this.totalPages) {
      this.currentPageNum = targetPage;
      this.renderSignersBar();
      this.renderCurrentPage();
    }
  }

  zoom(factor) {
    if (factor === 'fit') {
      this.pdfScale = 'fit';
    } else {
      const current = typeof this.pdfScale === 'number' ? this.pdfScale : 1.0;
      this.pdfScale = Math.max(0.5, Math.min(2.0, current + factor));
    }
    this.renderCurrentPage();
  }

  resetDefaultPlacement() {
    const roleCounts = {};
    this.currentInvitees.forEach(inv => {
      const role = inv.role || 'OWNER';
      const slotIdx = roleCounts[role] || 0;
      roleCounts[role] = slotIdx + 1;
      const isOwner = role === 'OWNER';
      const x1 = isOwner ? 45 : 345;
      const y1 = 620 + (slotIdx * 65);
      inv.appearances = [{
        page: this.totalPages || 'L',
        x1: x1,
        y1: y1,
        x2: x1 + 200,
        y2: y1 + 55
      }];
    });
    this.renderCurrentPage();
    this.updatePlacementSummary();
  }

  resetToConfig() {
    document.getElementById('skEsignError').style.display = 'none';
    document.getElementById('skEsignLoading').style.display = 'none';
    document.getElementById('skEsignContent').style.display = 'none';
    document.getElementById('skPlacementDrawerView').style.display = 'none';
    document.getElementById('skEsignConfigStep').style.display = 'flex';
    document.getElementById('skEsignDispatchBtn').style.display = 'inline-flex';
    document.getElementById('skRefreshStatusBtn').style.display = 'none';
    const modalFooter = document.getElementById('skEsignModalFooter');
    if (modalFooter) modalFooter.style.display = 'flex';
    const modalContainer = document.getElementById('skEsignModalContainer');
    if (modalContainer) modalContainer.classList.remove('is-expanded');
  }

  /* ─────────────────────────────────────────────────────────────────────────
     eSign Request Dispatch & Tracking
     ───────────────────────────────────────────────────────────────────────── */

  async submitEsignDispatch() {
    const configStepEl = document.getElementById('skEsignConfigStep');
    const loadingEl = document.getElementById('skEsignLoading');
    const errorEl = document.getElementById('skEsignError');
    const dispatchBtn = document.getElementById('skEsignDispatchBtn');

    configStepEl.style.display = 'none';
    dispatchBtn.style.display = 'none';
    errorEl.style.display = 'none';
    loadingEl.style.display = 'flex';

    document.getElementById('skModalTitle').innerText = 'Digital Signature Execution';
    document.getElementById('skModalSubtitle').innerText = 'Generating document & dispatching invitations...';

    // Global flags
    const smartLiveliness = document.getElementById('skGlobalLiveliness') ? document.getElementById('skGlobalLiveliness').checked : true;
    const enableFaceAuth = document.getElementById('skGlobalFaceAuth') ? document.getElementById('skGlobalFaceAuth').checked : true;
    const enableGps = document.getElementById('skGlobalGps') ? document.getElementById('skGlobalGps').checked : true;

    // Custom invitees payload with individual signature types, appearances and capturePhoto settings
    const formattedInvitees = this.currentInvitees.map(inv => {
      const signType = inv.signType || 'AADHAAR';
      let signatures = [{ "type": "AADHAAR" }];
      if (signType === 'VIRTUAL_SIGN') {
        signatures = [{ "type": "VIRTUAL_SIGN" }];
      } else if (signType === 'ALLOW_EITHER') {
        signatures = [{ "type": "AADHAAR" }, { "type": "VIRTUAL_SIGN" }];
      }

      const invObj = {
        name: inv.name,
        email: inv.email || null,
        phone: inv.phone || null,
        role: inv.role,
        signType: signType,
        signatures: signatures,
        appearances: inv.appearances || [],
        capturePhoto: inv.capturePhoto === true
      };
      if (inv.capturePhoto && smartLiveliness) {
        invObj.userLiveliness = true;
        invObj.smartUserLivelinessConfig = {
          enableSmartUserLiveliness: true,
          smartUserLivelinessRetryAttempts: 3
        };
      }
      return invObj;
    });

    const payload = {
      ...(this.currentFormData || {}),
      custom_invitees: formattedInvitees,
      enable_auto_placement: this.autoPlacement,
      smart_liveliness: smartLiveliness,
      enable_face_auth: enableFaceAuth,
      enable_gps: enableGps
    };

    try {
      const response = await fetch('/api/rental/request-esign', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      const result = await response.json();
      loadingEl.style.display = 'none';

      if (!response.ok || !result.success) {
        throw new Error(result.error || 'Failed to dispatch eSign invitations.');
      }

      this.currentDocumentId = result.document_id;
      this.renderEsignResult(result);
      document.getElementById('skRefreshStatusBtn').style.display = 'inline-flex';
      document.getElementById('skModalSubtitle').innerText = 'Signers can now execute using their direct links below.';

      // Start light polling for status every 15s
      this.startStatusPolling();
    } catch (err) {
      loadingEl.style.display = 'none';
      errorEl.style.display = 'block';
      document.getElementById('skEsignErrorMessage').innerText = err.message || 'Error occurred during eSign dispatch.';
    }
  }

  renderEsignResult(result) {
    const contentEl = document.getElementById('skEsignContent');
    const docIdEl = document.getElementById('skDocIdCode');
    const inviteesListEl = document.getElementById('skInviteesList');

    docIdEl.innerText = result.document_id || 'N/A';
    inviteesListEl.innerHTML = '';

    const invitees = result.invitees || [];
    if (invitees.length === 0) {
      inviteesListEl.innerHTML = '<div class="sk-empty-invitees">No invitees found.</div>';
    } else {
      invitees.forEach((inv, idx) => {
        const isSigned = inv.signed === true;
        const signUrl = inv.signUrl;
        const roleLabel = idx === 0 ? 'Primary Lessor (Owner)' : (idx === 1 ? 'Primary Lessee (Tenant)' : `Signer ${idx + 1}`);

        // Determine signature badge & button label based on configured signType
        const configuredInv = this.currentInvitees[idx];
        const signType = (configuredInv ? configuredInv.signType : (inv.signType || 'AADHAAR')).toUpperCase();
        let signBtnText = '✍️ Sign Now (Aadhaar / OTP)';
        let signTypeBadge = '<span class="sk-signtype-badge badge-aadhaar">🪪 Aadhaar eSign</span>';
        if (signType === 'VIRTUAL_SIGN' || signType === 'VIRTUAL') {
          signBtnText = '✍️ Sign Now (Virtual Sign)';
          signTypeBadge = '<span class="sk-signtype-badge badge-virtual">✍️ Virtual Sign</span>';
        } else if (signType === 'ALLOW_EITHER' || signType === 'EITHER') {
          signBtnText = '✍️ Sign Now (Aadhaar / Virtual)';
          signTypeBadge = '<span class="sk-signtype-badge badge-either">⚡ Aadhaar / Virtual</span>';
        }

        const card = document.createElement('div');
        card.className = `sk-invitee-card ${isSigned ? 'is-signed' : ''}`;
        card.innerHTML = `
          <div class="sk-invitee-main">
            <div class="sk-invitee-meta">
              <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 2px;">
                <span class="sk-invitee-role">${roleLabel}</span>
                ${signTypeBadge}
              </div>
              <h4 class="sk-invitee-name">${inv.name || 'Signer'}</h4>
              <div class="sk-invitee-contact">
                ${inv.phone ? `<span>📱 +91 ${inv.phone}</span>` : ''}
                ${inv.email ? `<span>✉️ ${inv.email}</span>` : ''}
              </div>
            </div>
            <div class="sk-invitee-status">
              ${isSigned 
                ? '<span class="sk-status-pill pill-completed">✓ Signed</span>' 
                : (inv.active ? '<span class="sk-status-pill pill-active">⚡ Active Signer</span>' : '<span class="sk-status-pill pill-pending">In Queue</span>')}
            </div>
          </div>
          <div class="sk-invitee-actions">
            ${signUrl && !isSigned ? `
              <a href="${signUrl}" target="_blank" class="sk-btn sk-btn-primary sk-btn-sm">
                ${signBtnText}
              </a>
              <button type="button" class="sk-btn sk-btn-secondary sk-btn-sm" onclick="safeKeysEsign.copySignLink('${signUrl}', this)">
                📋 Copy Link
              </button>
            ` : ''}
            ${isSigned ? '<span class="sk-signed-check">Digitally signed &amp; verified</span>' : ''}
          </div>
        `;
        inviteesListEl.appendChild(card);
      });
    }

    contentEl.style.display = 'block';
  }

  async refreshStatus() {
    if (!this.currentDocumentId) return;

    const refreshBtn = document.getElementById('skRefreshStatusBtn');
    if (refreshBtn) refreshBtn.innerText = 'Checking...';

    try {
      const response = await fetch(`/api/rental/esign-status/${this.currentDocumentId}?file=true`);
      const result = await response.json();
      if (refreshBtn) refreshBtn.innerText = '🔄 Refresh Status';

      if (response.ok && result.success) {
        this.updateStatusDisplay(result);
      }
    } catch (e) {
      if (refreshBtn) refreshBtn.innerText = '🔄 Refresh Status';
      console.warn('Status refresh error:', e);
    }
  }

  updateStatusDisplay(data) {
    const statusBadge = document.getElementById('skDocStatusBadge');
    const completedBanner = document.getElementById('skEsignCompletedBanner');
    const downloadBtn = document.getElementById('skDownloadSignedPdfBtn');

    const status = data.status || 'SENT';
    statusBadge.innerText = status;
    statusBadge.className = `sk-status-pill pill-${status.toLowerCase()}`;

    if (status === 'COMPLETED') {
      completedBanner.style.display = 'block';
      if (data.file_base64) {
        downloadBtn.href = `data:application/pdf;base64,${data.file_base64}`;
        downloadBtn.download = `Signed_${data.document_name || 'Rental_Agreement.pdf'}`;
        downloadBtn.style.display = 'inline-flex';
      }
      if (this.pollInterval) {
        clearInterval(this.pollInterval);
        this.pollInterval = null;
      }
    }

    // Re-render invitation items
    if (data.invitations) {
      this.renderEsignResult({
        document_id: data.document_id,
        invitees: data.invitations
      });
    }
  }

  startStatusPolling() {
    if (this.pollInterval) clearInterval(this.pollInterval);
    this.pollInterval = setInterval(() => {
      this.refreshStatus();
    }, 15000);
  }

  copySignLink(url, btnElement) {
    if (!url) return;
    navigator.clipboard.writeText(url).then(() => {
      const origText = btnElement.innerText;
      btnElement.innerText = '✓ Link Copied!';
      btnElement.classList.add('sk-btn-copied');
      setTimeout(() => {
        btnElement.innerText = origText;
        btnElement.classList.remove('sk-btn-copied');
      }, 2500);
    }).catch(err => {
      prompt('Copy this signing URL:', url);
    });
  }
}

// Global instance
window.safeKeysEsign = new SafeKeysEsignController();
