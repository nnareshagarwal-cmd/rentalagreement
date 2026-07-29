# Safekeys Design System & Governance Specification

> **Version**: 1.0.0  
> **Status**: Frozen Architecture Baseline  
> **Scope**: Token System, Component Contracts, & Design Governance for Safekeys Web Application

---

## 1. Design Tokens

### A. Color Palette
```css
:root {
  /* Brand Primary */
  --sk-color-primary-900: #0B0F17; /* Deep Slate Base */
  --sk-color-primary-800: #0F172A; /* Deep Surface */
  --sk-color-primary-700: #1E293B; /* Card Border / Subsurface */
  --sk-color-primary-600: #334155; /* Neutral Border */

  /* Accent & Action */
  --sk-color-emerald-500: #10B981; /* Safekeys Emerald (Success / Primary CTA) */
  --sk-color-emerald-600: #059669; /* Emerald Hover */
  --sk-color-indigo-500:  #6366F1; /* Accent / Focus Ring */
  --sk-color-indigo-600:  #4F46E5; /* Indigo Hover */

  /* Status Colors */
  --sk-color-success:     #10B981; /* Valid / Complete */
  --sk-color-warning:     #F59E0B; /* Caution / Review Needed */
  --sk-color-danger:      #EF4444; /* Error / Missing Field */
  --sk-color-info:        #3B82F6; /* Guidance / Tip */

  /* Surfaces & Backgrounds */
  --sk-color-bg-app:      #F8FAFC; /* Warm Pearl Background */
  --sk-color-bg-surface:  #FFFFFF; /* Pure White Card Surface */
  --sk-color-bg-muted:    #F1F5F9; /* Subtle Subsurface */

  /* Typography Colors */
  --sk-color-text-main:   #0F172A; /* High Contrast Heading/Body */
  --sk-color-text-muted:  #64748B; /* Secondary / Labels */
  --sk-color-text-subtle: #94A3B8; /* Disabled / Captions */
}
```

---

### B. Typography Hierarchy
```css
/* Fonts */
--sk-font-sans: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--sk-font-legal: 'Source Serif Pro', Georgia, Garamond, serif;

/* Type Scale */
--sk-text-display-xl: 36px / 1.2;  /* Hero / Main Metrics */
--sk-text-display-lg: 28px / 1.25; /* Page Titles */
--sk-text-heading:    20px / 1.3;  /* Section / Step Titles */
--sk-text-subheading: 16px / 1.4;  /* Card Titles / Field Groups */
--sk-text-body:       14px / 1.5;  /* Inputs / Standard Text */
--sk-text-caption:    12px / 1.4;  /* Tooltips / Small Badges */
```

---

### C. Spacing Scale
```css
--sk-space-1:  4px;  /* Micro gaps */
--sk-space-2:  8px;  /* Compact padding / icon gaps */
--sk-space-3: 12px;  /* Input padding / inner element spacing */
--sk-space-4: 16px;  /* Card inner padding / standard gap */
--sk-space-6: 24px;  /* Section gaps / grid column gap */
--sk-space-8: 32px;  /* Large container padding */
--sk-space-12: 48px; /* Page layout margin */
```

---

### D. Border Radii & Elevation (Shadows)
```css
/* Radius */
--sk-radius-sm:  8px;  /* Buttons, Badges, Inputs */
--sk-radius-md: 12px;  /* Small Cards, Modals */
--sk-radius-lg: 16px;  /* Standard Cards, Wizards */
--sk-radius-xl: 24px;  /* Floating Bottom Sheets / Drawers */

/* Elevation Shadows */
--sk-shadow-sm: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
--sk-shadow-md: 0 4px 12px -2px rgba(0, 0, 0, 0.08);
--sk-shadow-lg: 0 12px 24px -4px rgba(0, 0, 0, 0.12);
```

---

### E. Transitions & Animations
```css
--sk-transition-fast:   150ms cubic-bezier(0.4, 0, 0.2, 1); /* Hover, Focus */
--sk-transition-normal: 250ms cubic-bezier(0.4, 0, 0.2, 1); /* Step transitions */
--sk-transition-slow:   350ms cubic-bezier(0.4, 0, 0.2, 1); /* Modal / Drawer slide */
```

---

## 2. Reusable Component Inventory

All UI features in Sprints 1–5 MUST be constructed exclusively using these standard component specifications:

1. **`PrimaryButton`**: Pill/rounded emerald CTA with active press physics (`scale(0.98)`).
2. **`SecondaryButton`**: Subdued outline/ghost button for secondary actions.
3. **`InputField`**: Standardized text input with label, floating helper, and inline validation state.
4. **`SelectField`**: Custom select dropdown with keyboard navigation.
5. **`DatePicker`**: Accessible date selection with auto-tenure helpers.
6. **`Card`**: White surface container with `16px` radius and `1px` subtle border.
7. **`StatCard`**: Metric display card used in the workspace dashboard.
8. **`WizardHeader`**: Minimalist step header with progress indicators.
9. **`Stepper`**: 6-step horizontal/vertical progress tracker.
10. **`Toast`**: Non-blocking notification banner (`Draft Auto-saved`, `Link Copied`).
11. **`Sidebar / Topbar`**: Global navigation shell for the workspace.
12. **`ValidationPanel`**: Pre-flight review checklist item with status indicator.

---

## 3. Role-Based Access Control (RBAC) Matrix

| Role | Workspace Access Scope | Agreement Actions Permitted |
| :--- | :--- | :--- |
| **`Admin` / `Safekeys Exec`** | Global (All properties & agreements) | Create, Edit, Delete, Renew, Clone, Template Management |
| **`Broker`** | Assigned Portfolio Properties | Create, Edit Drafts, Send for Review, Renew |
| **`Landlord`** | Owned Properties & Agreements | View, Edit Draft, Approve, Sign |
| **`Tenant`** | Single Agreement Instance | View Agreement, Request Clause Changes, Sign |

---

## 4. Execution Sprints & Sprint Scope

```text
 ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
 │ SPRINT 1 │─►│ SPRINT 2 │─►│ SPRINT 3 │─►│ SPRINT 4 │─►│ SPRINT 5 │
 └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
  UI Shell &    6-Step        Workspace     Renewal,      AI, OCR &
  Design        Wizard &      Dashboard &   Clone,        Advanced
  System        Review        Search        Templates     Flows
```
