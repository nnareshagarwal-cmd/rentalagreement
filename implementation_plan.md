# Safekeys Frontend Implementation Plan (V4 Architecture)

> **Role**: Lead Frontend Engineer  
> **Architecture Basis**: SAFEKEYS V4 Platform Architecture & SAFEKEYS Design System Governance  
> **Primary Directive**: Zero Backend Regression. Preserve Flask API contracts (`app.py`), database handlers, and legal clause generation logic (`clauses/`).

---

## 1. File Modification Matrix

### A. Existing Files to Modify (Frontend & Templates Only)
- **`templates/rental_form.html`**
  - Wrap existing form field groups into 6 discrete step containers (`#step-1-agreement`, `#step-2-property`, `#step-3-owners`, `#step-4-tenants`, `#step-5-financial`, `#step-6-review`).
  - Add Persona Bar, 6-Step Horizontal Progress Stepper, and Step 6 Pre-Flight Review Checklist Container.
- **`templates/_static_assets.html`**
  - Update CSS and JS include order to load design tokens (`safekeys-tokens.css`), workspace styles (`safekeys-workspace.css`), and modular JS engines (`safekeys_state.js`, `safekeys_wizard.js`, `safekeys_review.js`).
- **`templates/index.html`**
  - Replace generic landing template with modern Workspace Dashboard layout (Operational Counters, Universal Search Bar, Recent Drafts, Properties Table).
- **`static/css/safekeys-base.css`**
  - Import design system CSS custom properties and apply base font (`Plus Jakarta Sans`), reset margins, and Pearl background (`#F8FAFC`).
- **`static/css/safekeys-ui.css`**
  - Refactor button classes (`.sk-btn-primary`, `.sk-btn-secondary`), input fields, cards (`.sk-card`), and status badges matching design tokens.
- **`static/js/rental_form_core.js`**
  - Decouple monolithic rendering into modular step renders; preserve existing field listeners, auto-calculations, and preview update triggers.

---

### B. New Files to Create
- **`static/css/safekeys-tokens.css`**
  - Central CSS Custom Properties store for colors, font scales, spacing, border radiuses, and shadow elevations as specified in `SAFEKEYS_DESIGN_SYSTEM.md`.
- **`static/css/safekeys-workspace.css`**
  - Styles for Workspace Dashboard, Universal Search, Operational Stat Cards, and Properties Table.
- **`static/css/safekeys-wizard.css`**
  - Styles for 6-Step Horizontal Stepper, Active Step Cards, Step Transition Animations, and Pre-Flight Checklist.
- **`static/js/safekeys_state.js`**
  - Centralized client state store managing active persona (`Landlord`, `Tenant`, `Broker`, `Exec`), creation mode (`AI Guided` vs `Quick Form`), current active step (1-6), and draft auto-save metadata.
- **`static/js/safekeys_wizard.js`**
  - 6-Step Wizard Controller managing step navigation (`Next`, `Back`, `Jump to Step`), step-specific validation triggers, and stepper UI sync.
- **`static/js/safekeys_review.js`**
  - Pre-Flight Checklist Engine executing deterministic checks (Mandatory fields, ID format validation, Date sanity, Deposit warnings) for Step 6.
- **`static/js/safekeys_workspace.js`**
  - Workspace Dashboard Controller handling draft loading, universal search filtering across property/tenant/owner names, and instant renewal/clone triggers.
- **`static/js/safekeys_society_templates.js`**
  - Dynamic Society Template Engine managing retrieval, auto-filling, and crowd-sourced creation of society rules.

---

### C. Files That MUST NEVER Be Changed (Backend & Core Clause Engines)
- **`app.py`**: All Flask routes (`/`, `/generate_preview`, `/generate_pdf`, `/save_draft`, etc.) and request handlers.
- **`config.py`**: Flask environment configurations.
- **`database.py`**: SQLite database schemas and query execution.
- **`field_registry.py`**: Core field definitions and registry schemas.
- **`clauses/agreement_renderer.py`**: Clause generation & HTML template mapping logic.
- **`clauses/evaluator.py`**: Clause rule evaluation engine.
- **`clauses/formatters.py`**: Indian currency & date formatters (`formatIndianNumber`, `numberToWords`).
- **`clauses/html_renderer.py`**: PDF/HTML legal contract preview renderer.
- **`services/ai_service.py`**: Backend AI preview generation service.

---

## 2. Recommended Folder Structure

