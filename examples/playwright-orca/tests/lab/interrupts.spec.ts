// Lab scenarios (untracked, bardsandcards/guidepup#21): who interrupts whom on Orca.
import { begin, end, page as html, settle } from "./fidelity";
import { delay } from "../../../../src/delay";
import { orcaTest as test } from "../../orca-test";

const LONG_A = "Apply the twenty percent seasonal discount to every item in your basket before checkout";
const LONG_B = "Review the shipping address and delivery window for this order before you pay";
const LONG_C = "Remove all saved payment methods from this account and sign out of every device";
const LIVE_LONG = "Your order has been placed and a confirmation email is on its way to your inbox now";
const LIVE_SHORT = "Saved. Your changes were stored.";

const live = (politeness: string) => `<div id="lr" aria-live="${politeness}"></div>`;

test("S1 assertive live region 300ms into a long focus announcement", async ({ page, orca }, info) => {
  await page.setContent(html("S1", `<button>Start</button><button id="b">${LONG_A}</button>${live("assertive")}`,
    `b.addEventListener("focus", () => setTimeout(() => { lr.textContent = ${JSON.stringify(LIVE_SHORT)}; }, 300));`));
  await orca.navigateToWebContent();
  await orca.press("Tab", { capture: false });
  await begin(info, orca);
  await orca.press("Tab", { capture: false });
  await end(info, orca);
});

test("S2 polite live region 300ms into a long focus announcement", async ({ page, orca }, info) => {
  await page.setContent(html("S2", `<button>Start</button><button id="b">${LONG_A}</button>${live("polite")}`,
    `b.addEventListener("focus", () => setTimeout(() => { lr.textContent = ${JSON.stringify(LIVE_SHORT)}; }, 300));`));
  await orca.navigateToWebContent();
  await orca.press("Tab", { capture: false });
  await begin(info, orca);
  await orca.press("Tab", { capture: false });
  await end(info, orca);
});

test("S3 Tab 600ms into a long assertive live region", async ({ page, orca }, info) => {
  await page.setContent(html("S3", `<button>Start</button><button>Next</button>${live("assertive")}`));
  await orca.navigateToWebContent();
  await orca.press("Tab", { capture: false });
  await begin(info, orca);
  await page.evaluate((t) => { document.getElementById("lr")!.textContent = t; }, LIVE_LONG);
  await delay(600);
  await orca.press("Tab", { capture: false });
  await end(info, orca);
});

test("S4 three Tabs 400ms apart through long buttons", async ({ page, orca }, info) => {
  await page.setContent(html("S4", `<button>Start</button><button>${LONG_A}</button><button>${LONG_B}</button><button>${LONG_C}</button>`));
  await orca.navigateToWebContent();
  await orca.press("Tab", { capture: false });
  await begin(info, orca);
  for (let i = 0; i < 3; i++) {
    await orca.press("Tab", { capture: false });
    await delay(400);
  }
  await end(info, orca);
});

test("S5 two long assertive updates 300ms apart, no input", async ({ page, orca }, info) => {
  await page.setContent(html("S5", `<button>Start</button>${live("assertive")}`));
  await orca.navigateToWebContent();
  await orca.press("Tab", { capture: false });
  await begin(info, orca);
  await page.evaluate((t) => { document.getElementById("lr")!.textContent = t; }, LIVE_LONG);
  await delay(300);
  await page.evaluate((t) => { document.getElementById("lr")!.textContent = t; }, LONG_B);
  await end(info, orca);
});

test("S6 Enter on a button that updates an assertive live region", async ({ page, orca }, info) => {
  await page.setContent(html("S6", `<button id="b">Place order</button>${live("assertive")}`,
    `b.addEventListener("click", () => { lr.textContent = ${JSON.stringify(LIVE_LONG)}; });`));
  await orca.navigateToWebContent();
  await orca.press("Tab", { capture: false });
  await settle();
  await begin(info, orca);
  await orca.press("Enter", { capture: false });
  await end(info, orca);
});

test("S7 typing into a field", async ({ page, orca }, info) => {
  await page.setContent(html("S7", `<label>Name <input id="n"></label>`));
  await orca.navigateToWebContent();
  await orca.press("Tab", { capture: false });
  await settle();
  await begin(info, orca);
  await orca.type("hello world", { capture: false });
  await end(info, orca);
});

test("S8 guidepup capture of typing (key echo on)", async ({ page, orca }, info) => {
  await page.setContent(html("S8", `<label>Name <input id="n"></label>`));
  await orca.navigateToWebContent();
  await orca.press("Tab", { capture: false });
  await settle();
  await begin(info, orca);
  await orca.type("hi", { capture: true });
  console.log(`GUIDEPUP ${JSON.stringify({ last: await orca.lastSpokenPhrase(), log: await orca.spokenPhraseLog() })}`);
  console.log(`VALUE ${await page.locator("#n").inputValue()}`);
  await end(info, orca);
});
