import { voiceOver, XcuiAgent } from "../../src/";
import { execFileSync } from "child_process";
import { resolve } from "path";

const url = process.argv[2] ?? `file://${resolve(__dirname, "page.html")}`;
const maxSteps = Number(process.argv[3] ?? 30);

/** Stop once the cursor stops moving: the same speech this many times. */
const MAX_REPEATS = 2;
/** Stop after this many silent elements in a row. */
const MAX_SILENT = 3;

const delay = async (ms: number) =>
  await new Promise((resolve) => setTimeout(resolve, ms));

/**
 * Reads a page with VoiceOver, element by element, using XCUIVoiceOverService.
 *
 * guidepup starts and stops VoiceOver; the XCUI agent moves the VoiceOver
 * cursor and returns what VoiceOver said for each element.
 */
async function run(): Promise<void> {
  // `open` focuses Safari via LaunchServices, without an AppleEvent that
  // Safari may be too busy to answer while VoiceOver starts.
  const openInSafari = (...args: string[]) =>
    execFileSync("open", ["-b", "com.apple.Safari", ...args]);

  openInSafari(url);
  await delay(4000);

  await voiceOver.start();

  let agent: XcuiAgent | undefined;

  try {
    // Starting VoiceOver focuses it; give Safari focus back.
    openInSafari();
    agent = await XcuiAgent.start();

    let previous = (await agent.speech()).utterance;
    let repeats = 0;
    let silent = 0;

    console.log(`start: ${previous}`);

    for (let step = 1; step <= maxSteps; step++) {
      // moveForward() won't enter Safari's web area on its own, so interact
      // with it when the cursor lands on it.
      const direction = previous.endsWith("web content") ? "in" : "forward";
      const speech = await agent.move(direction);

      if (speech.silent) {
        console.log(`${step} ${direction}: (VoiceOver said nothing)`);
      } else {
        const note = speech.truncated ? " [truncated at 64 characters]" : "";
        console.log(`${step} ${direction}: ${speech.utterance}${note}`);
      }

      silent = speech.silent ? silent + 1 : 0;
      repeats = speech.utterance === previous ? repeats + 1 : 0;

      if (silent >= MAX_SILENT || repeats >= MAX_REPEATS) {
        console.log("The VoiceOver cursor stopped moving; end of the page.");
        break;
      }

      previous = speech.utterance;
    }
  } catch (e) {
    console.error(e);
  } finally {
    await agent?.stop();
    await voiceOver.stop();
  }
}

run();
