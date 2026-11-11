import type { ReactNode } from "react";

// Small line icons for the phone navigation bar (feature 001, User Story 6). Decorative only:
// every link has its visible text label, so the icons are hidden from screen readers.

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      className="nav-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const HomeIcon = () => (
  <Icon>
    <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1z" />
  </Icon>
);

export const DocumentsIcon = () => (
  <Icon>
    <path d="M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7z" />
    <path d="M14 3v4h4M9 12h6M9 16h6" />
  </Icon>
);

export const TaxIcon = () => (
  <Icon>
    <path d="M6 3h12v18l-3-2-3 2-3-2-3 2z" />
    <path d="M9 8h6M9 12h6M9 16h3" />
  </Icon>
);

export const WealthIcon = () => (
  <Icon>
    <path d="M12 4v16M5 20h14M7 8h10" />
    <path d="M7 8 4.5 14a2.5 2.5 0 0 0 5 0zM17 8l-2.5 6a2.5 2.5 0 0 0 5 0z" />
  </Icon>
);

export const AskIcon = () => (
  <Icon>
    <path d="M5 5h14a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H10l-4 3.5V16H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z" />
    <path d="M10 9.2a2 2 0 1 1 2.6 1.9c-.4.2-.6.5-.6.9v.4M12 14h.01" />
  </Icon>
);

export const FilingIcon = () => (
  <Icon>
    <path d="M3.5 7a1 1 0 0 1 1-1h4.6l2 2h8.4a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1z" />
  </Icon>
);

export const ProfileIcon = () => (
  <Icon>
    <circle cx="12" cy="8.5" r="3.5" />
    <path d="M5 20a7 7 0 0 1 14 0" />
  </Icon>
);

/** The app's mark beside its name: an eight-pointed star (the pattern's motif) in gold, with a
 * green tick inside, for a return that's in order. */
export const Mark = () => (
  <svg
    width="26"
    height="26"
    viewBox="0 0 24 24"
    fill="none"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <g style={{ stroke: "var(--gold)" }} strokeWidth="1.6">
      <path d="M5.5 5.5h13v13h-13z" />
      <path d="M12 2.8 21.2 12 12 21.2 2.8 12z" />
    </g>
    <path
      d="m8.6 12.2 2.3 2.3 4.6-4.9"
      style={{ stroke: "var(--accent)" }}
      strokeWidth="2.2"
    />
  </svg>
);

/** Larger decorative icons for the upload area and empty states (task T061). */
function BigIcon({ children }: { children: ReactNode }) {
  return (
    <svg
      className="big-icon"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const UploadIcon = () => (
  <BigIcon>
    <path d="M12 15V4M7.5 8.5 12 4l4.5 4.5" />
    <path d="M4 15v4a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-4" />
  </BigIcon>
);

export const EmptyDocumentsIcon = () => (
  <BigIcon>
    <path d="M14 3H7a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1V7z" />
    <path d="M14 3v4h4M12 11v6M9 14h6" />
  </BigIcon>
);
