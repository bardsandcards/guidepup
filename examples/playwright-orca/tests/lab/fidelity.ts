// Lab helpers (untracked, bardsandcards/guidepup#21): Orca's own test output
// logs, a timeline marker per test, and waiting for timed speech to finish.
import { execFileSync } from "node:child_process";
import { appendFileSync, closeSync, existsSync, mkdirSync, openSync, readFileSync, readSync, statSync } from "node:fs";
import { delay } from "../../../../src/delay";
import type { Orca } from "../../../../src";
import type { TestInfo } from "@playwright/test";

const OUT = process.env.LAB_OUT ?? "/tmp/lab-out";
const TIMELINE = process.env.GP_TIMELINE;
const SECRET = process.env.ORCA_TEST_RPC_SECRET ?? "lab";

// guidepup uses the session bus from DBUS_SESSION_BUS_ADDRESS when there is
// one (dbus-run-session here), so Orca is on the same bus as this worker.
function orcaBusAddress(): string {
  const address = process.env.DBUS_SESSION_BUS_ADDRESS;
  if (!address) throw new Error("No DBUS_SESSION_BUS_ADDRESS");
  return address;
}

function setOrcaTestLog(module: "SpeechPresenter" | "BraillePresenter", path: string) {
  execFileSync("gdbus", [
    "call", "--address", orcaBusAddress(), "-d", "org.gnome.Orca1.Service",
    "-o", `/org/gnome/Orca1/Service/${module}`,
    "-m", `org.gnome.Orca1.${module}.SetLogFileForTesting`, `'${SECRET}'`, `'${path}'`,
  ]);
}

function timelineEvents(): { ev: string }[] {
  if (!TIMELINE || !existsSync(TIMELINE)) return [];
  return readFileSync(TIMELINE, "utf8").trim().split("\n").filter(Boolean).map((l) => JSON.parse(l));
}

/** Waits until the timed module has nothing playing and nothing new for quietMs. */
export async function settle(quietMs = 800, timeoutMs = 30000) {
  if (process.env.MODE === "asset") return delay(2000);
  const deadline = Date.now() + timeoutMs;
  let last = -1;
  let quietSince = Date.now();
  while (Date.now() < deadline) {
    const events = timelineEvents();
    const begins = events.filter((e) => e.ev === "begin").length;
    const done = events.filter((e) => e.ev === "end" || e.ev === "cut").length;
    if (events.length !== last) {
      last = events.length;
      quietSince = Date.now();
    } else if (begins === done && Date.now() - quietSince >= quietMs) {
      return;
    }
    await delay(50);
  }
}

// Orca's test logs carry no timestamps; poll them every 10ms and stamp new lines.
let tailer: ReturnType<typeof setInterval> | undefined;
function startTailer(dir: string) {
  const offsets: Record<string, number> = {};
  const files = ["orca-speech.jsonl", "orca-braille.jsonl"];
  tailer = setInterval(() => {
    for (const f of files) {
      const p = `${dir}/${f}`;
      if (!existsSync(p)) continue;
      const size = statSync(p).size;
      const from = offsets[f] ?? 0;
      if (size <= from) continue;
      const fd = openSync(p, "r");
      const buf = Buffer.alloc(size - from);
      readSync(fd, buf, 0, buf.length, from);
      closeSync(fd);
      const text = buf.toString("utf8");
      const end = text.lastIndexOf("\n") + 1;
      offsets[f] = from + Buffer.byteLength(text.slice(0, end));
      const wall = Date.now();
      for (const line of text.slice(0, end).split("\n").filter(Boolean)) {
        appendFileSync(`${dir}/orca-timed.jsonl`, JSON.stringify({ wall, log: f.slice(5, -6), ...JSON.parse(line) }) + "\n");
      }
    }
  }, 10);
}

export function slug(info: TestInfo) {
  const scenario = info.title.match(/^S\d+/)?.[0];
  const base = scenario ?? info.title.replace(/[^A-Za-z0-9]+/g, "-").slice(0, 48);
  return `${base}-r${info.repeatEachIndex}`;
}

export async function begin(info: TestInfo, orca: Orca) {
  await settle();
  const dir = `${OUT}/${slug(info)}`;
  mkdirSync(dir, { recursive: true });
  setOrcaTestLog("SpeechPresenter", `${dir}/orca-speech.jsonl`);
  setOrcaTestLog("BraillePresenter", `${dir}/orca-braille.jsonl`);
  startTailer(dir);
  await orca.clearSpokenPhraseLog();
  if (TIMELINE) appendFileSync(TIMELINE, JSON.stringify({ wall: Date.now(), ev: "test", name: slug(info) }) + "\n");
}

export async function end(info: TestInfo, _orca: Orca) {
  await settle();
  const dir = `${OUT}/${slug(info)}`;
  await delay(50);
  clearInterval(tailer);
  setOrcaTestLog("SpeechPresenter", "");
  setOrcaTestLog("BraillePresenter", "");
  if (TIMELINE) appendFileSync(TIMELINE, JSON.stringify({ wall: Date.now(), ev: "test-end", name: slug(info) }) + "\n");
}

export const page = (title: string, body: string, script = "") => `<!doctype html>
<html lang="en"><head><title>${title}</title></head>
<body><main><h1>${title}</h1>${body}</main><script>${script}</script></body></html>`;
