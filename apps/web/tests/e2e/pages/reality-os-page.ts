import { expect, type Page } from "@playwright/test";

export class RealityOsPage {
  constructor(private readonly page: Page) {}

  async goto(path: string, heading: string) {
    await this.page.goto(path);
    await expect(this.page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }

  async expectSection(name: string) {
    await expect(this.page.getByRole("heading", { name, exact: true })).toBeVisible();
  }

  async expectText(text: string | RegExp) {
    await expect(this.page.getByText(text)).toBeVisible();
  }

  async undoPendingWrite(title: string) {
    await this.page.getByRole("button", { name: `Undo pending write ${title}` }).click();
    await this.expectText("undo requested");
  }
}
