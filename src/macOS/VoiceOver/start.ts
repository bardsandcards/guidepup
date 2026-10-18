import { activate } from "../activate";
import { Applications } from "../Applications";
import { base } from "../../debug";
import type { CommandOptions } from "../../CommandOptions";
import { delay } from "../../delay";
import { ERR_VOICE_OVER_CANNOT_BE_STARTED } from "../errors";
import { exec } from "child_process";
import { keyCodeCommands } from "./keyCodeCommands";
import { release } from "node:os";
import { sendKeys } from "../sendKeys";
import { waitForReady } from "./waitForReady";

const debug = base.extend("start");

const VOICE_OVER_STARTER =
  "/System/Library/CoreServices/VoiceOver.app/Contents/MacOS/VoiceOverStarter";

function platformMajorVersion(): number {
  const osVersion = release().split(".", 1)[0];

  return Number(osVersion);
}

export async function start(options?: CommandOptions): Promise<void> {
  const darwinMajorVersion = platformMajorVersion();

  if (darwinMajorVersion >= 27) {
    // The system toggle asks VoiceOver to start straight away. Launched any
    // other way (e.g. `open -a`), VoiceOver waits ~9s for that request first.
    // `start()` has already made sure VoiceOver isn't running, so the toggle
    // can only turn it on.
    debug("toggling VoiceOver on");

    try {
      await sendKeys(keyCodeCommands.start, undefined, options);
    } catch (cause) {
      debug("toggling VoiceOver on failed", cause);

      throw new Error(ERR_VOICE_OVER_CANNOT_BE_STARTED, {
        cause,
      });
    }

    // VoiceOver can't take AppleEvents until it has finished starting.
    await waitForReady(options);
  } else {
    debug("executing VoiceOver Starter");

    await new Promise<void>((resolve, reject) => {
      exec(VOICE_OVER_STARTER, (cause) => {
        if (cause) {
          debug("VoiceOver Starter failed", cause);

          reject(new Error(ERR_VOICE_OVER_CANNOT_BE_STARTED, { cause }));
        } else {
          debug("VoiceOver Starter succeeded");

          resolve();
        }
      });
    });
  }

  await delay(500);

  await activate(Applications.VoiceOver, options);
}
