import { connect, Socket } from "node:net";
import { execFileSync, spawn } from "child_process";
import { existsSync, readdirSync, statSync } from "node:fs";
import { createInterface } from "node:readline";
import { EventEmitter } from "node:events";
import { XcuiAgent } from "./XcuiAgent";

jest.mock("child_process", () => ({
  execFileSync: jest.fn(),
  spawn: jest.fn(),
}));

jest.mock("node:fs", () => ({
  ...jest.requireActual("node:fs"),
  existsSync: jest.fn(),
  mkdirSync: jest.fn(),
  readdirSync: jest.fn(),
  statSync: jest.fn(),
}));

type Request = Record<string, unknown>;
type Reply = (request: Request) => Record<string, unknown>;

class FakeRunner extends EventEmitter {
  stdout = new EventEmitter();
  stderr = new EventEmitter();
  exitCode: number | null = null;
  signalCode: string | null = null;
  // Like a real ChildProcess, a killed runner exits with a signal, not a code.
  kill = jest.fn(() => this.exit(null, "SIGTERM"));

  exit(code: number | null, signal: string | null = null) {
    this.exitCode = code;
    this.signalCode = signal;
    this.emit("exit", code, signal);
  }
}

const NO_SPEECH = {
  ok: false,
  error: "No speech available",
  code: 3,
  domain: "com.apple.xctest.voiceoverservice",
};

let runner: FakeRunner;
let agentSocket: Socket | undefined;
let received: Request[];

/**
 * Stand in for the XCTest agent: connect back to the client's socket with the
 * given hello, then answer each request line with `reply`.
 */
function fakeAgent({
  reply = () => ({ ok: true }),
  hello = (token: string) => token,
  connects = true,
  exitsOnShutdown = true,
}: {
  reply?: Reply;
  hello?: (token: string) => string;
  connects?: boolean;
  exitsOnShutdown?: boolean;
} = {}) {
  jest.mocked(spawn).mockImplementation((_command, _args, options) => {
    runner = new FakeRunner();

    if (connects) {
      const env = options.env as Record<string, string>;
      const socket = connect(Number(env.TEST_RUNNER_AGENT_PORT), "127.0.0.1");

      agentSocket = socket;
      socket.on("connect", () => {
        socket.write(
          `${JSON.stringify({ hello: hello(env.TEST_RUNNER_AGENT_TOKEN) })}\n`,
        );
      });
      socket.on("error", () => undefined);
      createInterface({ input: socket }).on("line", (line) => {
        const request = JSON.parse(line);

        received.push(request);
        socket.write(`${JSON.stringify(reply(request))}\n`);

        if (request.command === "shutdown" && exitsOnShutdown) {
          socket.end();
          runner.exit(0);
        }
      });
    }

    return runner as never;
  });
}

/** An agent build that is up to date unless `stale` is set. */
function builtAgent({ exists = true, stale = false, xctestrun = true } = {}) {
  jest.mocked(existsSync).mockReturnValue(exists);
  jest.mocked(readdirSync).mockImplementation(((dir: string) => {
    if (!dir.endsWith("Build/Products")) {
      return ["Source.swift"];
    }

    return xctestrun ? ["VoiceOverAgent_macosx27.0-arm64.xctestrun"] : [];
  }) as never);
  jest.mocked(statSync).mockImplementation(((file: string) => ({
    mtimeMs: file.endsWith(".xctestrun") ? (stale ? 1 : 3) : 2,
  })) as never);
}

