# AgreementAI — Agent Knowledge Transfer Guide

> **Purpose**: Read this file FIRST before making any changes to the rental form.
> It tells you exactly which file to open, why the codebase is structured this way,
> and how to avoid wasting tokens re-reading files.

---

## 1. Why This Structure Exists

On 2026-07-25, the monolithic `templates/rental_form.html` (4,142 lines / 193 KB)
was split into 5 modular files. The reasons:

- **Token waste**: Every small change required reading 4,000+ lines (~15,000 tokens)
- **Future scalability**: Google API integration is planned; modular files make
  adding features clean
- **Browser caching**: Separate CSS/JS files cache independently — users only
  re-download the file that changed, not the entire page

**Backup of the original monolith**: `backups_20260725/rental_form.html.bak`

---

## 2. File Map — Which File Does What

```
templates/
  rental_form.html              ← 168 lines — HTML structure ONLY (no CSS, no JS)

static/css/
  rental_form.css               ← 927 lines — ALL form styles

static/js/
  rental_form_utils.js          ←  86 lines — Pure utility functions
  rental_form_core.js           ← 2927 lines — Main form logic (rendering, events, data)
  rental_form_copilot.js        ←  43 lines — AI copilot drawer chat
  property_context_bar.js       ← ~200 lines — Property context bar widget

Backend:
  app.py                        ← 152 lines — Flask routes
  services/ai_service.py        ← 208 lines — AI/preview rendering service
  clauses/agreement_renderer.py ← 1329 lines — HTML clause generation with field mapping
```

**JS Load Order** (in rental_form.html):
```
property_context_bar.js → rental_form_utils.js → rental_form_core.js → rental_form_copilot.js
```

---

## 3. Decision Tree — Which File to Read First

```
What kind of change is needed?
│
├─ STYLING (colors, fonts, layout, spacing, responsive)
│   → READ: static/css/rental_form.css (927 lines)
│   → Token cost: ~3,000
│
├─ NUMBER FORMATTING (Indian commas, number-to-words, date calculation)
│   → READ: static/js/rental_form_utils.js (86 lines)
│   → Token cost: ~500
│   → Contains: formatIndianNumber(), numberToWords(), calculateEndDate()
│
├─ AI COPILOT (chat drawer, prompt badges, AI review)
│   → READ: static/js/rental_form_copilot.js (43 lines)
│   → Token cost: ~300
│
├─ HTML STRUCTURE (buttons, layout, modals, sections, new elements)
│   → READ: templates/rental_form.html (168 lines)
│   → Token cost: ~1,000
│
├─ FORM FIELD LOGIC (add/remove fields, auto-calculations, event listeners,
│   rendering, field labels, save/load, preview, validation, renewal, lock-in,
│   bachelor fields, sign type, template filtering, localStorage draft)
│   → READ: static/js/rental_form_core.js (2927 lines)
│   → Token cost: ~10,000
│   → TIP: Use line-range reads. Key sections:
│       Lines 1-30:    Shared state variables
│       Lines 31-100:  loadTemplates, loadSocieties, loadMapping, loadExecutives
│       Lines 100-180: Society search dropdown
│       Lines 180-250: selectSociety, loadRentalData
│       Lines 250-1800: renderForm() — THE BIG FUNCTION (creates all fields)
│       Lines 1800-2100: setupSignTypeFields, template filtering, renewal toggle
│       Lines 2100-2300: setupAutoCalculations (P13/P16/P17/P19 auto-calc)
│       Lines 2300-2500: messages, popups, clause editing
│       Lines 2500-2700: buildRentalSubmitData, save/generate/download buttons
│       Lines 2700-2850: updatePreview, preview toggle, event listeners
│       Lines 2850-2927: initialize()
│
├─ BACKEND ROUTES or API ENDPOINTS
│   → READ: app.py (152 lines)
│   → Token cost: ~800
│
├─ AGREEMENT TEXT / CLAUSE CONTENT / FIELD MAPPING
│   → READ: clauses/agreement_renderer.py (1329 lines)
│   → Token cost: ~5,000
│
├─ GOOGLE API INTEGRATION (future)
│   → CREATE: static/js/rental_form_google.js (new file)
│   → MODIFY: templates/rental_form.html (add <script> tag)
│
└─ DON'T KNOW / MULTIPLE AREAS
    → READ THIS FILE FIRST, then read the specific module
```

