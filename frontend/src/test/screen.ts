import { fireEvent, screen } from "@testing-library/react";
import { vi } from "vitest";

/**
 * Pretend the screen is wide (a computer, 720 px and up) or narrow (a phone). jsdom has no
 * `matchMedia`, which the app reads as "wide"; tests call this to see the phone layout.
 */
export function screenIsWide(wide: boolean) {
  vi.stubGlobal(
    "matchMedia",
    (query: string) =>
      ({
        matches: wide,
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  );
}

/** Log out the way a user does now: open the Account menu, then choose Log out (task T035). */
export async function logOut() {
  fireEvent.click(await screen.findByRole("button", { name: "Account" }));
  fireEvent.click(screen.getByRole("button", { name: /log out/i }));
}
