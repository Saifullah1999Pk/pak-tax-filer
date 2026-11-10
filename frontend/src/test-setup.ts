import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// The suite runs files in parallel; on a busy machine a page can take over a second to appear.
// Waiting up to 3 s (instead of 1 s) only changes how long a failing test takes to report.
configure({ asyncUtilTimeout: 3000 });

// React Testing Library only cleans up automatically when Vitest's globals are on; they aren't,
// so unmount whatever each test rendered here. Without this, a second test in a file sees the
// first test's page too.
afterEach(cleanup);
