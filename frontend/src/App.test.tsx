import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import App from "./App";

// Fails if the placeholder page has no heading naming the app (spec FR-004, task T011).
test("the placeholder page shows a heading with the app name", () => {
  render(<App />);

  const heading = screen.getByRole("heading", { name: /pak-tax-filer/i });

  expect(heading).toBeTruthy();
});
