import { platform, release } from "os";
import { delay } from "../../../../src/delay";
import { expect } from "@playwright/test";
import { log } from "../../../log";
import { screenReaderTest as test } from "../../screenreader-test";

const MAX_NAVIGATION_LOOP = 10;

const record = async (filepath: string) => {
  try {
    const { record: guidepupRecord } = await import("@guidepup/record");

    return guidepupRecord(filepath);
  } catch {
    console.warn(
      "@guidepup/record not available. Recording will be skipped. This is expected on platforms without ffmpeg support (e.g., Windows ARM64).",
    );
  }
};

test.describe("Firefox Playwright Screen Reader", () => {
  test("I can capture screen reader output from live regions", async ({
    browser,
    browserName,
    page,
    screenReader,
  }) => {
    const osName = platform();
    const osVersion = release();
    const browserVersion = browser.version();
    const screenReaderName = screenReader.name;
    const screenReaderVersion = screenReader.version;
    const { retry } = test.info();
    const recordingFilePath = `./recordings/playwright-screenreader-live-region-${osName}-${osVersion}-${browserName}-${browserVersion}-attempt-${retry}-${+new Date()}.mov`;

    console.table({
      osName,
      osVersion,
      browserName,
      browserVersion,
      screenReaderName,
      screenReaderVersion,
      retry,
    });

    let stopRecording: (() => Promise<void>) | undefined;

    try {
      stopRecording = await record(recordingFilePath);

      log("Navigating to live region test page.");

      await page.goto("about:blank", {
        waitUntil: "load",
      });

      await page.setContent(`
<!doctype html>
<html>
  <head>
    <title>Guidepup Live Region Test</title>
  </head>
  <body>
    <main>
      <h1>Example 1</h1>
      <button id="trigger">Update</button>
    </main>

    <div role="alert" id="live"></div>

    <script>
      document.querySelector("#trigger").addEventListener("click", () => {
        document.querySelector("#live").textContent = "testing testing 123"
      });
    </script>
  </body>
</html>
    `);

      const button = page.locator("#trigger");
      await button.waitFor();
      await delay(500);

      await screenReader.navigateToWebContent();
      await delay(500);

      let navigationCount = 0;

      while (
        !(await screenReader.itemText())
          .replaceAll(/\s/g, "")
          .includes("Update") &&
        navigationCount <= MAX_NAVIGATION_LOOP
      ) {
        navigationCount++;

        log(`Performing command: "Orca+Ctrl+Right Arrow"`);
        await screenReader.next();
        log(
          `Screen reader output: "${await screenReader.lastSpokenPhrase()}".`,
        );
      }

      log(`Performing command: "Orca+Ctrl+Enter"`);
      await screenReader.act();
      const clickSpokenPhrase = await screenReader.lastSpokenPhrase();
      log(`Screen reader output: "${clickSpokenPhrase}".`);

      expect(clickSpokenPhrase).toContain("testing testing 123");
    } finally {
      await stopRecording?.();
    }
  });
});
