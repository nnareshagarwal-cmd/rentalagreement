/* rental_form_copilot.js - AI Copilot drawer and chat functionality */

function toggleRentalCopilotDrawer() {
  const drawer = document.getElementById('rentalCopilotDrawer');
  if (!drawer) return;
  drawer.style.display = drawer.style.display === 'flex' ? 'none' : 'flex';
}

async function sendCopilotQuery(promptText) {
  const input = document.getElementById('copilotInput');
  const msgs = document.getElementById('copilotMessages');
  const q = (promptText || input?.value || '').trim();
  if (!q || !msgs) return;
  if (input) input.value = '';

  const uMsg = document.createElement('div');
  uMsg.style.cssText = 'background:#4338ca; color:#ffffff; padding:10px 14px; border-radius:12px; align-self:flex-end; max-width:85%; font-size:13px;';
  uMsg.textContent = q;
  msgs.appendChild(uMsg);

  const aMsg = document.createElement('div');
  aMsg.style.cssText = 'background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.1); color:#cbd5e1; padding:10px 14px; border-radius:12px; align-self:flex-start; max-width:85%; font-size:13px;';
  aMsg.textContent = 'Thinking...';
  msgs.appendChild(aMsg);
  msgs.scrollTop = msgs.scrollHeight;

  try {
    const previewEl = document.getElementById('previewContent') || document.getElementById('previewPane');
    const currentHtml = previewEl ? previewEl.innerHTML : '';
    const res = await fetch('/api/ai/review-chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ agreement_html: currentHtml, prompt: q, agreement_type: 'simple_rental' })
    });
    const data = await res.json();
    aMsg.textContent = data.response || 'Action completed.';
    if (data.updated_html && previewEl) {
      previewEl.innerHTML = data.updated_html;
    }
  } catch (e) {
    aMsg.textContent = 'Sorry, could not process request right now.';
  }
}
