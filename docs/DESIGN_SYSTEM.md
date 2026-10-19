# Nexora Design System Baseline

Updated 2026-10-16. This records the UI that exists today and the rules for extending it; it does not claim a complete design-system implementation.

## Current visual system

- **Typography:** DM Sans is the primary UI font and Manrope is used for prominent headings and brand text. Both currently load from Google Fonts; deployments should decide whether to self-host them to avoid a third-party runtime dependency.
- **Palette:** light theme with dark navy navigation/auth surfaces, blue primary actions, teal success accents, pale gray canvas, white cards, muted secondary text, and light gray borders. Current CSS values are in `frontend/src/WorkforceApp.css`; global defaults are in `frontend/src/index.css`.
- **Layout:** fixed desktop sidebar with a sticky top bar and centered page content; on small screens the sidebar becomes a horizontal scrolling navigation row. Existing layout breakpoints are 1100px, 760px, and 480px.
- **Components already present:** buttons, cards, metric tiles, tables, status badges, form fields, pagination, toast/inline notices, empty states, leave cards, profile/settings panels and auth forms. These are CSS classes in the existing application, not yet a separately versioned component package.
- **Motion:** hover/width transitions are used for feedback. A `prefers-reduced-motion` rule suppresses most animation and transition duration.
- **Theme:** only a light theme is implemented. There is no dark-theme token set or user preference control.

## Accessibility baseline and decisions

- Keep a visible keyboard focus indicator on every interactive control. The current CSS uses a 3px outline for buttons and common form controls; new components must retain or improve it.
- Use native buttons, links, labels, inputs and tables where possible. Every field must have a programmatic label; errors and asynchronous outcomes must be announced with an appropriate live/status region.
- Preserve keyboard operation, visible focus, logical heading order, sufficient text/control contrast, and non-color status cues. Charts and visual summaries must have a text equivalent.
- Honor `prefers-reduced-motion`; do not communicate state only through animation.
- Keep the existing responsive breakpoints as a starting point, but verify content reflow and keyboard/screen-reader use in browser tests before declaring a workflow accessible.
- Current automated accessibility coverage and browser-level keyboard/screen-reader checks are absent. Existing CSS support is a baseline, not WCAG conformance evidence.

## Extension rules

1. Define shared color, type, spacing, radius, shadow, and focus tokens before adding another feature-specific palette.
2. Build reusable form, data-table, loading, error, empty, confirmation, and access-denied patterns as those workflows are extracted from `WorkforceApp.tsx`.
3. Validate color contrast and touch target sizes as part of component review; do not rely on color alone for status.
4. Keep layout usable at 320px and at browser zoom; do not add horizontal page scrolling for core workflows.
5. Add component tests for accessible names, labels, errors and keyboard behavior, then add browser checks for critical end-to-end workflows.

## Source files

- `frontend/src/index.css` — global font, colors, reset and root sizing.
- `frontend/src/WorkforceApp.css` — application/auth CSS variables, components, focus styles, responsive breakpoints and reduced-motion rule.
- `frontend/src/features/auth/AuthScreen.tsx` — extracted sign-in, employee registration, first-admin setup and invited-registration workflows.
- `frontend/src/WorkforceApp.tsx` — current workforce application markup and module workflows.