---

## 4. Key Field IDs and Their Behaviors

| Field ID | Label | Auto-Behavior |
|----------|-------|---------------|
| P1 | Today's Date | Read-only, auto-set to current date |
| P13 | Rent Amount | Indian comma formatting on input (e.g., 25,000) |
| P14 | Rent in Words | Auto-filled from P13, read-only |
| P16 | Agreement Start Date | Triggers P17 auto-calculation |
| P17 | Agreement End Date | Auto = P16 + 11 months - 1 day (user can override) |
| P19 | Security Deposit | Auto = P13 × 2, Indian commas (user can override) |
| P20 | Deposit in Words | Auto-filled from P19, read-only |
| P21 | Lock-in Months | Visible only when Renewal = Yes |
| P28 | Lock-in End Date | Auto = P16 + P21 months - 1 day, read-only |

---

## 5. Event Lifecycle (How the Form Initializes)

```
Page Load
  → initialize()                          [rental_form_core.js L2850+]
      → loadMapping(), loadTemplates(), loadExecutives(), loadSocieties()
      → Restore draft from localStorage
      → If URL has ?society=X → selectSociety(X)
          → loadRentalData(society)
              → renderForm(data)            [rental_form_core.js L250+]
                  → createSection()         — builds collapsible headers
                  → createField()           — builds input elements
                  → setupAutoCalculations() — binds P13↔P19, P16→P17
                  → setupRenewalToggle()    — lock-in field visibility
                  → setupSignTypeFields()   — digital/physical dropdowns
                  → setTimeout(updatePreview, 500)
      → updatePreview()                     — saves draft + fetches /api/rental/preview
```

---

## 6. Common Debugging Patterns

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Form fields not updating after code change | Browser cached old JS | Hard refresh (Ctrl+Shift+R) or increment `?v=` in HTML |
| Auto-calculations not working | `setupAutoCalculations()` didn't run — something above it in `renderForm()` crashed | Check browser console for errors in renderForm |
| Event listeners wiped on society change | `renderForm()` clears `#formFields` and recreates DOM | Listeners must be attached inside `renderForm()` |
| Preview not loading | `updatePreview()` calls `/api/rental/preview` — check backend | Check `app.py` route and `ai_service.py` |
| localStorage draft stale | Draft key = `rental_draft_simple` or `rental_draft_leave&license` | Clear with `localStorage.removeItem(key)` |

---

## 7. Token Budget Summary

| Change Scope | Files to Read | Estimated Tokens | vs Old (15,000) |
|-------------|--------------|-----------------|-----------------|
| CSS only | rental_form.css | ~3,000 | **80% saved** |
| Utility function | rental_form_utils.js | ~500 | **97% saved** |
| Copilot change | rental_form_copilot.js | ~300 | **98% saved** |
| HTML layout | rental_form.html | ~1,000 | **93% saved** |
| Form field logic | rental_form_core.js (targeted range) | ~3,000-5,000 | **67-80% saved** |
| Full form logic | rental_form_core.js (full) | ~10,000 | **33% saved** |
| Backend route | app.py | ~800 | **95% saved** |

---

## 8. Rules for Future Changes

1. **NEVER put inline `<style>` or `<script>` back into rental_form.html** — always use the separate files
2. **New features get new files** — e.g., `rental_form_google.js` for Google API
3. **Keep utility functions pure** — no DOM access in `rental_form_utils.js`
4. **Test after changes**: Start server with `python app.py`, open `http://127.0.0.1:7000/agreements/simple-rental`
5. **Workspace rule** at `.gemini/rules/rental_form_architecture.md` is auto-injected into every agent conversation — update it when you add new files or fields
