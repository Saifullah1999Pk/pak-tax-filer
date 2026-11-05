import { useNavigate } from "react-router";
import { useAuth } from "../auth/AuthContext";

/** Logs out (ending the session on the server) and returns to the login page (task T028). */
export function LogoutButton() {
  const { logout } = useAuth();
  const navigate = useNavigate();

  async function handleClick() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <button type="button" onClick={handleClick}>
      Log out
    </button>
  );
}
