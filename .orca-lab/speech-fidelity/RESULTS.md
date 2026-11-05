# Results log

## 1. Does STOP reach a module after END? (speechd 0.12.1 source, src/server)

**No, except in a race window.**
- `is_sb_speaking()` (speaking.c:706-793): on the module's `end` mark, `SPEAKING = 0`,
  and at the bottom `if (SPEAKING == 0) speaking_module = NULL`.
- `output_stop()` (output.c:919-948): `if (speaking_module == NULL) OL_RET(0)`: no `STOP` sent.
- `speaking_stop(uid)` (speaking.c:430): only acts `if (get_speaking_client_uid() == uid)`, which is 0 when not SPEAKING.
- Client CANCEL → `speaking_cancel` → `speaking_stop` (no-op when idle) + `stop_from_uid` (drops QUEUED messages).

So with guidepup's module (`701 BEGIN`/`702 END` straight after `SPEAK`), speechd never thinks anything is in
flight, and an interrupt can only discard messages still waiting in speechd's queue. The `stop`/`cancel`
messages the module broadcasts can only appear in the window between SPEAK and speechd processing END.
To be confirmed live in step 5 (timestamped module log).

## 2. Orca 51.1 built-in test recording + who interrupts whom (source)

**Orca already has a test-output recorder for speech AND braille, with interrupt markers.**
- `output_recorder.py`: line-buffered JSONL. Testing D-Bus commands (registered only when Orca is launched
  with `ORCA_TEST_RPC_SECRET`; secret is the first arg):
  - `SpeechPresenter.SetLogFileForTesting(token, path)` → `{"kind":"speech","text",language,dialect,voice_type}`
    per utterance, plus `{"kind":"interrupt"}` from `PresentationManager.interrupt_presentation()`
    (`speech_presenter.record_interrupt`, "so output observers can drop speech that was interrupted").
  - `BraillePresenter.SetLogFileForTesting(token, path)` → `{"kind":"braille",cursor_cell,full,visible,mask}`
    from `update_monitor()` (called for every braille refresh, even without a device or monitor).
