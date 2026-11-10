import type { ReactNode } from "react";
import { Link, NavLink, Outlet } from "react-router";
import { useProfile } from "../profile/ProfileContext";
import { LogoutButton } from "./LogoutButton";
import {
  DocumentsIcon,
  HomeIcon,
  Mark,
  ProfileIcon,
  TaxIcon,
  WealthIcon,
} from "./NavIcons";

// The frames around every page (feature 001, User Story 6, task T050; FR-027). Pages keep their
// own <main>; a frame adds the header, the navigation and the "Skip to content" target.

const CONTENT_ID = "content";

const NAV_ITEMS = [
  { to: "/", label: "Home", icon: <HomeIcon /> },
  { to: "/documents", label: "Documents", icon: <DocumentsIcon /> },
  { to: "/tax", label: "Tax", icon: <TaxIcon /> },
  {
    to: "/wealth",
    // On phones only "Wealth" shows; the full name is still the link's name.
    label: (
      <>
        Wealth <span className="nav-long">statement</span>
      </>
    ),
    icon: <WealthIcon />,
  },
  { to: "/profile", label: "Profile", icon: <ProfileIcon /> },
];

function MainNav() {
  return (
    <nav className="app-nav" aria-label="Main">
      <ul>
        {NAV_ITEMS.map((item) => (
          <li key={item.to}>
            {/* NavLink marks the current page with aria-current="page". */}
            <NavLink to={item.to} end={item.to === "/"}>
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}

type FrameProps = {
  /** The full frame: the tax year and the navigation. */
  full: boolean;
  showLogout: boolean;
  children?: ReactNode;
};

/**
 * One component for every frame, so a page whose frame changes (profile setup becoming
 * editing) keeps its place in the tree and isn't re-created.
 */
function Frame({ full, showLogout, children }: FrameProps) {
  const { profile } = useProfile();
  return (
    <>
      <a className="skip-link" href={`#${CONTENT_ID}`}>
        Skip to content
      </a>
      <header className="app-header">
        <div className="app-header-inner">
          <Link to="/" className="wordmark" translate="no">
            <Mark />
            PakTaxFiler
          </Link>
          <div className="header-end">
            {full && profile && (
              <p className="tax-year">
                <span className="tax-year-prefix">Tax year </span>
                {profile.tax_year}
              </p>
            )}
            {showLogout && (
              <div className="logout">
                <LogoutButton />
              </div>
            )}
          </div>
          {full && <MainNav />}
        </div>
      </header>
      {/* tabIndex -1: the skip link can move focus here, but Tab never stops on it. */}
      <div
        id={CONTENT_ID}
        className={full ? "app-body" : "plain-body"}
        tabIndex={-1}
      >
        {children ?? <Outlet />}
      </div>
    </>
  );
}

/** Logged-in pages with a profile: header with the tax year and Log out, and the navigation. */
export function AppFrame({ children }: { children?: ReactNode }) {
  return (
    <Frame full showLogout>
      {children}
    </Frame>
  );
}

/** Login, sign-up and not found: the app's name above one panel. */
export function PlainFrame({ children }: { children?: ReactNode }) {
  return (
    <Frame full={false} showLogout={false}>
      {children}
    </Frame>
  );
}

/** The profile page: the full frame when editing, the simple one (with Log out) during
 * first-time setup, when there's no tax year yet and every other page would send you back. */
export function ProfileFrame({ children }: { children?: ReactNode }) {
  const { profile, loading } = useProfile();
  // While loading, assume editing (most visits): the full frame, so it doesn't jump.
  return (
    <Frame full={loading || profile !== null} showLogout>
      {children}
    </Frame>
  );
}
