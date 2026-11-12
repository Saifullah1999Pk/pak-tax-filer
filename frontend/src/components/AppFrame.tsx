import type { ReactNode } from "react";
import { Link, Outlet } from "react-router";
import { useProfile } from "../profile/ProfileContext";
import { LogoutButton } from "./LogoutButton";
import { AccountMenu, ComputerLinks, PhoneNav } from "./MainNav";
import { Mark } from "./NavIcons";
import { useWideScreen } from "./useWideScreen";

// The frames around every page (feature 001, User Story 6, task T050; FR-027, amended with 006,
// task T035). Pages keep their own <main>; a frame adds the header, the navigation and the
// "Skip to content" target.

const CONTENT_ID = "content";

type FrameProps = {
  /** The full frame: the tax year and the navigation. */
  full: boolean;
  showLogout: boolean;
  /** The brand panel beside the page (login and sign-up). */
  brand?: boolean;
  children?: ReactNode;
};

/** What the app does, beside the login and sign-up forms (task T058, FR-032). */
function BrandPanel() {
  return (
    <aside className="brand-panel" aria-label="About PakTaxFiler">
      <p className="brand-title">Your salaried tax return, step by step.</p>
      <ol className="brand-steps" role="list">
        <li>Upload your salary and bank certificates</li>
        <li>Check every figure the app reads</li>
        <li>See your tax and your wealth statement</li>
      </ol>
      <p className="brand-note">
        AI reads your certificates, you confirm every figure, and the tax itself
        is worked out from FBR&apos;s published rates.
      </p>
    </aside>
  );
}

/**
 * One component for every frame, so a page whose frame changes (profile setup becoming
 * editing) keeps its place in the tree and isn't re-created.
 */
function Frame({ full, showLogout, brand = false, children }: FrameProps) {
  const { profile } = useProfile();
  // One layout at a time, so the page never holds two menus.
  const wide = useWideScreen();
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
            {/* The full frame puts Log out in the Account menu; first-time setup shows it. */}
            {!full && showLogout && (
              <div className="logout">
                <LogoutButton />
              </div>
            )}
            {full && wide && <AccountMenu />}
          </div>
          {full && (wide ? <ComputerLinks /> : <PhoneNav />)}
        </div>
      </header>
      {/* tabIndex -1: the skip link can move focus here, but Tab never stops on it. */}
      <div
        id={CONTENT_ID}
        className={full ? "app-body" : "plain-body"}
        tabIndex={-1}
      >
        {brand ? (
          <div className="auth-layout">
            <BrandPanel />
            {children ?? <Outlet />}
          </div>
        ) : (
          (children ?? <Outlet />)
        )}
      </div>
    </>
  );
}

/** Logged-in pages with a profile: header with the tax year, the navigation and Account. */
export function AppFrame({ children }: { children?: ReactNode }) {
  return (
    <Frame full showLogout>
      {children}
    </Frame>
  );
}

/** Not found: the app's name above one panel. */
export function PlainFrame({ children }: { children?: ReactNode }) {
  return (
    <Frame full={false} showLogout={false}>
      {children}
    </Frame>
  );
}

/** Login and sign-up: the simple frame with the brand panel beside the form. */
export function AuthFrame({ children }: { children?: ReactNode }) {
  return (
    <Frame full={false} showLogout={false} brand>
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