- `output_reader.py` (Orca's own test reader): `_honor_interrupts` drops ALL speech preceding the last
  interrupt marker in a drain. That is the pessimistic model: interrupted speech counts as never heard.
  Reality sits between "all heard" (guidepup today) and "none heard" (Orca's reader); it depends on timing.

**Who interrupts on Orca (prediction from source, to verify live):**
- Orca opens its speechd client with `Priority.MESSAGE` for everything (speechdispatcherfactory.py:145).
  speechd `resolve_priorities(SPD_MESSAGE)` only stops in-flight speech if the current one is TEXT/NOTIFICATION/PROGRESS,
  so MESSAGE never cuts MESSAGE (speaking.c:996-1003). Orca's speech is never cut by speechd's own priority rules.
- The only cut is Orca's explicit `interrupt_presentation()` → `interrupt_speech()` → `server.stop()` → `_cancel()`
  (32 call sites: focus changes, navigation commands, object presentation...). It also kills braille flash
  messages and flushes the live region queue.
- Live region messages go through `present_message` → `speak_message`: **no interrupt**. ASSERTIVE only jumps
  Orca's own live-region queue and purges queued POLITE messages (live_region_presenter.py:312).
- **Prediction:** on Orca, an assertive live region does NOT cut the current utterance; it is heard after it.
  The reverse is what loses speech: a focus change/navigation cuts in-flight speech AND drops queued live
  region messages. (Behavior of NVDA/JAWS/VoiceOver differs and isn't covered here.)

## 3. Lab build (2026-11-01)

- Worktree `~/projects/guidepup-wt/speech-fidelity` = upstream main `a7c5839` (0.40.0), detached. Lab files in its
  `.orca-lab/` and `examples/playwright-orca/tests/lab/` (both excluded from git).
- Image `guidepup-orca:26.04-audio` (`image/Dockerfile`): base lab image + espeak-ng CLI, brltty 6.7, python venv/pip, sox, ffmpeg, liblouis-bin.
- Runner `.orca-lab/sf.sh <label> [filter]` (env MODE=asset|instant|timed|audio, RATE, INI_EXTRA, BRLTTY=1, REPEAT).
  Assets installed to `.orca-lab/sr` via GUIDEPUP_SCREEN_READERS_PATH; the shared cache asset is never modified. Container pinned to CPUs 0-7.
- **Timed speech module** `.orca-lab/modules/guidepup-timed.py` (replaces `speechd/modules/guidepup` in the lab copy):
  same guidepup socket protocol, synthesises with libespeak-ng via ctypes (same rate mapping as sd_espeak-ng),
  holds `END` for the real audio length (`audio` mode also plays it via pacat), and on `STOP` records which
  words had played (espeak-ng WORD events). Timeline JSONL per run.
- Orca's built-in test logs enabled per test with `ORCA_TEST_RPC_SECRET` + `gdbus call ... SetLogFileForTesting`
  (guidepup reuses the worker's session bus, so `DBUS_SESSION_BUS_ADDRESS` works). A 10 ms tailer stamps each record.
- **Braille display:** brltty Virtual driver (`-b vr -d client:<sock>`) + `vr-display.py` (40 cells), started before Orca,
  BrlAPI `auth=none`. Logs every `Visual` (text window) and `Braille` (dots) change with timestamps.
- Views: `tl.py` (speech timeline), `view.py <out/label>` (all four channels merged).

### Side findings while building
- **guidepup's speech rate setting is ignored on Orca 51.1.** `guidepup.ini` sets `[voice] rate=100`; Orca 51 reads
  voice settings from `voice-sets/<set>/<voice-type>/` (`gsettings_registry.voice_set_sub_path`). speechd received
  `rate=0` (Orca's default 50 → espeak 170 wpm). Writing `[voice-sets/primary/default] rate=100` gives speechd `rate=100` (449 wpm).
  No effect on today's captures (the asset module takes no time), but it matters as soon as speech has duration.
- **Typed-character echo never reaches guidepup.** Orca speaks typed letters with `client.char()` → speechd sends the module
  `CHAR` + data block. The asset module has no `CHAR`/`KEY`/`SOUND_ICON` branch (falls through to `200 OK` without reading
  the data). (Key names like "tab"/"space" come as SPEAK and do arrive.) To verify against the asset module directly.
- Orca renames its process (`orca`) and its `/proc/<pid>/environ` is clobbered, so don't look for it that way.

## 4. Interruption matrix (MODE=timed, key echo off unless noted, WM=0, 1 run each so far)

guidepup's capture = every SPEAK text (the module forwards each SPEAK to the socket), i.e. always the full text.

| Scenario | rate 50 (170 wpm): heard | rate 100 (449 wpm): heard |
|---|---|---|
| S1 assertive LR 300 ms into 15-word focus announcement | both in full; LR queued, spoken at ~5.0 s | both in full; LR at ~2.1 s |
| S2 polite, same | same as S1 | same |
| S3 Tab 600 ms into 17-word assertive LR | LR cut: "Your order" + "has"…; then "Next button" | "Your order has" + "placed"… |
| S4 3 Tabs 400 ms apart, long buttons | 1st: "Apply"+"the"; 2nd: "Review"+"the"; 3rd in full | "Apply the"; "Review the shipping"; 3rd in full |
| S5 two long assertive updates 300 ms apart | both in full, queued | same |
| S6 Enter → assertive LR | in full | in full |
| S7 type "hello world" (key echo on) | each echo cut 0-8 ms in by the next key (guidepup types at ~2.5 ms/key); only final "d" heard | same |

- **Prediction from source confirmed: on Orca a live region never cuts speech; navigation/focus does.** Assertive only reorders Orca's own LR queue.
- Orca's test log marks every cut with `{"kind":"interrupt"}`; Orca's own reader would drop all speech before the last marker (pessimistic).
- Under WM=0 each key arrives 3x (at-spi2-core no-focus bug, fixed in at-spi2-core main, unreleased), so each key echo is spoken 3x and each cuts the previous.

## 5. Braille, first look (BRLTTY=1, 40-cell virtual display)

`view.py out/brl1`:
- S1: the display flashes the live region at **408 ms** while speech is still on the button name; speech reaches the LR at
  **5061 ms**. The flash reverts after ~5 s. Braille and speech users get the update ~4.6 s apart.
- S3: the Tab kills the LR flash after ~500 ms (`interrupt_presentation(kill_flash=True)`), display → "Start button" → "Next button".
- S6: LR flash for ~5 s, then "Place order button".
- Orca's braille test log (`orca-braille.jsonl`) matches the display's text window 1:1 (with a device it uses the device's 40 cells;
  without one, the 32-cell monitor size), but carries no timing and no dots.

## 6. Repeats + estimating "heard" from Orca's own log (no timed module)

Runs `rep-r50`, `rep-r100` (timed, 5x S1-S6, BRLTTY=1) and `rep-asset` (asset module, 5x, BRLTTY=1): 90/90 tests passed.
Orca's speech/interrupt sequence was identical across asset/timed and across all repeats.

`estimate.py`: replays Orca's timestamped test log (speech + interrupt markers, 10 ms tailer) through a model of
speechd's queue (MESSAGE never interrupts MESSAGE; Orca's cancel cuts the current utterance and drops the queue),
with durations + word timings from libespeak-ng at the run's rate. Compared with the timed module's ground truth:

| run | utterances | outcome (full/cut/dropped) match | heard-words match | mean cut-time error |
|---|---|---|---|---|
| rep-r50 (170 wpm), espeak durations | 60 | 60/60 | 60/60 | 5.2 ms |
| rep-r100 (449 wpm), espeak durations | 60 | 60/60 | 58/60 (2 word-boundary ties ≤7 ms) | 4.4 ms |
| rep-r50, chars heuristic (18.5 chars/s @170 wpm) | 60 | 60/60 | n/a (no word timings) | 5.2 ms |
| rep-r100, chars heuristic | 60 | 60/60 | n/a | 4.4 ms |

On `rep-asset` (stock module) the estimates give the same per-utterance distribution as the timed truth in all 30 tests
(e.g. S3: "Your order" 5/5; S4: "Apply" 5/5, "Review" 5/5, 3rd full 5/5).

**So guidepup can report interrupted speech without changing speech timing or test speed:** watch Orca's speech test log
(interrupt markers) and estimate durations with espeak-ng (an Orca dependency, already installed) or a chars/s heuristic.
Caveats: needs Orca's testing commands (`ORCA_TEST_RPC_SECRET`, test-only API); espeak-ng en-us durations only; the
"heard" figure is for a user acting at the test's own pace (a test that tabs every 400 ms cuts speech a slower user would hear).

## 7. Real audio (MODE=audio)

- PulseAudio in the container (`module-null-sink` 22050 Hz mono), the module plays each utterance with `pacat`,
  `parecord` records the sink monitor to `session.wav` (16 kHz). Works; 12/12 tests passed (`out/audio1`, 2.4 min).
- Bug found + fixed in the lab module: a STOP during pacat's drain made the module send `702 END` after `703 STOP`
  (speechd: "unexpected event 702 END"), and STOP couldn't kill a pacat blocked on a write. Outcome is now claimed once
  under a lock; STOP kills the player directly; PCM is fed by a separate thread.
- Recording lag vs module clock: constant ~240-250 ms, no drift over 140 s. In clean cases a cut reaches the sink
  ~65 ms after STOP and a full utterance drains ~30-50 ms after END. Per-utterance alignment on the mixed recording is
  noisy where utterances are back to back, so for ASR the module now also saves **what played of each utterance**
  (`CLIPS=1` → `out/<label>/played/*.wav`, the synthesized PCM cut at the heard point).

## 8. Braille, continued

- **Contracted braille is impossible with the guidepup Orca asset.** Its `orca_platform.py` has `tablesdir = ""`
  (built without liblouis), and `braille.py` then sets `LOUIS = None`, so `contracted-braille=true` silently falls back to
  computer braille. Patching the lab copy to `/usr/share/liblouis/tables` gives real UEB grade 2 on the display
  (`out/brl-g2`): `,apply ! tw5ty p}c5t s1sonal 4c.t to e i` (40 cells now reach "every i" vs "discou" uncontracted),
  live region flash `,sav$4 ,yr *anges 7 /or$4`. liblouis back-translation of the cells recovers the text.
- So a braille assertion layer has three possible sources, in increasing fidelity: Orca's braille test log (text window,
  32 cells without a device, no timing), the vr display's `Visual` line (device-sized window, timestamps), the vr display's
  `Braille` dots + liblouis back-translation (what a contracted-braille reader actually feels).
- Flash messages: default `flash-message-duration=5000`; the LR flash in S1/S6 lasted ~5.0 s, in S3 the Tab killed it at ~0.5 s.

## 9. Durations vs the real speechd → sd_espeak-ng → PulseAudio pipeline

The estimator and the timed module share libespeak-ng, so their agreement proves the queue model, not the durations.
`sd-durations.sh`: standalone speech-dispatcher 0.12.1 with the real `sd_espeak-ng`, `AudioOutputMethod "pulse"`,
punctuation "most", `spd-say -w -r {0,100}`, recorded from the null sink; sounding length (first→last loud 10 ms frame)
vs the module's synthesis of the same text:

| rate | phrase | real ms | module ms | diff |
|---|---|---|---|---|
| 0 | Apply the twenty percent … button (15 words) | 5120 | 5050 | −1.4% |
| 100 | same | 2050 | 2110 | +2.9% |
| 0 | Saved. Your changes were stored. | 2160 | 2070 | −4.2% |
| 100 | same | 800 | 770 | −3.8% |
| 0 | Your order has been placed … now (17 words) | 4540 | 4540 | 0.0% |
| 100 | same | 1830 | 1900 | +3.8% |
| 0 | Start button | 790 | 800 | +1.3% |
| 100 | same | 290 | 260 | −10.3% (30 ms) |
| 0 | Review the shipping … button | 4250 | 4170 | −1.9% |
| 100 | same | 1770 | 1800 | +1.7% |

Within ±4.2% for sentences, ≤30 ms for short phrases. The timed module is a faithful stand-in for Orca + sd_espeak-ng timing.

Module fix: on a STOP that crosses our END the module replied `703 STOP` while idle (inherited from the asset module), which
speechd logs as "unexpected event 703 STOP" (3 times in ~40 sessions). Now silent when idle, like sd_espeak-ng.

## 10. Upstream's own specs with speech that takes time

Copies of `examples/playwright-orca/tests/firefox/{firefox,firefox-keyboard}.spec.ts` in `tests/labup/` with a fixture
that only adds the Orca logs + timeline markers (`tests/lab/upfixture.ts`); specs unchanged otherwise.

| run | firefox.spec (docs site) | firefox-keyboard.spec (3 tests) |
|---|---|---|
| asset module (today) | pass | 3/3 |
| timed, rate 50 (= guidepup's effective rate, 170 wpm) | **fail 4/4** | 3/3 |
| timed, rate 100 (449 wpm) | pass | 3/3 |

**Why it fails:** Orca speaks the docs-site paragraph as two utterances, `"Run with Jest, with Playwright, as an "` and
`"paragraph"`. With the stock module both arrive within a millisecond and land in one capture, which the snapshot expects
as `"Run with Jest, with Playwright, as an. paragraph"`. With real-time speech, speechd holds `"paragraph"` until the
first utterance finishes (2.3 s at 170 wpm), after guidepup's capture has gone quiet and closed. So **guidepup's capture
windows silently rely on speech taking no time**; with realistic delivery the same Orca output is split across captures.
That's the 4th layer (delivery timing), separate from what's heard.

**How much of what guidepup records is heard, at the tests' own pace** (`estimate.py` over Orca's log, 170 wpm, stock module):

| test | utterances | heard in full | cut | dropped from queue |
|---|---|---|---|---|
| docs site (headings, then `navigateNextUntil`) | 28 | 10 | 5 (e.g. "Reliable" of "Reliable Automation For Your Screen…") | 13 |
| Tab → Enter → live region | 5 | 2 | 2 (startup: title, "main content") | 1 |
| Shift+Tab | 4 | 1 | 2 (startup) | 1 |
| type into a field | 20 | 2 | 17 (key echo ×3, typed letters) | 1 |

The docs-site test asserts on phrases a listener at that pace would mostly never hear. That's expected for a fast
automated test, but it's the gap cmorten described: the snapshot says nothing about whether the content was
announced in a way a user could take in.

Precise mechanism: `OrcaClient.ts:45` `SPEECH_DEBOUNCE_TIMEOUT = 1_000` closes a capture after 1 s with no new speech on
the socket. At 170 wpm the first utterance plays 2.3 s (> 1 s, so split, fail); at 449 wpm about 0.9 s (< 1 s, so joined, pass).
Any utterance longer than ~1 s followed by a queued one would split the same way.


## 11. CPU speech recognition as a "was it heard?" check (benchmark, `asr/REPORT.md`)

17 CPU models, 4 threads on CPUs 12-15, on 2028 synthetic clips (espeak-ng 175/300/450 wpm + Piper, cut at word
boundaries and mid-word, cut times from MMS_FA forced alignment) and the 426 real Orca clips
(`out/real-corpus-manifest.jsonl`). Rows: `asr/results.csv`; per-model tables: `asr/tables*.md`.

- **The "it completes the sentence" fear is unfounded:** 0/284 real cut clips and 0% of synthetic cuts got two or more
  words from the unplayed rest, for every model. Whisper's failure mode is looping or unrelated text at fast rates,
  not finishing the sentence.
- **Rate decides it.** Real Orca, 170 wpm, with the rule "flag cut only when 2+ expected tokens are missing":
  Parakeet-TDT-0.6b-v2, faster-whisper small.en and distil-small.en all give 0/75 false alarms and 87/87 cuts caught.
  At 449 wpm, 48-52 of 65 complete utterances are flagged as cut: unusable.
- Near-empty cuts (≤80 ms, 209 real clips) come back as fillers ("You", "Yeah.", "Um"); a checker must read one filler
  token as "nothing heard". The last word can't be placed better than ±1 (half-played words get completed 7-25%).
  Single letters are unreliable ("c" → "See").
- Pick: **Parakeet-TDT-0.6b-v2 int8 via onnx-asr** (CC-BY-4.0 weights, download at run time; RTF 0.38, 0.54 s/clip,
  1.2 GB RSS, deterministic, silent on silence/noise 24/24). MIT runner-up: faster-whisper small.en (4× slower, says
  "You" on silence).
- Spot-check by me: Parakeet real full 170 wpm SPEAK = 72/75 recounted from `results.csv` (k_sim == n). Matches.

## 12. Follow-up: score the KNOWN text against the audio (prefix CTC), instead of transcribing

The ASR report's suggested next step. `asr/scripts/prefix_ctc.py`: MMS_FA emissions (wav2vec2 CTC, characters), then
`loss(j) = -log P(chars of w1..wj | audio)` for every prefix j = 0..n, k̂ = argmin. `asr/scripts/prefix_eval.py` also
fits a per-char / per-word bias on the synthetic corpus only and applies it unchanged to the real one
(`asr/tables_prefix.md`). 0.42 s median per clip on 4 threads.

| real Orca clips | unbiased: exact / beyond k+1 / flags cut | bias fitted on synthetic: exact / beyond k+1 / flags cut |
|---|---|---|
| full, 170 wpm (75) | 61% / - / **39%** false alarm (4% with 1-word slack) | 96% / - / 4% (0% slack) |
| full, 449 wpm (65) | 0% / - / 100% false alarm (97% slack) | 31% / - / 69% (20% slack) |
| cut >80 ms, 170 wpm (40) | 80% / 0% / 100% | 22% / **78%** / 92% |
| cut >80 ms, 449 wpm (35) | 60% / 0% / 100% | 77% / 14% / 86% |
| cut ≤80 ms (151) | ~99% / 0% / 100% | 57-73% / 27-43% / 22-33% |

**Negative result: no single setting works.** Unbiased, it never overshoots and catches every cut, but complete
utterances lose their last word ("Start button" → the model hears "sarma"; MMS_FA is weak on espeak-ng), so 39% false
alarms at 170 wpm. A bias fixes that on synthetic clips but overshoots real ones: 27 of the 40 real 170 wpm cuts are
3-word utterances cut ~100 ms in, and an unplayed word squeezed into the 300 ms of padded silence costs only ~1.5
nats/char, under the fitted 3.25/char bonus. Synthetic cut clips mostly leave 1-3 words unplayed after real speech, so
the bias didn't transfer. At 449 wpm the fitted version is better than any ASR model (20% vs 74-80% false alarms with
slack) but still not usable.

Not tried (ideas): gate alignment on voiced frames (unplayed chars may not sit in post-speech silence), use a
character model trained on synthetic voices, or per-clip calibration from the uncut utterance's own audio (guidepup
could synthesise the full text with the same voice where it owns the voice, i.e. Orca, which already has better options).
