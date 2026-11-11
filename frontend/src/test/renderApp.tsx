import { render } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router";
import { AppRoutes } from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { ProfileProvider } from "../profile/ProfileContext";

/** The current address as text, for tests that must tell two pages' URLs apart. */
// A test helper, never hot-reloaded, so fast refresh's one-kind-of-export rule doesn't apply.
// eslint-disable-next-line react/only-export-components
function ShowLocation() {
  const { pathname, search } = useLocation();
  return <p>Location: {pathname + search}</p>;
}

/**
 * Render the whole app at a path, as the browser would (router + auth state + routes). With
 * `showLocation`, the current address is also shown as "Location: /path?query".
 */
export function renderApp(path: string, { showLocation = false } = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <ProfileProvider>
          <AppRoutes />
          {showLocation && <ShowLocation />}
        </ProfileProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}
