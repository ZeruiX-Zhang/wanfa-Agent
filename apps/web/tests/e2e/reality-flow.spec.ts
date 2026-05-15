import { expect, test } from "@playwright/test";
import { RealityOsPage } from "./pages/reality-os-page";

test.describe("Reality OS hardened acceptance flow", () => {
  test("renders input, memo, verification, pending knowledge, and supervisor approval surfaces", async ({ page }) => {
    const app = new RealityOsPage(page);

    await app.goto("/input", "Input");
    await app.expectSection("Capture Entrypoints");
    await app.expectSection("Clarification");
    await app.expectText("Browser extension");

    await app.goto("/decision/demo-case", "Decision Workbench");
    await app.expectSection("Decision Memo Draft");
    await app.expectSection("Evidence");
    await app.expectSection("Counterarguments");
    await app.expectSection("Risks");
    await app.expectText(/confidence \d+%/);

    await app.goto("/verification/demo-verification", "Verification");
    await app.expectSection("Claim");
    await app.expectSection("Evidence");
    await app.expectSection("Eval Summary");
    await app.expectSection("Trace");

    await app.goto("/reflection", "Reflection");
    await app.expectSection("Pending Knowledge Writes");
    await app.undoPendingWrite("Decision review lesson");

    await app.goto("/supervisor", "Supervisor");
    await app.expectSection("Agent Tasks");
    await app.expectSection("Approvals");
    await app.expectSection("Tool Calls");
    await app.expectText("High-risk actions require approval before execution.");
    await expect(page.getByRole("button", { name: "Approval required" })).toBeDisabled();
  });
});

