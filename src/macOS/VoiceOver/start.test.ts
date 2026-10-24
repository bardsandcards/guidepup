import { activate } from "../activate";
import { Applications } from "../Applications";
import { delay } from "../../delay";
import { ERR_VOICE_OVER_CANNOT_BE_STARTED } from "../errors";
import { runAppleScript } from "../runAppleScript";
import { start } from "./start";
import { waitForReady } from "./waitForReady";

jest.mock("../runAppleScript", () => ({
  runAppleScript: jest.fn(),
}));
jest.mock("../activate", () => ({
  activate: jest.fn(),
}));
jest.mock("../../delay", () => ({
  delay: jest.fn(),
}));
jest.mock("./waitForReady", () => ({
  waitForReady: jest.fn(),
}));

const options = { timeout: 1234 };

describe("when starting VoiceOver", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("when asking VoiceOver to start succeeds", () => {
    beforeEach(async () => {
      await start(options);
    });

    test("should ask VoiceOver to start with libScreenReader", () => {
      expect(runAppleScript).toHaveBeenCalledWith(
        expect.stringContaining("_ScreenReaderStart(0)"),
        options,
      );
    });

    test("should wait for VoiceOver to be ready, then bring it to the foreground", () => {
      expect(waitForReady).toHaveBeenCalledWith(options);
      expect(delay).toHaveBeenCalledWith(500);
      expect(activate).toHaveBeenCalledWith(Applications.VoiceOver, options);
      expect(
        jest.mocked(waitForReady).mock.invocationCallOrder[0],
      ).toBeLessThan(jest.mocked(activate).mock.invocationCallOrder[0]);
    });
  });

  describe("when asking VoiceOver to start fails", () => {
    const error = new Error("osascript failed");

    test("should reject with a startup error caused by the failure", async () => {
      jest.mocked(runAppleScript).mockRejectedValueOnce(error);

      await expect(start(options)).rejects.toMatchObject({
        message: ERR_VOICE_OVER_CANNOT_BE_STARTED,
        cause: error,
      });
      expect(waitForReady).not.toHaveBeenCalled();
      expect(activate).not.toHaveBeenCalled();
    });
  });

  describe("when activating VoiceOver fails", () => {
    const error = new Error("activation failed");

    test("should propagate the activation error to the caller", async () => {
      jest.mocked(activate).mockRejectedValueOnce(error);

      await expect(start(options)).rejects.toBe(error);
    });
  });
});
