# Design: a clean, responsive app on phone and computer (feature 001, User Story 6)

**Date:** 2026-11-10 · **Status:** draft for approval

## Intent

The lead looked at the live app and said the frontend "looks messy". It is unstyled: browser
default fonts and spacing, no shared header or navigation, each page carrying its own "Home"
link, and long forms (the wealth statement) that are hard to use on a phone. The user wants "the
best looking + responsive + snappy website while being functional and easy to use", working
properly on both computer and phone.

The pages, their behaviour and the API stay as they are. This change gives every page one
consistent look and frame, makes each page work at phone width, and turns Home into a checklist
that shows the next step to take.

## Who it's for

Salaried taxpayers in Pakistan, many of whom will open it on a phone, working from their salary
and bank certificates toward a tax figure and a wealth statement that IRIS accepts. The job of
the interface is to make a stressful, unfamiliar task feel orderly: always clear where you are,
what's done, and what comes next.

## Goals, non-goals, anti-goals

- **Goals:**
  - one visual system (colour, type, spacing) applied to all nine pages: Login, Signup, Home,
    Profile, Documents, Review, Tax, Wealth, Not found;
  - a shared app frame with navigation that suits both computer and phone;
  - every page usable from 320 px wide up, with no sideways scrolling;
  - a Home page that shows progress and the next step;
  - fast: no UI library, little JavaScript added, one font file;
  - light and dark themes, following the device setting.
- **Non-goals:**
  - a step-by-step "interview" flow with Next and Back through the whole app (considered and set
    aside, below);
  - new pages, new backend endpoints or API changes;
  - a landing or marketing page, animations for their own sake, a logo or brand identity beyond
    a wordmark.
- **Anti-goals:**
  - losing accessibility: everything stays usable by keyboard and screen reader, and colour
    never carries meaning on its own;
  - breaking the tests' way of finding things (role, label, visible text);
  - hiding the "not yet practitioner-reviewed" label or making it easy to miss;
  - any money calculation in the frontend (constitution, Principle I).

## Inspiration (research, 2026-11-10)