```
c:\My Drive\vscodeworkspace1_v1_agreement\
├── static/
│   ├── css/
│   │   ├── safekeys-tokens.css           [NEW] Design Tokens & Variables
│   │   ├── safekeys-base.css             [MODIFY] Base Reset & Foundations
│   │   ├── safekeys-ui.css               [MODIFY] Core Component Library
│   │   ├── safekeys-workspace.css        [NEW] Dashboard & Search Styles
│   │   └── safekeys-wizard.css           [NEW] 6-Step Wizard & Checklist Styles
│   ├── js/
│   │   ├── safekeys_state.js             [NEW] Client State & Persona Engine
│   │   ├── safekeys_wizard.js            [NEW] 6-Step Navigation & Stepper
│   │   ├── safekeys_review.js            [NEW] Pre-Flight Checklist Engine
│   │   ├── safekeys_workspace.js         [NEW] Dashboard & Universal Search
│   │   ├── safekeys_society_templates.js   [NEW] Dynamic Society Templates Manager
│   │   ├── rental_form_utils.js          [PRESERVE] Utility Functions
│   │   └── rental_form_core.js           [MODIFY] Form Logic & Field Event Listeners
├── templates/
│   ├── rental_form.html                  [MODIFY] Wizard Shell & 6 Steps Markup
│   ├── _static_assets.html               [MODIFY] Asset Load Order
│   └── index.html                        [MODIFY] Workspace Dashboard Shell
├── clauses/                              [NEVER TOUCH] Legal Clause Engines
├── app.py                                [NEVER TOUCH] Flask App & API Endpoints
├── config.py                             [NEVER TOUCH] Configuration
├── database.py                           [NEVER TOUCH] Database Access
├── field_registry.py                     [NEVER TOUCH] Field Definitions
├── SAFEKEYS_DESIGN_SYSTEM.md             [DOCUMENTATION] Design Tokens Baseline
└── implementation_plan.md                [PLAN] Updated V4 Frontend Implementation Plan
```

---

## 3. Phased Implementation Roadmap (Safest Order)

### Phase 1: Design Tokens & UI Shell Modernization (Sprint 1)
- Create `static/css/safekeys-tokens.css` with CSS variables.
- Update `static/css/safekeys-base.css` and `static/css/safekeys-ui.css`.
- Update `templates/_static_assets.html`.
- *Verification*: Verify page renders with new typography, colors, and buttons with 0 console errors and 0 backend route changes.

### Phase 2: 6-Step Wizard Engine & Pre-Flight Review (Sprint 2)
- Create `static/js/safekeys_state.js`, `static/js/safekeys_wizard.js`, and `static/js/safekeys_review.js`.
- Update `templates/rental_form.html` to group fields into 6 step containers with stepper.
- Implement Step 6 Pre-Flight Checklist.
- *Verification*: Test step navigation (`Next`/`Back`), step-specific error highlighting, and ensure form payload submitted to `/generate_preview` remains 100% identical.

### Phase 3: Workspace Dashboard & Universal Search (Sprint 3)
- Create `static/css/safekeys-workspace.css` and `static/js/safekeys_workspace.js`.
- Refactor `templates/index.html` to present operational stat cards (`Drafts`, `Generated Today`, `Renewals Due`) and universal search filter.
- *Verification*: Confirm recent drafts load correctly from browser storage / server.

### Phase 4: Renewal, Clone, & Dynamic Society Templates (Sprint 4)
- Create `static/js/safekeys_society_templates.js`.
- Wire `Instant Renewal` (pre-fills existing agreement, increments dates) and `Property Clone` (keeps property/landlord, resets tenant).
- Connect society template saving & dropdown auto-fill.
- *Verification*: Test instant renewal and cloning flows end-to-end.

### Phase 5: Advanced AI & Acceleration Layer (Sprint 5 - Deferred)
- OCR document parsing, conversational AI guided mode, and external document import.

---

## 4. Risk Assessment & Mitigation Matrix

| Risk | Severity | Impact | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **Breaking Input Field Names** | High | Form submit to `/generate_preview` or `/generate_pdf` fails | Keep all input `id` and `name` attributes 100% identical. Re-organize DOM containers only. |
| **Breaking JS Calculations** | Medium | Rent auto-calc or Indian word format breaks | Preserve existing event listeners in `rental_form_core.js` and `rental_form_utils.js`. |
| **State Loss on Refresh** | Medium | User loses selected persona or active step | Store `active_persona`, `preferred_mode`, and draft state in browser `localStorage`. |
| **CSS Leakage / Collision** | Low | Legacy styles corrupt modern cards | Namespace all new styles under `.sk-workspace`, `.sk-wizard`, `.sk-card`, `.sk-btn`. |
