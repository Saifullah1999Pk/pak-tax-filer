import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { DownloadPdfButton } from "./DownloadPdfButton";

// The PDF download (feature 008, task T005; contracts/pdf-and-telemetry.md). The PDF is made by
// the backend with the practitioner label on every page; this only offers it, or says why not.

test("downloads the PDF from its address", () => {
  render(<DownloadPdfButton href="/api/tax/2025-26/pdf" disabledReason={null} />);

  const link = screen.getByRole("link", { name: "Download PDF" });
  expect(link.getAttribute("href")).toBe("/api/tax/2025-26/pdf");
  expect(link.hasAttribute("download")).toBe(true);
});

test("when the result can't be exported, it says why and offers no download", () => {
  render(
    <DownloadPdfButton
      href="/api/tax/2025-26/pdf"
      disabledReason="Upload and confirm a salary certificate first."
    />,
  );

  expect(screen.queryByRole("link", { name: "Download PDF" })).toBeNull();
  const button = screen.getByRole("button", { name: "Download PDF" });
  expect(button.getAttribute("aria-disabled")).toBe("true");
  expect(button.getAttribute("aria-describedby")).toBeTruthy();
  expect(
    screen.getByText("Upload and confirm a salary certificate first."),
  ).toBeDefined();
});