| Source | Taken from it |
|---|---|
| [Wealthsimple Tax](https://loanscanada.ca/taxes/wealthsimple-tax-review/) | Calm and uncluttered, with lots of white space; the whole result visible at once |
| [Taxfix](https://taxfix.de/en/newsroom), TurboTax | Guide people one step at a time; always show what's next |
| [GOV.UK design system](https://design-system.service.gov.uk/patterns/question-pages) and [form structure](https://www.gov.uk/service-manual/design/form-structure) | Big, clear form fields; labels above inputs; a "where you are" indicator on long forms |
| [Fintech UX trends](https://www.theskinsfactory.com/uiux-design-blog/fintech-ui-ux-design), [mobile-first fintech](https://products-by-klivvr.pages.dev/products/klivvr-consumer-app/articles/mobile-first-fintech-ux) | Mobile first; information in layers; a dashboard that shows what's left to do, not decoration |

These are references for structure and tone only; nothing is copied from another product's
branding, text or exact layout.

## Approaches considered

| | Approach | Trade-off |
|---|---|---|
| A | Restyle only | Fixes "messy", but people still work out the order themselves |
| **B (chosen)** | Restyle, plus a shared frame and a Home checklist that guides to the next step | Most of the guidance for a fraction of the work; pages and tests keep their shape |
| C | Full step-by-step flow (one screen at a time, Next and Back) | Most guided, but restructures every page and rewrites most tests and specs; can be built on B later if needed |

The user picked B ("middle path sounds good").

## How it works (decided)

### 1. Visual system

Written as CSS custom properties in `frontend/src/styles.css`, so every page uses the same named
values instead of one-off numbers.

- **Colour** (light; dark mode swaps these):

  | Token | Light | Use |
  |---|---|---|
  | `--ink` | `#16202C` | Text |
  | `--muted` | `#5B6675` | Secondary text, form-line citations |
  | `--page` | `#F5F7F9` | Page background |
  | `--surface` | `#FFFFFF` | Panels, inputs |
  | `--line` | `#DCE1E7` | Borders, dividers |
  | `--accent` | `#0B6E5F` | Buttons, links, current step |
  | `--warn` | `#A15C07` | Low confidence, notices (existing meaning, kept) |
  | `--danger` | `#B42318` | Errors |

  Contrast is at least 4.5:1 for text against its background in both themes.
- **Type:** one family, **Public Sans**, self-hosted as a single variable font. It was designed
  for government forms, reads well at small sizes, and has tabular figures, so amounts line up
  in columns. A short scale: 14, 16 (body), 18, 22, 28, 36 px. Money in results uses tabular
  figures and is right-aligned in tables.
- **Spacing:** a 4 px scale (4, 8, 12, 16, 24, 32, 48), nothing in between. Corner radius
  4 px for inputs and buttons, 8 px for panels; shadows only where something floats (the phone
  tab bar).
- **One memorable element:** the Home checklist (section 3). Everything else stays quiet.

### 2. App frame (one layout component around every logged-in page)

- **Header:** the wordmark "PakTaxFiler" (links to Home), the tax year from the profile (e.g.
  "Tax year 2025-26"), and Log out.
- **Navigation:** one `<nav>` with five links: Home, Documents, Tax, Wealth statement,
  Profile. The current page is marked with `aria-current="page"` and a visible style.
  - **Computer (≥ 720 px):** links in the header.
  - **Phone (< 720 px):** the same nav, moved by CSS into a bar fixed to the bottom of the
    screen with a small icon above each label (inline SVG, labels always visible), tap targets
    at least 48 px.
  - Because it is one element restyled by CSS, there is never a duplicate set of links.
- **Content width:** 720 px for forms and results; up to 1100 px for the document review page,
  which keeps its side-by-side layout on wide screens and stacks on narrow ones.
- The per-page "Home" links are removed (the frame replaces them). "Back to documents" on the
  review page stays, since it's a real "go up one level" link.
- Login, Signup and Not found use a simpler frame: the wordmark above a centred panel, no nav.
- **Profile** gets the full frame when the user already has a profile (editing). During
  first-time setup (no profile yet) it gets the simple frame plus Log out: there is no tax year
  to show, and every nav link would only send the user back to setup (my call, builder check).
  Profile's own Log out button goes, since the header has one.
- A "Skip to content" link is the first focusable element.

### 3. Home: the filing checklist

Home keeps its "Logged in as <email>" line (feature 002's contract and FR-013 rely on it) and
becomes an ordered list of the four steps of filing, each with its state and one action. Only
documents for the **profile's tax year** count, the same documents the tax and wealth pages use
(my call, builder check: counting other years could say "Ready" when the Tax page would refuse).

| Step | State shown | Action | Comes from |
|---|---|---|---|
| 1. Profile | Done: "Tax year 2025-26, on the ATL" (or "not on the ATL") | Edit | The profile already loaded (Home requires one) |
| 2. Documents | The counts that apply, e.g. "1 confirmed, 1 to review, 1 failed", or "None yet" | "Review the next document" (straight to it) if any is ready to review; otherwise "Upload documents" | `GET /api/documents` (already exists), this year's only |
| 3. Tax | "Ready" once a salary certificate for the year is confirmed, else "Needs a confirmed salary certificate" | See your tax | The same list |
| 4. Wealth statement | Same rule as Tax | Open | The same list |

- **Documents is done** when at least one salary certificate for the year is confirmed and
  nothing is waiting to be reviewed (my call, builder check). Documents still being read count
  as neither; failed ones are shown in the counts but don't hold the step back, since a
  confirmed certificate already lets Tax run.
- The first step that isn't done is highlighted as "Next", with the main button. When Profile
  and Documents are both done, Tax is "Next".
- Tax and Wealth show "Ready", never "Done": knowing whether they're done would mean calling
  their endpoints, which also ask the AI for a summary, on every visit to Home. That costs
  free-tier quota and seconds for a status line.
- The numbering is real (the steps are a sequence), shown as a vertical path on phone and on
  computer.
- If the documents list fails to load, the steps still show, with "Couldn't load your
  documents" and a "Try again" button (the app's existing wording for retrying); nothing is guessed.

### 4. Pages

- **Forms (Login, Signup, Profile, Wealth):** labels above fields, inputs 48 px tall,
  `inputmode="numeric"` for amounts, errors under the field they belong to (existing wording
  and ARIA links kept), the main button full-width on phone.
- **Documents:** the list becomes rows showing type, tax year, status (as text, with a coloured
  dot as extra) and the action. The upload form is a clear panel at the top.
- **Review:** keeps document-beside-figures on wide screens; on phone the document is
  collapsible above the figures so the figures aren't pushed far down. Low-confidence fields
  keep their "Low confidence" text and amber edge.
- **Tax result:** the practitioner label at the top of the result, then **two headline
  figures side by side** (stacked on phone): the salary side ("Rs X payable" or "Rs X
  over-deducted") and the bank-profit side, exactly as the API words them. There is no combined
  total: feature 004 keeps the two sides separate until the lead answers whether one can be set
  off against the other, and the frontend never adds them (Principle I). The non-ATL "to be
  confirmed" line stays with the bank-profit side. Below: the detail rows, then the breakdown as
  a ledger: description on the left, amount right-aligned with tabular figures, source in muted
  text beneath. The AI summary, when shown, sits in its own clearly labelled panel.
- **Wealth result:** stays where it is, after the form and its Save button, because it's the
  outcome of saving (focus and the "Saved." message stay beside Save). Inside the result
  section the headline comes first: the label, then the message (reconciled, or the gap and its
  direction) set large, then "Where to look", the summary and the breakdown (my call, builder
  check).
- **Wealth form:** the four parts, "What I own", "What I owe", "Money in and out" and
  "Result", are separate sections with their existing headings, and a short section bar at the
  top (links to each heading) jumps between them. It stays pinned under the header on computers
  only; on phones and tablets it would take too much of the screen (review H2). Each asset or liability row stacks its fields
  vertically on phone and sits in one line on computer. It stays one page with one Save button,
  so saving behaves exactly as it does now.
- **Loading, empty, error states:** keep their current wording; styled consistently.

### 5. Speed

- No CSS framework or component library; plain CSS in the existing `styles.css` plus a few
  small components (layout, nav icons, checklist).
- One font file (variable, Latin subset, `font-display: swap`); everything else is the system's.
- Measured with Lighthouse on the production build: Performance ≥ 90 and Accessibility ≥ 95 on
  mobile settings for Login, Home and Wealth.

## Skills used

From the skill repos the user pointed to (read in full; they are applied from their text, not
installed, unless the user asks to install them):

- **Designing and building:** anthropics `frontend-design` (the token plan above; checked
  against generic AI-design defaults: no cream-and-terracotta, no purple, no identical card
  grids, no all-caps labels) and addyosmani `frontend-ui-engineering` (WCAG AA, mobile first,
  spacing scale, empty and error states). Plus the project's own `react-feature` and
  `superpowers:test-driven-development`.
- **Checking:** vercel `web-design-guidelines` (an audit of the changed files against the Web
  Interface Guidelines) and addyosmani `browser-testing-with-devtools` (looking at the real app
  in a browser at 320, 768, 1024 and 1440 px, in light and dark). Then the `frontend-reviewer`
  agent and the `code-review` skill.

## Constraints

- React + TypeScript + Vite as today; React Testing Library tests find elements by role, label
  or text, never by CSS class.
- Every page keeps its current behaviour and API calls; only Home gains one call it didn't make
  before (the documents list).
- The practitioner label stays on every tax and wealth result (Principle IV); money is only
  displayed (Principle I).
- No real data in screenshots or tests (Principle V).
- Spec home: feature 001 gains User Story 6 (as 001 got User Story 5 for deployment). Then
  Spec Kit: specify → clarify → plan → tasks → analyze. Branch `001-ui`, stacked on PR #33.

## Builder check (2026-11-10)

A reviewer read this design as the builder would. Its five questions were all settled from
earlier decisions or as my calls, marked "(my call, builder check)" above: the Tax page's two
headline figures (004's no-total rule), counting only this tax year's documents on Home, when
the Documents step is done, the Wealth result staying after the form, and Profile's frame during
setup plus keeping "Logged in as" on Home.

## Left to the builder

- Exact icon drawings, hover and focus styles within the tokens, and dark-mode values that meet
  the same contrast.
- How the layout component is split into files, and the CSS file organisation (one file or a
  few), as long as tests find things by role and text.
- Breakpoints other than the 720 px navigation switch.
