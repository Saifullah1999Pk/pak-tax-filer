import { Route, Routes } from "react-router";
import { RequireAuth } from "./auth/RequireAuth";
import { DocumentsPage } from "./pages/DocumentsPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ProfilePage } from "./pages/ProfilePage";
import { ReviewPage } from "./pages/ReviewPage";
import { SignupPage } from "./pages/SignupPage";
import { TaxPage } from "./pages/TaxPage";
import { WealthPage } from "./pages/WealthPage";
import { RequireProfile } from "./profile/RequireProfile";

/**
 * The app's pages (feature 002 tasks T029, T041; feature 003 tasks T015, T019; feature 004 task T013). Every logged-in page except /profile also needs the
 * taxpayer profile. main.tsx provides the router, AuthProvider and ProfileProvider.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route
        path="/profile"
        element={
          <RequireAuth>
            <ProfilePage />
          </RequireAuth>
        }
      />
      <Route
        path="/documents"
        element={
          <RequireAuth>
            <RequireProfile>
              <DocumentsPage />
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/documents/:id"
        element={
          <RequireAuth>
            <RequireProfile>
              <ReviewPage />
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/tax"
        element={
          <RequireAuth>
            <RequireProfile>
              <TaxPage />
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/wealth"
        element={
          <RequireAuth>
            <RequireProfile>
              <WealthPage />
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <RequireProfile>
              <HomePage />
            </RequireProfile>
          </RequireAuth>
        }
      />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
