import { exec, ExecException } from "child_process";
import { activate } from "../activate";
import { Applications } from "../Applications";
import { delay } from "../../delay";
import { ERR_VOICE_OVER_CANNOT_BE_STARTED } from "../errors";
import { keyCodeCommands } from "./keyCodeCommands";
import { release } from "node:os";
import { sendKeys } from "../sendKeys";
import { start } from "./start";
import { waitForReady } from "./waitForReady";

jest.mock("child_process", () => ({
  exec: jest.fn(),
}));
jest.mock("../sendKeys", () => ({
  sendKeys: jest.fn(),
}));
jest.mock("./waitForReady", () => ({
  waitForReady: jest.fn(),
}));
jest.mock("node:os", () => ({
  release: jest.fn(),
}));
jest.mock("../activate", () => ({
  activate: jest.fn(),
}));
jest.mock("../../delay", () => ({
  delay: jest.fn(),
}));

const options = { timeout: 1234 };

describe("when starting VoiceOver", () => {
  let resultPromise: Promise<void>;

  const completeStarter = (error: ExecException | null = null) => {
    (
      jest.mocked(exec).mock.calls[0][1] as (
        error: ExecException | null,
        stdout: string,
        stderr: string,
      ) => void
    )(error, "", "");
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.mocked(release).mockReturnValue("26.0.0");
    resultPromise = start(options);
  });

  afterEach(async () => {
    if (jest.mocked(exec).mock.calls.length > 0) {
      completeStarter();
    }
    await resultPromise.catch(() => undefined);
  });

  test("should start VoiceOver using VoiceOverStarter before macOS 27", () => {
    expect(release).toHaveBeenCalled();
    expect(exec).toHaveBeenCalledWith(
      "/System/Library/CoreServices/VoiceOver.app/Contents/MacOS/VoiceOverStarter",
      expect.any(Function),
    );
  });

  test("should toggle VoiceOver on with its keyboard shortcut on macOS 27 and later", async () => {
    completeStarter();
    await resultPromise;
    jest.clearAllMocks();
    jest.mocked(release).mockReturnValue("27.0.0");

    await start(options);

    expect(release).toHaveBeenCalled();
    expect(sendKeys).toHaveBeenCalledWith(
      keyCodeCommands.start,
      undefined,
      options,
    );
    expect(waitForReady).toHaveBeenCalledWith(options);
    expect(exec).not.toHaveBeenCalled();
  });

  test("should reject when toggling VoiceOver on fails on macOS 27 and later", async () => {
    completeStarter();
    await resultPromise;
    jest.clearAllMocks();
    jest.mocked(release).mockReturnValue("27.0.0");

    const error = new Error("send keys failed");
    jest.mocked(sendKeys).mockRejectedValue(error);

    await expect(start(options)).rejects.toEqual(
      new Error(ERR_VOICE_OVER_CANNOT_BE_STARTED, { cause: error }),
    );
    expect(delay).not.toHaveBeenCalled();
    expect(activate).not.toHaveBeenCalled();
  });

  describe("when the starter succeeds", () => {
    beforeEach(() => {
      completeStarter();
    });

    test("should wait briefly before bringing VoiceOver to the foreground", async () => {
      await resultPromise;

      expect(delay).toHaveBeenCalledWith(500);
      expect(activate).toHaveBeenCalledWith(Applications.VoiceOver, options);
    });
  });

  describe("when the starter fails", () => {
    const error = new Error("test-error-message");

    beforeEach(() => {
      completeStarter(error);
    });

    test("should reject with a startup error", async () => {
      await expect(resultPromise).rejects.toEqual(
        new Error(ERR_VOICE_OVER_CANNOT_BE_STARTED, { cause: error }),
      );
      expect(delay).not.toHaveBeenCalled();
      expect(activate).not.toHaveBeenCalled();
    });
  });

  describe("when activating VoiceOver fails", () => {
    const error = new Error("activation failed");

    beforeEach(() => {
      jest.mocked(activate).mockRejectedValue(error);
      completeStarter();
    });

    test("should propagate the activation error to the caller", async () => {
      await expect(resultPromise).rejects.toBe(error);
    });
  });
});
