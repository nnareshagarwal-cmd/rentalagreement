/* rental_form_copilot.js - AI Copilot auto-expand panel and chat functionality */

/**
 * Open the copilot panel with slide-in animation.
 */
function openCopilotPanel() {
  const panel = document.getElementById('rentalCopilotDrawer');
  const overlay = document.getElementById('copilotOverlay');
  if (!panel) return;
  panel.classList.add('active');
  if (overlay) overlay.classList.add('active');
  // Auto-focus the input
  setTimeout(() => {
    const input = document.getElementById('copilotInput');
    if (input) input.focus();
  }, 350);
}

/**
 * Close the copilot panel.
 */
function closeCopilotPanel() {
  const panel = document.getElementById('rentalCopilotDrawer');
  const overlay = document.getElementById('copilotOverlay');
  if (panel) panel.classList.remove('active');
  if (overlay) overlay.classList.remove('active');
}

/**
 * Toggle copilot panel open/close (used by the floating AI button).
 */
function toggleRentalCopilotDrawer() {
  const panel = document.getElementById('rentalCopilotDrawer');
  if (!panel) return;
  if (panel.classList.contains('active')) {
    closeCopilotPanel();
  } else {
    openCopilotPanel();
  }
}

/**
 * Format AI response text: escape HTML, render bold and newlines.
 */
function formatCopilotResponse(text) {
  if (!text) return '';
  return text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

/**
 * Send a query to the AI Copilot.
 * Auto-opens the panel if not already open.
 */
async function sendCopilotQuery(promptText) {
  const input = document.getElementById('copilotInput');
  const msgs = document.getElementById('copilotMessages');
  const q = (promptText || input?.value || '').trim();
  if (!q || !msgs) return;
  if (input) input.value = '';

  // Auto-open panel if not already visible
  openCopilotPanel();

  // Hide quick chips after first message to give more space
  const chips = document.getElementById('copilotChips');
  if (chips && msgs.children.length > 1) {
    chips.style.display = 'none';
  }

  // Append user message bubble
  const uMsg = document.createElement('div');
  uMsg.className = 'copilot-user-msg';
  uMsg.textContent = q;
  msgs.appendChild(uMsg);

  // Append loading indicator
  const loadMsg = document.createElement('div');
  loadMsg.className = 'copilot-loading-msg';
  loadMsg.innerHTML = '<span>⚡ AI Copilot analyzing agreement</span><span class="copilot-loading-dots"><span></span><span></span><span></span></span>';
  msgs.appendChild(loadMsg);
  msgs.scrollTop = msgs.scrollHeight;

  try {
    const previewEl = document.getElementById('previewContent') || document.getElementById('previewPane');
    const currentHtml = previewEl ? previewEl.innerHTML : '';
    const res = await fetch('/api/ai/review-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agreement_html: currentHtml, prompt: q, agreement_type: 'simple_rental' })
    });
    const resJson = await res.json();
    const payload = resJson.data || resJson;
    const responseText = payload.response || 'Action completed successfully.';
    const formatted = formatCopilotResponse(responseText);

    // Remove loading indicator
    if (loadMsg.parentNode) loadMsg.remove();

    // Create AI response bubble
    const aMsg = document.createElement('div');
    aMsg.className = 'copilot-ai-msg';

    if (payload.action === 'modify') {
      aMsg.classList.add('modify');

      // ── Sync field_updates back to the form ──
      const fieldUpdates = payload.field_updates || {};
      const updatedFields = [];

      for (const [fieldKey, newValue] of Object.entries(fieldUpdates)) {
        const el = document.getElementById(fieldKey);
        if (!el) continue;

        // Update the form field value
        if (el.tagName === 'SELECT') {
          // For selects, find the matching option (case-insensitive)
          const options = Array.from(el.options);
          const match = options.find(opt =>
            opt.value.toLowerCase() === newValue.toLowerCase() ||
            opt.text.toLowerCase() === newValue.toLowerCase()
          );
          if (match) {
            el.value = match.value;
          } else {
            el.value = newValue;
          }
        } else if (el.type === 'checkbox') {
          el.checked = newValue === 'Y' || newValue === 'true' || newValue === true;
        } else {
          el.value = newValue;
        }

        // Dispatch change event so calculations and other listeners fire
        el.dispatchEvent(new Event('change', { bubbles: true }));
        updatedFields.push(fieldKey);

        // Visual flash on the form field to show it was updated
        _flashFieldUpdate(el);
      }

      // Build sync status message
      let syncNote = '';
      if (updatedFields.length > 0) {
        syncNote = `<br><span style="color:#34d399; font-size:12px; margin-top:6px; display:inline-block;">` +
          `✅ Form synced: ${updatedFields.map(f => f.replace(/_/g, ' ')).join(', ')} — auto-saved</span>`;

        // Trigger localStorage save
        if (typeof debouncedLocalSave === 'function') debouncedLocalSave();
        if (typeof saveFormToLocal === 'function') saveFormToLocal();

        // Re-render preview from form data (ensures form → preview consistency)
        if (typeof triggerDebouncedPreview === 'function') {
          triggerDebouncedPreview();
        }
      }

      aMsg.innerHTML = `<strong>🤖 AI Copilot — Clause Updated</strong>${formatted}${syncNote}`;

      // If no field_updates, still update the preview HTML directly
      if (updatedFields.length === 0 && payload.updated_html && previewEl) {
        previewEl.innerHTML = payload.updated_html;
      }
    } else {
      aMsg.classList.add('answer');
      aMsg.innerHTML = `<strong>🤖 AI Copilot Review</strong>${formatted}`;
    }

    msgs.appendChild(aMsg);
  } catch (e) {
    // Remove loading indicator
    if (loadMsg.parentNode) loadMsg.remove();

    const errMsg = document.createElement('div');
    errMsg.className = 'copilot-ai-msg error';
    errMsg.innerHTML = '<strong>⚠️ Error</strong>Sorry, could not process the request right now. Please try again.';
    msgs.appendChild(errMsg);
  }
  msgs.scrollTop = msgs.scrollHeight;
}

/**
 * Flash a green border on a form field to indicate it was updated by AI.
 */
function _flashFieldUpdate(el) {
  const origBorder = el.style.border;
  const origBoxShadow = el.style.boxShadow;
  const origTransition = el.style.transition;

  el.style.transition = 'all 0.3s ease';
  el.style.border = '2px solid #34d399';
  el.style.boxShadow = '0 0 0 3px rgba(52, 211, 153, 0.25)';

  // Scroll the field into view if not visible
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });

  setTimeout(() => {
    el.style.border = origBorder;
    el.style.boxShadow = origBoxShadow;
    setTimeout(() => { el.style.transition = origTransition; }, 300);
  }, 2500);
}