describe("XcuiAgent", () => {
  let agent: XcuiAgent | undefined;

  beforeEach(() => {
    jest.resetAllMocks();
    received = [];
    agent = undefined;
    agentSocket = undefined;
    builtAgent();
  });

  afterEach(async () => {
    jest.useRealTimers();
    await agent?.stop();
    agentSocket?.destroy();
  });

  describe("start", () => {
    it.each`
      description             | build                              | rebuilds
      ${"is up to date"}      | ${{}}                              | ${false}
      ${"is older than code"} | ${{ stale: true }}                 | ${true}
      ${"has never been run"} | ${{ exists: false, stale: false }} | ${true}
      ${"is missing"}         | ${{ xctestrun: false }}            | ${true}
    `(
      "should only build the agent when the build $description",
      async ({ build, rebuilds }) => {
        builtAgent(build);
        jest.mocked(execFileSync).mockImplementation((() => {
          // The build produces an up-to-date .xctestrun.
          builtAgent();
        }) as never);
        fakeAgent();

        agent = await XcuiAgent.start();

        expect(execFileSync).toHaveBeenCalledTimes(rebuilds ? 1 : 0);
        expect(spawn).toHaveBeenCalledWith(
          "xcodebuild",
          expect.arrayContaining([
            "test-without-building",
            "-only-testing:AgentTests/VoiceOverAgentTests/testServe",
          ]),
          expect.anything(),
        );
      },
    );

    it("should fail clearly when the build produces no agent", async () => {
      builtAgent({ exists: false });
      fakeAgent();

      await expect(XcuiAgent.start()).rejects.toThrow(
        "XCUI agent build produced no up-to-date .xctestrun",
      );
      expect(spawn).not.toHaveBeenCalled();
    });

    it("should fail clearly when xcodebuild can't be launched", async () => {
      jest.mocked(spawn).mockImplementation(() => {
        runner = new FakeRunner();
        setImmediate(() =>
          runner.emit("error", new Error("spawn xcodebuild ENOENT")),
        );

        return runner as never;
      });

      await expect(XcuiAgent.start()).rejects.toThrow(
        "XCUI agent could not be launched: spawn xcodebuild ENOENT",
      );
    });

    it("should give up when the agent never connects, e.g. stuck on an authorisation prompt", async () => {
      jest.useFakeTimers({ doNotFake: ["nextTick", "setImmediate"] });
      fakeAgent({ connects: false });

      const starting = XcuiAgent.start();
      const outcome = expect(starting).rejects.toThrow(
        "Timed out waiting for the XCUI agent",
      );

      await new Promise((resolve) => setImmediate(resolve));
      jest.advanceTimersByTime(120_000);
      await outcome;

      expect(runner.kill).toHaveBeenCalled();
      jest.useRealTimers();
    });

    it("should ignore connections without the token, and keep waiting for the agent", async () => {
      jest.mocked(spawn).mockImplementation((_command, _args, options) => {
        const env = options.env as Record<string, string>;
        const port = Number(env.TEST_RUNNER_AGENT_PORT);

        runner = new FakeRunner();

        const imposter = connect(port, "127.0.0.1", () =>
          imposter.write("not json\n"),
        );
        imposter.on("error", () => undefined);
        imposter.on("close", () => {
          // Only once the imposter is rejected does the real agent connect.
          const socket = connect(port, "127.0.0.1", () =>
            socket.write(
              `${JSON.stringify({ hello: env.TEST_RUNNER_AGENT_TOKEN })}\n`,
            ),
          );
          agentSocket = socket;
          createInterface({ input: socket }).on("line", (line) => {
            received.push(JSON.parse(line));
            socket.write(`${JSON.stringify({ ok: true, isEnabled: true })}\n`);
          });
        });

        return runner as never;
      });

      agent = await XcuiAgent.start();

      await expect(agent.isEnabled()).resolves.toBe(true);
      runner.exit(0);
    });

    it("should fail with the runner's output when it exits before connecting", async () => {
      fakeAgent({ connects: false });

      const starting = XcuiAgent.start();

      await new Promise((resolve) => setImmediate(resolve));
      runner.stdout.emit(
        "data",
        Buffer.from("Not authorized for performing UI testing actions."),
      );
      runner.exit(65);

      await expect(starting).rejects.toThrow(
        /exited \(code 65\) before connecting:\nNot authorized for performing UI testing actions\./,
      );
    });
  });

  describe("speech", () => {
    it.each`
      call                                                    | request
      ${(a: XcuiAgent) => a.speech()}                         | ${{ command: "speech" }}
      ${(a: XcuiAgent) => a.move("in")}                       | ${{ command: "move", direction: "in" }}
      ${(a: XcuiAgent) => a.move("out")}                      | ${{ command: "move", direction: "out" }}
      ${(a: XcuiAgent) => a.move(("back" + "ward") as never)} | ${{ command: "move", direction: "backward" }}
    `(
      "should send $request and return what VoiceOver said",
      async ({ call, request }) => {
        fakeAgent({
          reply: () => ({
            ok: true,
            utterance: "link Checkout",
            truncated: false,
          }),
        });
        agent = await XcuiAgent.start();

        await expect(call(agent)).resolves.toEqual({
          utterance: "link Checkout",
          truncated: false,
          silent: false,
        });
        expect(received).toEqual([request]);
      },
    );

    it("should pass on when an utterance hit the 64 character limit", async () => {
      fakeAgent({
        reply: () => ({ ok: true, utterance: "x".repeat(64), truncated: true }),
      });
      agent = await XcuiAgent.start();

      await expect(agent.move("forward")).resolves.toMatchObject({
        truncated: true,
      });
    });

    it("should report silence, rather than fail, when VoiceOver says nothing", async () => {
      fakeAgent({ reply: () => NO_SPEECH });
      agent = await XcuiAgent.start();

      await expect(agent.move("forward")).resolves.toEqual({
        utterance: "",
        truncated: false,
        silent: true,
      });
    });

    it("should fail on other VoiceOver errors", async () => {
      fakeAgent({
        reply: () => ({
          ok: false,
          error: "VoiceOver is not running",
          code: 2,
          domain: NO_SPEECH.domain,
        }),
      });
      agent = await XcuiAgent.start();

      await expect(agent.move("forward")).rejects.toThrow(
        "XCUI agent: VoiceOver is not running (code 2)",
      );
    });

    it("should match concurrent requests to their own responses, in order", async () => {
      fakeAgent({
        reply: (request) => ({
          ok: true,
          utterance: `moved ${request.direction}`,
          truncated: false,
        }),
      });
      agent = await XcuiAgent.start();

      const results = await Promise.all([
        agent.move("forward"),
        agent.move("in"),
        agent.move("out"),
      ]);

      expect(results.map((result) => result.utterance)).toEqual([
        "moved forward",
        "moved in",
        "moved out",
      ]);
    });

    it("should fail a request when the agent's response isn't valid JSON", async () => {
      fakeAgent();
      agent = await XcuiAgent.start();
      jest.mocked(spawn).mockClear();

      const moving = agent.move("forward");
      agentSocket?.write("garbage\n");

      // The garbage line is consumed as this request's response.
      await expect(moving).rejects.toThrow(SyntaxError);
    });

    it("should fail pending requests when the agent disconnects", async () => {
      fakeAgent({
        reply: () => {
          agentSocket?.destroy();
          runner.exit(1);

          return { ok: true };
        },
      });
      agent = await XcuiAgent.start();

      await expect(agent.move("forward")).rejects.toThrow(
        "XCUI agent disconnected",
      );
    });
  });

  describe("stop", () => {
    it("should ask the agent to shut down and wait for it to exit", async () => {
      fakeAgent();
      agent = await XcuiAgent.start();

      await agent.stop();

      expect(received).toContainEqual({ command: "shutdown" });
      expect(runner.exitCode).toBe(0);
    });

    it("should kill an agent that doesn't exit after shutting down", async () => {
      fakeAgent({ exitsOnShutdown: false });
      agent = await XcuiAgent.start();
      jest.useFakeTimers({ doNotFake: ["nextTick", "setImmediate"] });

      const stopping = agent.stop();

      // Let the shutdown round-trip, then run out the 10s grace period.
      while (!runner.kill.mock.calls.length) {
        await new Promise((resolve) => setImmediate(resolve));
        jest.advanceTimersByTime(10_000);
      }
      await stopping;

      expect(received).toContainEqual({ command: "shutdown" });
    });

    it("should not hang or crash when the agent has already died", async () => {
      fakeAgent();
      agent = await XcuiAgent.start();

      // A crashed runner drops the connection.
      agentSocket?.resetAndDestroy();
      runner.exit(1);
      await new Promise((resolve) => setTimeout(resolve, 50));

      await expect(agent.stop()).resolves.toBeUndefined();
    });
  });
});
