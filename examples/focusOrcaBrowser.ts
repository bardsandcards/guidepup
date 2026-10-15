import type { CommandOptions } from "../src/CommandOptions";
import { delay } from "../src/delay";
import { execFileSync } from "node:child_process";

const MAX_APPLICATION_SWITCH_RETRY_COUNT = 10;
const SPEECH_MONITOR_WINDOW_NAME = "On-screen speech";
const SPEECH_MONITOR_WINDOW_TIMEOUT = 2_000;

const cleanString = (str: string): string =>
  str
    .toLowerCase()
    .replace(/[|¦:;'"`\-‐–—·_()[\]{}\\^~]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

/**
 * Orca creates its speech monitor window the first time it speaks after the
 * monitor is turned on, and a window manager gives the new window focus. Wait
 * for it to be shown so it can't take focus after the browser is focused.
 */
const waitForSpeechMonitorWindow = () => {
  try {
    execFileSync(
      "xdotool",
      [
        "search",
        "--sync",
        "--onlyvisible",
        "--name",
        `^${SPEECH_MONITOR_WINDOW_NAME}$`,
      ],
      { stdio: "ignore", timeout: SPEECH_MONITOR_WINDOW_TIMEOUT },
    );
  } catch {
    // No speech monitor window to wait for.
  }
};

/**
 * The name of the window with X input focus, or `null` when it's unknown: no
 * window has focus, or the focused window has no name, as can happen when no
 * window manager is running.
 */
const getFocusedWindowName = (): string | null => {
  try {
    const name = execFileSync("xdotool", ["getwindowfocus", "getwindowname"], {
      stdio: ["ignore", "pipe", "ignore"],
    })
      .toString()
      .trim();

    return name || null;
  } catch {
    return null;
  }
};

type OrcaFocusController<Command> = {
  perform(
    command: Command,
    options?: Pick<CommandOptions, "capture">,
  ): Promise<void>;
  lastSpokenPhrase(): Promise<string>;
  spokenPhraseLog(): Promise<string[]>;
  clearSpokenPhraseLog(): Promise<void>;
};

export const focusOrcaBrowser = async <Command>({
  orca,
  pageTitle,
  presentTitleCommand,
}: {
  orca: OrcaFocusController<Command>;
  pageTitle: string;
  presentTitleCommand: Command;
}): Promise<void> => {
  const cleanedPageTitle = cleanString(pageTitle);

  if (!cleanedPageTitle) {
    throw new Error("Cannot focus a browser window with an empty page title.");
  }
  const currentSpokenPhraseLog = [...(await orca.spokenPhraseLog())];

  try {
    await orca.perform(presentTitleCommand, { capture: "initial" });
    waitForSpeechMonitorWindow();

    for (
      let retryCount = 0;
      retryCount <= MAX_APPLICATION_SWITCH_RETRY_COUNT;
      retryCount++
    ) {
      await orca.clearSpokenPhraseLog();
      await orca.perform(presentTitleCommand, { capture: "initial" });

      const windowTitle = cleanString(await orca.lastSpokenPhrase());
      const isOrcaOnBrowser = windowTitle.includes(cleanedPageTitle);
      const focusedWindowName = getFocusedWindowName();
      const hasInputFocus =
        focusedWindowName === null
          ? isOrcaOnBrowser
          : cleanString(focusedWindowName).includes(cleanedPageTitle);

      if (isOrcaOnBrowser && hasInputFocus) {
        return;
      }

      if (retryCount < MAX_APPLICATION_SWITCH_RETRY_COUNT) {
        // Orca can lag behind a window switch, so only switch windows when the
        // browser doesn't have input focus.
        if (!hasInputFocus) {
          execFileSync("xdotool", ["key", "--clearmodifiers", "alt+Tab"]);
        }

        await delay(100);
      }
    }

    throw new Error(
      `Unable to focus browser window with title "${pageTitle}" after ${MAX_APPLICATION_SWITCH_RETRY_COUNT} Alt+Tab attempts.`,
    );
  } finally {
    await orca.clearSpokenPhraseLog();

    const spokenPhraseLog = await orca.spokenPhraseLog();

    spokenPhraseLog.push(...currentSpokenPhraseLog);
  }
};
