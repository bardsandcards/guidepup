import { DEFAULT_RUNNING_TIMEOUT } from "../../constants";
import { ERR_VOICE_OVER_RUNNING_TIMEOUT } from "../errors";
import { isRunning } from "./isRunning";
import { runAppleScript } from "../runAppleScript";
import { waitForCondition } from "../../waitForCondition";
import { waitForReady } from "./waitForReady";

jest.mock("./isRunning", () => ({
  isRunning: jest.fn(),
}));
jest.mock("../runAppleScript", () => ({
  runAppleScript: jest.fn(),
}));
jest.mock("../../waitForCondition", () => ({
  waitForCondition: jest.fn(),
}));

const options = { timeout: 1234 };

describe("waitForReady", () => {
  let condition: () => Promise<boolean>;

  beforeEach(async () => {
    jest.clearAllMocks();
    jest.mocked(isRunning).mockResolvedValue(true);

    await waitForReady(options);

    condition = jest.mocked(waitForCondition).mock
      .calls[0][0] as () => Promise<boolean>;
  });

  it("should wait up to the running timeout", () => {
    expect(waitForCondition).toHaveBeenCalledWith(expect.any(Function), {
      pollTimeout: DEFAULT_RUNNING_TIMEOUT,
      timeoutErrorMessage: ERR_VOICE_OVER_RUNNING_TIMEOUT,
    });
  });

  it("should not address VoiceOver before its process exists", async () => {
    jest.mocked(isRunning).mockResolvedValue(false);

    await expect(condition()).resolves.toBe(false);
    expect(isRunning).toHaveBeenCalledWith(options, true);
    expect(runAppleScript).not.toHaveBeenCalled();
  });

  it("should be ready when VoiceOver answers", async () => {
    jest.mocked(runAppleScript).mockResolvedValue("true");

    await expect(condition()).resolves.toBe(true);
  });

  it.each`
    description                      | message                                                 | expected
    ${"an error about the property"} | ${"execution error: Can’t get enabled. (-1728)"}        | ${true}
    ${"application isn't running"}   | ${"execution error: Application isn’t running. (-600)"} | ${false}
    ${"an AppleEvent timeout"}       | ${"execution error: AppleEvent timed out. (-1712)"}     | ${false}
  `(
    "should be ready $expected when VoiceOver answers with $description",
    async ({ message, expected }) => {
      jest.mocked(runAppleScript).mockRejectedValue(new Error(message));

      await expect(condition()).resolves.toBe(expected);
    },
  );
});
