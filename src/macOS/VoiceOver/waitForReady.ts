import { Applications } from "../Applications";
import type { CommandOptions } from "../../CommandOptions";
import { DEFAULT_RUNNING_TIMEOUT } from "../../constants";
import { ERR_VOICE_OVER_RUNNING_TIMEOUT } from "../errors";
import { isRunning } from "./isRunning";
import { runAppleScript } from "../runAppleScript";
import { waitForCondition } from "../../waitForCondition";

// Not ready yet: the process isn't registered with LaunchServices (-600), or
// it hasn't answered the event in time (-1712).
const NOT_READY = /\((-600|-1712)\)/;

/**
 * Waits until VoiceOver answers an AppleEvent itself. Any answer, even an
 * error about the property, means it is ready.
 */
export async function waitForReady(options?: CommandOptions): Promise<void> {
  return await waitForCondition(
    async () => {
      // Only address VoiceOver once its process exists, so the probe can't
      // launch it.
      if (!(await isRunning(options, true))) {
        return false;
      }

      try {
        await runAppleScript(
          `tell application "${Applications.VoiceOver}"\nreturn enabled of caption window\nend tell`,
          { timeout: 1000 },
        );
      } catch (error) {
        return !NOT_READY.test(error.message);
      }

      return true;
    },
    {
      pollTimeout: DEFAULT_RUNNING_TIMEOUT,
      timeoutErrorMessage: ERR_VOICE_OVER_RUNNING_TIMEOUT,
    },
  );
}
