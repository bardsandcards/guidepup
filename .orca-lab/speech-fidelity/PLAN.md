# Speech + braille fidelity lab (bardsandcards/guidepup#21)

Started 2026-11-01. Lab only; not for merge.

Goal: capture what a user actually hears (voice) and reads (braille) on Orca,
not just what Orca sends. Then judge whether a small CPU ASR model can serve as
a cross-check (most useful on VoiceOver/NVDA).

## Two loss layers (keep separate)

- L1: Orca drops/flushes queued messages before they reach speechd
  (known: focus change → interrupt_presentation → live_region flush). The text
  log is CORRECT here: nothing was sent.
- L2: the speech engine cuts in-flight audio (STOP/CANCEL mid-utterance). The
  text log OVERSTATES here: guidepup's module reports END instantly, so nothing
  is ever in flight.

## Steps

1. speechd source: does STOP reach a module that has reported END?
2. Orca 51.1 source: `_record_speech` / `set_log_file_for_testing` / braille analogue.
3. Image tag `guidepup-orca:26.04-audio` (espeak-ng CLI, brltty, venv/pip, sox, ffmpeg).
4. Ground truth: real sd_espeak-ng → pulse null sink → parecord monitor.
5. Timed guidepup module: synthesize, play, hold END, on STOP emit `cut` with heard prefix.
6. Scenarios (synthetic pages): long focus + assertive LR; polite LR; 2× assertive;
   focus change during LR; typing echo. Measure both directions.
7. ASR benchmark on host (CPU primary): truncation-alignment metric, RTF, size,
   silence hallucination, determinism.
8. Braille: brltty before Orca, driver-level capture, flash messages, liblouis back-translation.

Results: RESULTS.md (append after each step).
