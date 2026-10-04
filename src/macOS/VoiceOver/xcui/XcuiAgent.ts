import { ChildProcess, execFileSync, spawn } from "child_process";
import { createServer, Server, Socket } from "node:net";
import { existsSync, mkdirSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { base } from "../../../debug";
import { createInterface } from "node:readline";
import { homedir } from "node:os";
import { randomBytes } from "node:crypto";

const debug = base.extend("xcui");

const AGENT_DIR = resolve(__dirname, "../../../../xcui-agent");
const AGENT_PROJECT = join(AGENT_DIR, "VoiceOverAgent.xcodeproj");
const AGENT_SOURCES = [
  join(AGENT_DIR, "AgentTests"),
  join(AGENT_DIR, "Host"),
  AGENT_PROJECT,
];
const DERIVED_DATA = join(homedir(), "Library/Caches/guidepup/xcui-agent");
const PRODUCTS = join(DERIVED_DATA, "Build/Products");
const CONNECT_TIMEOUT = 120_000;
const STOP_TIMEOUT = 10_000;
const OUTPUT_TAIL = 4000;

export type XcuiDirection = "forward" | "backward" | "in" | "out";

export interface XcuiSpeech {
  /** What VoiceOver said. XCUIVoiceOverService cuts this off at 64 characters. */
  utterance: string;
  /** Whether the utterance reached the 64 character limit and may be cut off. */
  truncated: boolean;
}

interface Pending {
  resolve: (response: Record<string, unknown>) => void;
  reject: (error: Error) => void;
}

function newestSourceMtime(): number {
  return AGENT_SOURCES.flatMap((dir) =>
    readdirSync(dir).map((name) => statSync(join(dir, name)).mtimeMs),
  ).reduce((newest, mtime) => Math.max(newest, mtime), 0);
}

/**
 * The built agent's .xctestrun, if it exists and is newer than the sources.
 */
function findXctestrun(): string | undefined {
  if (!existsSync(PRODUCTS)) {
    return undefined;
  }

  const file = readdirSync(PRODUCTS).find((name) =>
    name.endsWith(".xctestrun"),
  );

  if (!file) {
    return undefined;
  }

  const xctestrun = join(PRODUCTS, file);

  return statSync(xctestrun).mtimeMs > newestSourceMtime()
    ? xctestrun
    : undefined;
}

function buildAgent(): string {
  debug("building agent", { project: AGENT_PROJECT });
  mkdirSync(DERIVED_DATA, { recursive: true });

  execFileSync(
    "xcodebuild",
    [
      "build-for-testing",
      "-project",
      AGENT_PROJECT,
      "-scheme",
      "VoiceOverAgent",
      "-destination",
      "platform=macOS",
      "-derivedDataPath",
      DERIVED_DATA,
    ],
    { stdio: "ignore" },
  );

  const xctestrun = findXctestrun();

  if (!xctestrun) {
    throw new Error("XCUI agent build produced no up-to-date .xctestrun");
  }

  return xctestrun;
}

/**
 * Drives VoiceOver through Apple's XCUIVoiceOverService (macOS 27+).
 *
 * The service is only usable inside an authorised UI test run, so this
 * starts a long-running XCTest "agent" that connects back to a local socket
 * and answers commands. VoiceOver must already be running (e.g. via
 * `voiceOver.start()`); the agent never starts or stops it.
 */
export class XcuiAgent {
  #server: Server;
  #socket: Socket;
  #child: ChildProcess;
  #queue: Promise<unknown> = Promise.resolve();
  #pending: Pending[] = [];

  private constructor(server: Server, socket: Socket, child: ChildProcess) {
    this.#server = server;
    this.#socket = socket;
    this.#child = child;

    createInterface({ input: socket }).on("line", (line) => {
      const pending = this.#pending.shift();

      try {
        pending?.resolve(JSON.parse(line));
      } catch (error) {
        pending?.reject(error as Error);
      }
    });

    socket.on("close", () => {
      for (const pending of this.#pending.splice(0)) {
        pending.reject(new Error("XCUI agent disconnected"));
      }
    });
  }

  /**
   * Build the agent if needed, launch it, and wait for it to connect.
   */
  static async start(): Promise<XcuiAgent> {
    const xctestrun = findXctestrun() ?? buildAgent();
    const token = randomBytes(16).toString("hex");
    const server = createServer();

    await new Promise<void>((done) => server.listen(0, "127.0.0.1", done));

    const { port } = server.address() as { port: number };

    debug("launching agent", { xctestrun, port });

    const child = spawn(
      "xcodebuild",
      [
        "test-without-building",
        "-xctestrun",
        xctestrun,
        "-destination",
        "platform=macOS",
        "-only-testing:AgentTests/VoiceOverAgentTests/testServe",
      ],
      {
        env: {
          ...process.env,
          TEST_RUNNER_AGENT_PORT: String(port),
          TEST_RUNNER_AGENT_TOKEN: token,
        },
        stdio: ["ignore", "pipe", "pipe"],
      },
    );

    let output = "";
    const collect = (chunk: Buffer) => {
      output = (output + chunk.toString()).slice(-OUTPUT_TAIL);
    };

    child.stdout.on("data", collect);
    child.stderr.on("data", collect);

    try {
      const socket = await new Promise<Socket>((done, fail) => {
        const timer = setTimeout(
          () => fail(new Error("Timed out waiting for the XCUI agent")),
          CONNECT_TIMEOUT,
        );

        child.once("exit", (code) => {
          clearTimeout(timer);
          fail(
            new Error(
              `XCUI agent exited (code ${code}) before connecting:\n${output}`,
            ),
          );
        });

        server.on("connection", (socket) => {
          createInterface({ input: socket }).once("line", (line) => {
            let hello: unknown;

            try {
              hello = JSON.parse(line).hello;
            } catch {
              // Treated as a bad hello below.
            }

            if (hello !== token) {
              debug("rejected connection with bad hello");
              socket.destroy();

              return;
            }

            clearTimeout(timer);
            done(socket);
          });
        });
      });

      debug("agent connected");

      return new XcuiAgent(server, socket, child);
    } catch (error) {
      child.kill();
      server.close();

      throw error;
    }
  }

  /**
   * Whether VoiceOver is enabled, according to XCUIVoiceOverService.
   */
  async isEnabled(): Promise<boolean> {
    const response = await this.#request({ command: "status" });

    return response.isEnabled as boolean;
  }

  /**
   * Move the VoiceOver cursor and return what VoiceOver said.
   */
  async move(direction: XcuiDirection): Promise<XcuiSpeech> {
    return this.#speech(await this.#request({ command: "move", direction }));
  }

  /**
   * What VoiceOver says for the element under the VoiceOver cursor.
   */
  async speech(): Promise<XcuiSpeech> {
    return this.#speech(await this.#request({ command: "speech" }));
  }

  /**
   * Shut the agent down. VoiceOver keeps running.
   */
  async stop(): Promise<void> {
    const exited =
      this.#child.exitCode === null && this.#child.signalCode === null
        ? new Promise((done) => this.#child.once("exit", done))
        : Promise.resolve();

    try {
      await this.#request({ command: "shutdown" });
    } catch (error) {
      debug("shutdown request failed", error);
    }

    const timer = setTimeout(() => this.#child.kill(), STOP_TIMEOUT);

    await exited;
    clearTimeout(timer);
    this.#socket.destroy();
    this.#server.close();
  }

  #speech(response: Record<string, unknown>): XcuiSpeech {
    return {
      utterance: response.utterance as string,
      truncated: response.truncated as boolean,
    };
  }

  #request(message: object): Promise<Record<string, unknown>> {
    // The agent handles one request at a time, in order.
    const request = this.#queue.then(
      () =>
        new Promise<Record<string, unknown>>((done, fail) => {
          this.#pending.push({
            resolve: (response) =>
              response.ok
                ? done(response)
                : fail(
                    new Error(
                      `XCUI agent: ${response.error} (code ${response.code})`,
                    ),
                  ),
            reject: fail,
          });
          this.#socket.write(`${JSON.stringify(message)}\n`);
        }),
    );

    this.#queue = request.catch(() => undefined);

    return request;
  }
}
