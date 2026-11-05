# CPU ASR for screen-reader speech: can it tell what the user heard?

Status: complete except where noted (written incrementally overnight 2026-11-01; CPU only, no GPU column).

## Question

guidepup records the text a screen reader *sends* to speech. On VoiceOver/NVDA only audio is
available, so the question is whether a small CPU speech recogniser can transcribe screen-reader
audio well enough to say what a user actually heard, and above all whether an utterance was
**cut off partway**.

Hypothesis stated before any model ran: autoregressive decoders (Whisper, Moonshine, Canary)
can "finish the sentence" from context, i.e. hallucinate the missing tail of a truncated clip;
frame-synchronous models (Parakeet TDT, zipformer transducers, Kaldi/Vosk) structurally should
not, because every emitted token is tied to frames that exist.

## Method

### Corpus

- Phrases: 84 (15 from the brief, 34 more of the same shape written for this run: roles,
  states, landmarks, headings with levels, counts, punctuation names, key echo; 35 unique
  strings taken verbatim from guidepup `examples/**/*spokenPhrase*.snapshot.json` on
  upstream-main d36297c). List: `phrases.json`, source `scripts/phrases.py`.
- TTS text: the screen-reader string with digits spelled out the way espeak-ng 1.52 reads them
  (checked with `espeak-ng -x`: "123" -> "one hundred twenty three", "$42.50" -> "dollar forty
  two point five zero", "A11y" -> "A eleven y", "Abc" -> "A B C"). Punctuation is kept so the
  TTS keeps its pauses. Both TTSes get the same text.
- Voices: espeak-ng 1.52 en-us at 175 (Orca default), 300 and 450 wpm (docker image
  `guidepup-orca:26.04-audio`); Piper `en_US-lessac-medium` (rhasspy/piper-voices) at default
  rate as the "nicer neural voice" stand-in.
- All audio resampled to 16 kHz mono, leading/trailing TTS silence trimmed (-50 dBFS, 10 ms
  frames), 300 ms of digital silence padded on each side.

### Token space (decided before building clips)

Every reference and every hypothesis goes through one normaliser (`scripts/textnorm.py`):
openai-whisper's `EnglishTextNormalizer` (lowercase, strip punctuation, spelled numbers to
digits, "second" -> "2nd"), applied per punctuation-separated piece so "level two. twenty four"
doesn't merge into "224", plus five compound aliases ("git hub"/"github", "a b c"/"abc",
"a p i"/"api", "a 11 y"/"a11y", "guide pup"/"guidepup"), model-written currency
("$42.50", "Subtotal$42.50") -> "dollar 42.50" (espeak reads "$42.50" as "dollar forty two
point five zero"; references never contain "$") and lone "1" -> "one".

k, k-hat, n and cut times are all in these canonical tokens. Canonical token boundaries are
mapped to spoken (aligned) words by prefix normalisation: boundary j is cuttable if some spoken
prefix normalises to exactly the first j canonical tokens; its time comes from the last such
spoken word.

### Word timing

Primary: forced alignment of the spoken words with torchaudio 2.8 `MMS_FA` (wav2vec2 CTC,
20 ms frames) on the padded full utterance (`scripts/align.py`, `scripts/align_corpus.py`).
The cut for "after token k" is the **midpoint of the gap** between the aligned end of the last
spoken word of token k and the aligned start of the next spoken word (at 450 wpm the gap is
usually 0 frames, so the cut is the shared boundary).

Cross-check (`corpus/prefix_check.json`): every chunk-boundary prefix of the 49 brief/extra
phrases was synthesised alone, trimmed the same way, and its duration compared with the cut
time. A prefix spoken alone gets phrase-final lengthening and a final fall, so it should run
somewhat *longer* than the same words inside the sentence.

| voice | prefixes | median (prefix-TTS end - cut) ms | IQR ms | within ±100 ms | median inter-word gap ms |
|---|---|---|---|---|---|
| espeak175 | 148 | +86 | +68 / +116 | 56% | 60 |
| espeak450 | 148 | +24 | +8 / +35 | 97% | 0 |
| piper | 148 | +93 | +27 / +156 | 50% | 61 |

The offsets are positive and small at 450 wpm (+24 ms median) and around +90 ms at the slower
voices, consistent with phrase-final lengthening rather than misalignment. The large
negatives (to -420 ms) are all cuts inside sentence pauses ("Name. entry..", "dialog. Confirm"),
where the gap midpoint sits in the middle of a long silence: harmless for a cut. The large
positives (to +860 ms) are Piper prefixes that Piper itself rendered with different durations
(VITS durations depend on the whole input; e.g. "Sort by. combo box. Price, low to high" came
out 300-500 ms longer alone).

Second, independent check for the espeak voices (`scripts/espeak_events.py`, run inside the
image through ctypes on `libespeak-ng.so.1`; `scripts/check_events.py`): espeak-ng's own
`espeakEVENT_WORD` callbacks give the synthesiser's word-start positions. For every trunc
clip, the cut was compared with espeak's start of the next word:

| voice | trunc clips | aligner next-word start minus espeak word event, median ms | cut minus espeak next-word start, median ms | 10th / 90th pct ms | cut at most 20 ms past next-word start | cut more than 40 ms past |
|---|---|---|---|---|---|---|
| espeak175 | 205 | +39 | +9 | -76 / +36 | 70% | 8% |
| espeak300 | 205 | +26 | +11 | -24 / +36 | 72% | 8% |
| espeak450 | 205 | +10 | +4 | -19 / +29 | 81% | 4% |

So the CTC aligner places word starts 10-40 ms late, and the gap-midpoint cut sits on average
4-11 ms after espeak's own start of the next word. In 4-8% of clips the cut lets more than
40 ms of the next word's onset through (often a stop closure or burst rather than a vowel).
This biases toward k̂ = k+1 slightly, which is why "within 1" is reported and why tail
hallucination counts only hits beyond k+1. A sensitivity split (clean cuts only) is in the
results. Energy at the cut (20 ms window, dB relative to the utterance's loudest 20 ms frame)
shows these are connected-speech boundaries, not silences, except at punctuation pauses:

| voice | trunc clips | median dB re peak | below -30 dB | above -15 dB |
|---|---|---|---|---|
| espeak175 | 205 | -22 | 34% | 30% |
| espeak300 | 205 | -18 | 24% | 40% |
| espeak450 | 205 | -14 | 12% | 52% |
| piper | 205 | -19 | 35% | 40% |

### Clip types (`scripts/build_clips.py`, manifest `corpus/clips.jsonl`)

| type | what | count |
|---|---|---|
| full | whole utterance, 300 ms silence each side | 336 (84 phrases x 4 voices) |
| trunc | abrupt cut (no fade, like a speechd STOP) after canonical token k, + 300 ms silence; at most 6 evenly spaced k per phrase | 820 |
| mid | abrupt cut halfway through the first spoken word of token k+1 | 820 |
| silence / noise | 3 s digital zero, 3 s dither (-90 dBFS), 3 s white noise at -50 and -40 dBFS RMS | 4 |
| pair | two utterances back to back (TTS padding removed) with a 150 ms gap | 48 (12 pairs x 4 voices) |

Total 2028 clips, 51.3 min of audio. Some models ran only the `core` subset (728 clips: every
full clip, trunc/mid of the 15 brief phrases, silence/noise, 3 pairs per voice) because of CPU
time; the tables say which.

### Metrics (`scripts/score.py`, `scripts/summarize.py`)

Hypotheses are normalised with the same `textnorm.norm` as the references, then aligned to the
**full** reference with Levenshtein (sub = ins = del = 1), backtracking so repeated words align
as early as possible.

- WER: full clips, per voice.
- k̂ (strict) = 1 + position of the last reference token the model got **exactly right**.
  exact = k̂ == k, within 1 = |k̂ - k| <= 1, under = k̂ < k, over = k̂ > k.
- k̂ (lenient, "k_pos") = 1 + last reference position aligned to **any** hypothesis token (hit
  or substitution): how far into the known text the model got, even when it misheard words.
  Useful because the checker knows the expected text, but with sub = ins every junk token after
  the last hit aligns as a substitution of the next reference token, so junk counts as progress.
- **k̂ (sim), the headline variant**: like lenient, but a substitution counts only when the two
  tokens are character-similar (difflib ratio >= 0.5: "card"/"cart" counts, "video"/"42.50"
  does not).
- **Cut detected** = k̂ < n on a trunc clip (what a checker that knows the expected text would
  report); **false "cut"** = k̂ < n on a full clip. These two are the decision pair.
- **Tail hallucination** (brief's definition): an exact hit on a reference token beyond k+1.
  Reported for trunc and mid clips. It over-counts coincidences: unrelated junk such as "I'll see
  you next time" for "alert. Your..." hits "will" further on. So a stricter **tail completion**
  (at least 2 exact hits beyond k+1) is reported too.
- Junk after cut: any non-hit hypothesis token after the last hit.
- False "cut off" on full clips: k̂ < n on a complete utterance (strict and lenient).
- Mid-word: completed (token k+1 exactly right although only half was played) / guessed (some
  other token emitted for it) / dropped (nothing after token k).
- Silence/noise: any non-empty normalised output on the 4 silence/noise clips of the main
  corpus plus 20 more (`scripts/make_sil.py`: 1/3/5 s of zero, dither, white noise at -60/-50/-40
  dBFS and pink noise at -50 dBFS, two seeds for some), 24 clips per model.
- Pairs: both utterances have at least one exact hit; WER over the concatenation.
- Short utterances: exact transcript on full clips with n <= 2 tokens ("tab", "link", "A", ...).
- Word timestamps: on trunc clips, |end of the last emitted word - aligned end of word k|, median.
- RTF / latency / load / peak RSS: separate timing pass on 60 duration-stratified clips, one
  process at a time, 4 threads on 4 CPUs (12-15), after one discarded warm-up call. Load time
  is a cold process on a warm page cache.
- Determinism: 40 clips (full, trunc, mid, silence/noise, pairs) run 3 times in one process;
  identical text (and identical text + word times).

## Results

Tables are regenerated by `scripts/summarize.py` (also `summary.csv`). **Rows whose subset is
`turbo` (fw-large-v3-turbo, moonv-tiny-streaming, moonv-small-streaming) have WER over 60 full
clips (the 15 brief phrases) instead of 336: compare them with the others in the "Same 158
clips" table, not in the headline table.**

<!-- TABLES -->
### Headline (WER on all 336 full clips, except `turbo`-subset models: 60 full clips, see the same-clip table below; truncation with k̂_sim on the core trunc clips = 15 brief phrases x 4 voices, the same clips for every model except the models run on the `turbo` subset (fw-large-v3-turbo, moonv-*), whose trunc/mid clips are espeak175 only)

| model | subset (clips) | size MB | licence | RTF 4 thr | median latency s (clips <1.2 s) | load s | peak RSS MB | WER 175 | WER 300 | WER 450 | WER piper | trunc exact | trunc within 1 | cut detected (trunc k̂<n) | false 'cut' on full | tail halluc trunc / mid (any hit > k+1) | tail completion trunc / mid (≥2 hits > k+1) | silence+noise non-empty | determinism |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fw-tiny.en | all (2028) | 78 | MIT | 0.25 | 0.39 (0.38) | 0.5 | 286 | 47% | 141% | 239% | 15% | 49% | 71% | 100% | 40% | 0% / 0% | 0% / 0% | 3/24 | 40/40 text, 40/40 text+times x3; 40/40 vs main run |
| fw-base.en | all (2028) | 148 | MIT | 0.51 | 0.69 (0.67) | 0.6 | 402 | 33% | 73% | 325% | 15% | 60% | 82% | 99% | 33% | 0% / 0% | 0% / 0% | 19/24 | 40/40 text, 40/40 text+times x3; 40/40 vs main run |
| fw-small.en | core (728) | 486 | MIT | 1.36 | 2.10 (2.05) | 1.0 | 837 | 26% | 44% | 114% | 10% | 70% | 89% | 99% | 19% | 0% / 0% | 0% / 0% | 17/24 | 40/40 text, 40/40 text+times x3; 28/28 vs main run |
| fw-distil-small.en | core (728) | 336 | MIT | 1.26 | 1.83 (1.80) | 0.8 | 607 | 28% | 59% | 84% | 12% | 65% | 85% | 100% | 21% | 0% / 0% | 0% / 0% | 9/24 | 40/40 text, 40/40 text+times x3; 28/28 vs main run |
| fw-large-v3-turbo | turbo (158) | 1622 | MIT | 6.56 | 10.01 (9.96) | 2.4 | 2052 | 14% | 36% | 42% | 6% | 89% | 98% | 100% | 13% | 0% / 0% | 0% / 0% | 14/24 | - |
| wcpp-tiny.en-q5_1 | core (728) | 32 | MIT | 0.44 | 0.66 (0.65) | 0.3 | 163 | 49% | 120% | 104% | 18% | 49% | 73% | 99% | 44% | 0% / 0% | 0% / 0% | 0/24 | 40/40 text, 40/40 text+times x3; 28/28 vs main run |
| wcpp-base.en-q5_1 | core (728) | 60 | MIT | 1.00 | 1.55 (1.54) | 0.3 | 211 | 38% | 108% | 114% | 16% | 60% | 81% | 99% | 32% | 0% / 1% | 0% / 0% | 0/24 | 40/40 text, 40/40 text+times x3; 28/28 vs main run |
| moonshine-tiny | all (2028) | 109 | MIT | 0.07 | 0.10 (0.06) | 1.5 | 398 | 60% | 79% | 93% | 24% | 51% | 73% | 100% | 43% | 0% / 0% | 0% / 0% | 0/24 | 40/40 text, 40/40 text+times x3; 40/40 vs main run |
| moonshine-base | all (2028) | 247 | MIT | 0.12 | 0.15 (0.12) | 1.9 | 682 | 49% | 67% | 80% | 16% | 51% | 72% | 99% | 35% | 0% / 0% | 0% / 0% | 0/24 | 40/40 text, 40/40 text+times x3; 40/40 vs main run |
| moonv-tiny-streaming | turbo (158) | 78 | MIT (package README + HF card) | 1.95 | 2.74 (1.90) | 1.7 | 244 | 66% | 95% | 114% | 17% | 49% | 91% | 100% | 43% | 0% / 0% | 0% / 0% | 1/24 | 40/40 text, 40/40 text+times x3; 4/6 vs main run |
| moonv-small-streaming | turbo (158) | 142 | MIT (package README + HF card) | 3.74 | 5.56 (3.70) | 3.1 | 490 | 44% | 80% | 108% | 22% | 55% | 96% | 100% | 43% | 0% / 0% | 0% / 0% | 1/24 | 40/40 text, 40/40 text+times x3; 4/6 vs main run |
| parakeet-tdt-0.6b-v2 | all (2028) | 661 | CC-BY-4.0 | 0.38 | 0.54 (0.47) | 2.6 | 1204 | 17% | 43% | 69% | 10% | 69% | 87% | 99% | 21% | 1% / 0% | 0% / 0% | 0/24 | 40/40 text, 40/40 text+times x3; 40/40 vs main run |
| parakeet-tdt-0.6b-v3 | core (728) | 671 | CC-BY-4.0 | 0.40 | 0.60 (0.45) | 2.6 | 1198 | 21% | 43% | 86% | 15% | 64% | 86% | 99% | 26% | 0% / 0% | 0% / 0% | 2/24 | 40/40 text, 40/40 text+times x3; 28/28 vs main run |
| canary-180m-flash | core (728) | 213 | CC-BY-4.0 | 0.27 | 0.28 (0.23) | 1.0 | 528 | 72% | 89% | 99% | 21% | 31% | 57% | 100% | 57% | 0% / 0% | 0% / 0% | 0/24 | 40/40 text, 40/40 text+times x3; 28/28 vs main run |
| zipformer-en-2023-06-26 | all (2028) | 73 | Apache-2.0 | 0.26 | 0.34 (0.27) | 2.2 | 201 | 84% | 95% | 100% | 33% | 56% | 81% | 98% | 41% | 0% / 1% | 0% / 0% | 0/24 | 40/40 text, 40/40 text+times x3; 40/40 vs main run |
| vosk-small-en-us-0.15 | all (2028) | 71 | Apache-2.0 (alphacephei models page) | 0.10 | 0.10 (0.05) | 0.4 | 350 | 62% | 82% | 104% | 26% | 56% | 80% | 99% | 44% | 0% / 0% | 0% / 0% | 8/24 | 40/40 text, 40/40 text+times x3; 37/40 vs main run |
| vosk-en-us-0.22-lgraph | core (728) | 214 | Apache-2.0 (alphacephei models page) | 0.85 | 0.98 (0.59) | 0.9 | 738 | 65% | 88% | 99% | 21% | 45% | 67% | 100% | 47% | 0% / 0% | 0% / 0% | 18/24 | 40/40 text, 40/40 text+times x3; 25/28 vs main run |

### Truncation detail over every trunc/mid clip the model ran (all k̂ variants), mid-word, pairs, short clips, timestamps

| model | trunc clips | strict exact / w1 | lenient exact / w1 | sim exact / w1 | under / over (strict) | cut detected strict / lenient / sim | false 'cut' on full strict / lenient / sim | junk after cut | mid-word completed / guessed / dropped | pairs both heard | pair WER | short (n≤2) exact | last-word ts median abs err s | sim exact: clean / unclean espeak cuts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fw-tiny.en | 820 | 38% / 69% | 57% / 86% | 50% / 76% | 61% / 1% | 99% / 85% / 99% | 53% / 3% / 40% | 54% | 18% / 72% / 10% | 65% | 94% | 31% (136) | 0.067 | 36% / 38% (n=158) |
| fw-base.en | 820 | 43% / 73% | 57% / 82% | 57% / 81% | 56% / 1% | 99% / 81% / 99% | 41% / 5% / 33% | 55% | 26% / 69% / 6% | 73% | 58% | 49% (136) | 0.096 | 46% / 44% (n=158) |
| fw-small.en | 188 | 56% / 80% | 80% / 97% | 70% / 89% | 43% / 1% | 99% / 95% / 99% | 27% / 3% / 19% | 43% | 20% / 74% / 6% | 92% | 14% | 57% (136) | 0.046 | 63% / 62% (n=29) |
| fw-distil-small.en | 188 | 55% / 76% | 80% / 97% | 65% / 85% | 45% / 0% | 100% / 95% / 100% | 36% / 7% / 21% | 45% | 15% / 72% / 13% | 83% | 21% | 49% (136) | 0.044 | 61% / 45% (n=29) |
| fw-large-v3-turbo | 47 | 79% / 94% | 87% / 98% | 89% / 98% | 21% / 0% | 100% / 96% / 100% | 17% / 5% / 13% | 26% | 17% / 79% / 4% | - | - | 75% (12) | 0.048 | 89% / 89% (n=9) |
| wcpp-tiny.en-q5_1 | 188 | 39% / 63% | 54% / 84% | 49% / 73% | 61% / 1% | 99% / 94% / 99% | 55% / 23% / 44% | 39% | 11% / 62% / 27% | 67% | 49% | 30% (136) | 0.907 | 38% / 21% (n=29) |
| wcpp-base.en-q5_1 | 188 | 47% / 72% | 61% / 90% | 60% / 81% | 53% / 1% | 99% / 93% / 99% | 43% / 9% / 32% | 42% | 18% / 70% / 12% | 67% | 45% | 45% (136) | 0.435 | 54% / 41% (n=29) |
| moonshine-tiny | 820 | 39% / 69% | 54% / 82% | 50% / 75% | 60% / 0% | 100% / 94% / 100% | 59% / 23% / 43% | 33% | 11% / 57% / 31% | 67% | 56% | 27% (136) | - | 37% / 40% (n=158) |
| moonshine-base | 820 | 42% / 71% | 56% / 84% | 53% / 78% | 58% / 0% | 100% / 94% / 100% | 50% / 18% / 35% | 33% | 15% / 57% / 28% | 69% | 47% | 36% (136) | - | 39% / 48% (n=158) |
| moonv-tiny-streaming | 47 | 38% / 81% | 55% / 81% | 49% / 91% | 62% / 0% | 100% / 89% / 100% | 53% / 15% / 43% | 51% | 2% / 55% / 43% | - | - | 50% (12) | - | 45% / 67% (n=9) |
| moonv-small-streaming | 47 | 45% / 89% | 70% / 96% | 55% / 96% | 55% / 0% | 100% / 98% / 100% | 53% / 12% / 43% | 49% | 4% / 66% / 30% | - | - | 42% (12) | - | 50% / 78% (n=9) |
| parakeet-tdt-0.6b-v2 | 820 | 57% / 83% | 78% / 95% | 71% / 88% | 41% / 1% | 99% / 93% / 99% | 29% / 5% / 21% | 42% | 26% / 69% / 6% | 92% | 25% | 57% (136) | 0.136 | 64% / 66% (n=158) |
| parakeet-tdt-0.6b-v3 | 188 | 57% / 79% | 81% / 98% | 64% / 86% | 42% / 1% | 99% / 96% / 99% | 37% / 9% / 26% | 42% | 12% / 80% / 8% | 92% | 17% | 47% (136) | 0.143 | 55% / 62% (n=29) |
| canary-180m-flash | 188 | 24% / 52% | 32% / 61% | 31% / 57% | 76% / 0% | 100% / 97% / 100% | 63% / 51% / 57% | 18% | 12% / 30% / 59% | 42% | 63% | 29% (136) | - | 15% / 7% (n=29) |
| zipformer-en-2023-06-26 | 820 | 34% / 69% | 38% / 91% | 55% / 83% | 64% / 2% | 100% / 81% / 99% | 62% / 10% / 41% | 85% | 13% / 86% / 1% | 56% | 72% | 30% (136) | 0.384 | 45% / 47% (n=158) |
| vosk-small-en-us-0.15 | 820 | 42% / 72% | 75% / 95% | 57% / 80% | 57% / 0% | 100% / 95% / 100% | 57% / 11% / 44% | 55% | 7% / 84% / 8% | 62% | 61% | 29% (136) | 0.065 | 45% / 49% (n=158) |
| vosk-en-us-0.22-lgraph | 188 | 35% / 60% | 65% / 84% | 45% / 67% | 65% / 0% | 100% / 99% / 100% | 60% / 25% / 47% | 63% | 9% / 88% / 4% | 42% | 53% | 29% (136) | 0.057 | 29% / 31% (n=29) |

### Same 158 clips for every model (`turbo` subset: 15 brief phrases; full clips x 4 voices, trunc/mid at espeak175)

| model | WER 175 | WER 300 | WER 450 | WER piper | trunc exact (175) | within 1 | false 'cut' on full (all 4 voices) | tail completion |
|---|---|---|---|---|---|---|---|---|
| fw-tiny.en | 42% | 97% | 141% | 8% | 77% | 98% | 37% | 0% |
| fw-base.en | 36% | 59% | 127% | 9% | 74% | 96% | 32% | 0% |
| fw-small.en | 20% | 36% | 66% | 2% | 87% | 98% | 13% | 0% |
| fw-distil-small.en | 25% | 45% | 83% | 2% | 81% | 94% | 20% | 0% |
| fw-large-v3-turbo | 14% | 36% | 42% | 6% | 89% | 98% | 13% | 0% |
| wcpp-tiny.en-q5_1 | 33% | 86% | 106% | 12% | 72% | 96% | 42% | 0% |
| wcpp-base.en-q5_1 | 39% | 66% | 134% | 8% | 85% | 98% | 30% | 0% |
| moonshine-tiny | 44% | 78% | 92% | 14% | 64% | 85% | 37% | 0% |
| moonshine-base | 38% | 80% | 77% | 8% | 66% | 87% | 35% | 0% |
| moonv-tiny-streaming | 66% | 95% | 114% | 17% | 49% | 91% | 43% | 0% |
| moonv-small-streaming | 44% | 80% | 108% | 22% | 55% | 96% | 43% | 0% |
| parakeet-tdt-0.6b-v2 | 11% | 34% | 58% | 6% | 81% | 94% | 13% | 0% |
| parakeet-tdt-0.6b-v3 | 19% | 41% | 78% | 6% | 85% | 98% | 18% | 0% |
| canary-180m-flash | 73% | 91% | 97% | 25% | 34% | 66% | 58% | 0% |
| zipformer-en-2023-06-26 | 86% | 91% | 98% | 27% | 64% | 83% | 37% | 0% |
| vosk-small-en-us-0.15 | 48% | 77% | 105% | 12% | 77% | 94% | 30% | 0% |
| vosk-en-us-0.22-lgraph | 56% | 88% | 97% | 8% | 60% | 81% | 47% | 0% |

### Per voice (k̂_sim). len ratio = median normalised hyp tokens / ref tokens on full clips

| model | voice | WER | len ratio | trunc exact | within 1 | cut detected | false 'cut' on full | tail halluc trunc+mid |
|---|---|---|---|---|---|---|---|---|
| fw-tiny.en | espeak175 | 47% | 1.00 | 74% | 93% | 100% | 19% | 0% |
| fw-tiny.en | espeak300 | 141% | 1.24 | 28% | 65% | 98% | 44% | 0% |
| fw-tiny.en | espeak450 | 239% | 1.50 | 7% | 45% | 98% | 92% | 1% |
| fw-tiny.en | piper | 15% | 1.00 | 90% | 100% | 100% | 7% | 0% |
| fw-base.en | espeak175 | 33% | 1.00 | 75% | 95% | 100% | 13% | 0% |
| fw-base.en | espeak300 | 73% | 1.00 | 45% | 81% | 98% | 39% | 1% |
| fw-base.en | espeak450 | 325% | 1.37 | 18% | 50% | 98% | 71% | 0% |
| fw-base.en | piper | 15% | 1.00 | 89% | 98% | 99% | 8% | 0% |
| fw-small.en | espeak175 | 26% | 1.00 | 87% | 98% | 100% | 11% | 0% |
| fw-small.en | espeak300 | 44% | 1.00 | 57% | 85% | 100% | 23% | 0% |
| fw-small.en | espeak450 | 114% | 1.00 | 45% | 74% | 100% | 38% | 0% |
| fw-small.en | piper | 10% | 1.00 | 91% | 98% | 98% | 6% | 0% |
| fw-distil-small.en | espeak175 | 28% | 1.00 | 81% | 94% | 100% | 11% | 0% |
| fw-distil-small.en | espeak300 | 59% | 1.00 | 57% | 81% | 100% | 26% | 0% |
| fw-distil-small.en | espeak450 | 84% | 1.00 | 34% | 68% | 100% | 42% | 0% |
| fw-distil-small.en | piper | 12% | 1.00 | 89% | 98% | 100% | 6% | 0% |
| fw-large-v3-turbo | espeak175 | 14% | 1.00 | 89% | 98% | 100% | 7% | 0% |
| fw-large-v3-turbo | espeak300 | 36% | 1.00 | - | - | - | 20% | - |
| fw-large-v3-turbo | espeak450 | 42% | 1.00 | - | - | - | 27% | - |
| fw-large-v3-turbo | piper | 6% | 1.00 | - | - | - | 0% | - |
| wcpp-tiny.en-q5_1 | espeak175 | 49% | 1.00 | 72% | 96% | 100% | 20% | 0% |
| wcpp-tiny.en-q5_1 | espeak300 | 120% | 1.00 | 21% | 55% | 100% | 51% | 0% |
| wcpp-tiny.en-q5_1 | espeak450 | 104% | 0.67 | 11% | 43% | 100% | 94% | 0% |
| wcpp-tiny.en-q5_1 | piper | 18% | 1.00 | 91% | 98% | 98% | 12% | 0% |
| wcpp-base.en-q5_1 | espeak175 | 38% | 1.00 | 85% | 98% | 100% | 14% | 0% |
| wcpp-base.en-q5_1 | espeak300 | 108% | 1.00 | 53% | 83% | 100% | 38% | 0% |
| wcpp-base.en-q5_1 | espeak450 | 114% | 1.00 | 15% | 47% | 100% | 65% | 1% |
| wcpp-base.en-q5_1 | piper | 16% | 1.00 | 87% | 98% | 98% | 10% | 0% |
| moonshine-tiny | espeak175 | 60% | 1.00 | 60% | 82% | 100% | 36% | 0% |
| moonshine-tiny | espeak300 | 79% | 1.00 | 38% | 68% | 100% | 52% | 0% |
| moonshine-tiny | espeak450 | 93% | 1.00 | 15% | 51% | 100% | 75% | 0% |
| moonshine-tiny | piper | 24% | 1.00 | 88% | 99% | 100% | 7% | 0% |
| moonshine-base | espeak175 | 49% | 1.00 | 66% | 88% | 100% | 18% | 0% |
| moonshine-base | espeak300 | 67% | 1.00 | 42% | 72% | 100% | 44% | 0% |
| moonshine-base | espeak450 | 80% | 1.00 | 17% | 54% | 100% | 69% | 0% |
| moonshine-base | piper | 16% | 1.00 | 86% | 98% | 100% | 10% | 0% |
| moonv-tiny-streaming | espeak175 | 66% | 1.00 | 49% | 91% | 100% | 27% | 0% |
| moonv-tiny-streaming | espeak300 | 95% | 1.25 | - | - | - | 60% | - |
| moonv-tiny-streaming | espeak450 | 114% | 1.00 | - | - | - | 87% | - |
| moonv-tiny-streaming | piper | 17% | 1.20 | - | - | - | 0% | - |
| moonv-small-streaming | espeak175 | 44% | 1.17 | 55% | 96% | 100% | 33% | 0% |
| moonv-small-streaming | espeak300 | 80% | 1.25 | - | - | - | 53% | - |
| moonv-small-streaming | espeak450 | 108% | 1.20 | - | - | - | 87% | - |
| moonv-small-streaming | piper | 22% | 1.00 | - | - | - | 0% | - |
| parakeet-tdt-0.6b-v2 | espeak175 | 17% | 1.00 | 83% | 96% | 100% | 6% | 0% |
| parakeet-tdt-0.6b-v2 | espeak300 | 43% | 1.00 | 68% | 90% | 99% | 29% | 0% |
| parakeet-tdt-0.6b-v2 | espeak450 | 69% | 1.00 | 42% | 71% | 99% | 43% | 1% |
| parakeet-tdt-0.6b-v2 | piper | 10% | 1.00 | 92% | 98% | 98% | 7% | 1% |
| parakeet-tdt-0.6b-v3 | espeak175 | 21% | 1.00 | 85% | 98% | 100% | 14% | 0% |
| parakeet-tdt-0.6b-v3 | espeak300 | 43% | 1.00 | 60% | 81% | 98% | 21% | 0% |
| parakeet-tdt-0.6b-v3 | espeak450 | 86% | 1.00 | 26% | 68% | 98% | 61% | 0% |
| parakeet-tdt-0.6b-v3 | piper | 15% | 1.00 | 87% | 96% | 100% | 7% | 0% |
| canary-180m-flash | espeak175 | 72% | 1.00 | 34% | 66% | 100% | 42% | 0% |
| canary-180m-flash | espeak300 | 89% | 0.00 | 6% | 38% | 100% | 80% | 0% |
| canary-180m-flash | espeak450 | 99% | 0.00 | 0% | 30% | 100% | 96% | 0% |
| canary-180m-flash | piper | 21% | 1.00 | 85% | 96% | 100% | 12% | 0% |
| zipformer-en-2023-06-26 | espeak175 | 84% | 1.00 | 54% | 83% | 100% | 36% | 0% |
| zipformer-en-2023-06-26 | espeak300 | 95% | 1.06 | 43% | 80% | 99% | 51% | 1% |
| zipformer-en-2023-06-26 | espeak450 | 100% | 1.00 | 39% | 71% | 99% | 70% | 0% |
| zipformer-en-2023-06-26 | piper | 33% | 1.00 | 82% | 98% | 98% | 8% | 1% |
| vosk-small-en-us-0.15 | espeak175 | 62% | 1.00 | 67% | 91% | 100% | 33% | 0% |
| vosk-small-en-us-0.15 | espeak300 | 82% | 1.00 | 46% | 74% | 100% | 48% | 0% |
| vosk-small-en-us-0.15 | espeak450 | 104% | 1.00 | 25% | 55% | 100% | 86% | 0% |
| vosk-small-en-us-0.15 | piper | 26% | 1.00 | 89% | 100% | 100% | 10% | 0% |
| vosk-en-us-0.22-lgraph | espeak175 | 65% | 1.00 | 60% | 81% | 100% | 27% | 0% |
| vosk-en-us-0.22-lgraph | espeak300 | 88% | 0.82 | 15% | 47% | 100% | 67% | 0% |
| vosk-en-us-0.22-lgraph | espeak450 | 99% | 0.67 | 13% | 43% | 100% | 88% | 0% |
| vosk-en-us-0.22-lgraph | piper | 21% | 1.00 | 94% | 98% | 100% | 7% | 0% |
<!-- /TABLES -->

### Decision rule: flag "cut off" when k̂_sim < n - t (core clips; `scripts/decision.py`)

<!-- DECISION -->
| model | voice | t | detected (all cuts) | detected (cuts with k ≤ n-2) | false alarm on full |
|---|---|---|---|---|---|
| parakeet-tdt-0.6b-v2 | espeak175 | 0 | 100% | 100% | 6% |
| parakeet-tdt-0.6b-v2 | espeak175 | 1 | 77% | 100% | 1% |
| parakeet-tdt-0.6b-v2 | espeak300 | 0 | 98% | 100% | 29% |
| parakeet-tdt-0.6b-v2 | espeak300 | 1 | 83% | 100% | 8% |
| parakeet-tdt-0.6b-v2 | espeak450 | 0 | 100% | 100% | 43% |
| parakeet-tdt-0.6b-v2 | espeak450 | 1 | 85% | 100% | 15% |
| parakeet-tdt-0.6b-v2 | piper | 0 | 100% | 100% | 7% |
| parakeet-tdt-0.6b-v2 | piper | 1 | 72% | 100% | 0% |
| parakeet-tdt-0.6b-v3 | espeak175 | 0 | 100% | 100% | 14% |
| parakeet-tdt-0.6b-v3 | espeak175 | 1 | 74% | 100% | 2% |
| parakeet-tdt-0.6b-v3 | espeak300 | 0 | 98% | 100% | 21% |
| parakeet-tdt-0.6b-v3 | espeak300 | 1 | 85% | 100% | 5% |
| parakeet-tdt-0.6b-v3 | espeak450 | 0 | 98% | 100% | 61% |
| parakeet-tdt-0.6b-v3 | espeak450 | 1 | 94% | 100% | 33% |
| parakeet-tdt-0.6b-v3 | piper | 0 | 100% | 100% | 7% |
| parakeet-tdt-0.6b-v3 | piper | 1 | 72% | 100% | 0% |
| fw-small.en | espeak175 | 0 | 100% | 100% | 11% |
| fw-small.en | espeak175 | 1 | 77% | 100% | 5% |
| fw-small.en | espeak300 | 0 | 100% | 100% | 23% |
| fw-small.en | espeak300 | 1 | 83% | 97% | 6% |
| fw-small.en | espeak450 | 0 | 100% | 100% | 38% |
| fw-small.en | espeak450 | 1 | 83% | 94% | 18% |
| fw-small.en | piper | 0 | 98% | 100% | 6% |
| fw-small.en | piper | 1 | 72% | 100% | 0% |
| fw-distil-small.en | espeak175 | 0 | 100% | 100% | 11% |
| fw-distil-small.en | espeak175 | 1 | 77% | 100% | 5% |
| fw-distil-small.en | espeak300 | 0 | 100% | 100% | 26% |
| fw-distil-small.en | espeak300 | 1 | 83% | 97% | 11% |
| fw-distil-small.en | espeak450 | 0 | 100% | 100% | 42% |
| fw-distil-small.en | espeak450 | 1 | 83% | 94% | 20% |
| fw-distil-small.en | piper | 0 | 100% | 100% | 6% |
| fw-distil-small.en | piper | 1 | 72% | 100% | 0% |
| fw-large-v3-turbo | espeak175 | 0 | 100% | 100% | 7% |
| fw-large-v3-turbo | espeak175 | 1 | 74% | 100% | 7% |
| fw-large-v3-turbo | espeak300 | 0 | - | - | 20% |
| fw-large-v3-turbo | espeak300 | 1 | - | - | 7% |
| fw-large-v3-turbo | espeak450 | 0 | - | - | 27% |
| fw-large-v3-turbo | espeak450 | 1 | - | - | 13% |
| fw-large-v3-turbo | piper | 0 | - | - | 0% |
| fw-large-v3-turbo | piper | 1 | - | - | 0% |
| fw-base.en | espeak175 | 0 | 100% | 100% | 13% |
| fw-base.en | espeak175 | 1 | 79% | 100% | 1% |
| fw-base.en | espeak300 | 0 | 98% | 97% | 39% |
| fw-base.en | espeak300 | 1 | 79% | 97% | 12% |
| fw-base.en | espeak450 | 0 | 98% | 100% | 71% |
| fw-base.en | espeak450 | 1 | 94% | 100% | 38% |
| fw-base.en | piper | 0 | 100% | 100% | 8% |
| fw-base.en | piper | 1 | 72% | 100% | 0% |
<!-- /DECISION -->

## Real Orca sessions

Extra evaluation set: 426 clips recorded from real Orca sessions
(`.orca-lab/out/real-corpus-manifest.jsonl`, from `make_manifest.py`, read-only), espeak-ng
en-us as played, each WAV already cut where Orca interrupted it (WAV length == heardMs, checked).
Mix: SPEAK full 140 (75 at 170 wpm, 65 at 449), SPEAK cut 226 (145 / 81), CHAR (single typed
letter) cut 58 / full 2. 209 cuts have heardMs <= 80 ms (e.g. "Nightly" cut after 6 ms at
startup), which are reported separately as near-empty.

Import (`scripts/build_real.py`): resampled to 16 kHz, 300 ms silence padded each side like the
synthetic clips, reference = norm(text), k = len(norm(heardText)); type full / trunc (cut with no
partial word) / mid (cut inside `partialWord`). In 3 clips ("Apply the twenty percent ...", heard
"Apply the twenty") the normaliser merges "twenty percent" into "20%", so the heard prefix is not
a token prefix; they are kept and score as a partial-word cut.

**match** per clip: full -> k̂_sim == n; cut -> k̂_sim == k, or k+1 when a partial word was
playing, and no exact hit on any token beyond k+1 (nothing from the unplayed rest of `text`).

Models: the three best synthetic CPU candidates, Parakeet-TDT-0.6b-v2, faster-whisper small.en
and distil-small.en (all 426 clips each).

Summary:
- **No completion of the unplayed text** on any of the 284 real cut clips by any of the three
  (≥2 hits beyond k+1: 0/284 each). distil-small.en and small.en have 5 and 3 single
  coincidental hits at 449 wpm ("When you get it" for heard "Review the shipping").
- **170 wpm works:** complete SPEAK utterances transcribed to the last token 72/75 (Parakeet),
  68/75 (small.en), 71/75 (distil); cuts >80 ms matched 40/40, 40/40 and 35/40. With the
  one-token slack rule (flag only when 2+ expected tokens are missing): 0/75 false alarms and
  87/87 such cuts detected, for all three.
- **449 wpm does not:** complete utterances matched 8/65, 3/65, 9/65; even with the slack rule
  48-52 of 65 complete utterances would be flagged as cut. Real 449 wpm is harder than the
  synthetic 450 wpm set (Parakeet false "cut" 88% vs 43%), probably because many real 449 clips
  are short ("Nightly", "Start button", "Screen reader on.").
- **Near-empty cuts (≤80 ms):** nothing from `text` is ever produced, but the models emit
  fillers: small.en on 165/209 ("You"), Parakeet on 158/209 raw ("Yeah.", "Um", "Uh"; 80 after
  the normaliser), distil-small.en on 69/209. A checker should treat one short filler token as
  "nothing heard".
- Single typed letters (CHAR, 58 cuts, all near-empty, 2 full): the 2 complete ones were right
  for Parakeet and wrong for both Whisper models.

<!-- REAL_TABLES -->
| model | group | clips | match | clean match (no extra words) | non-empty output (normalised / raw incl. Um, Uh) | k̂_sim exact | within 1 | any hit beyond k+1 | ≥2 hits beyond k+1 (completion) | false 'cut' (full only) |
|---|---|---|---|---|---|---|---|---|---|---|
| fw-distil-small.en | all | 426 | 78% (331/426) | 73% (312/426) | 67% (285/426) / 67% (285/426) | 77% (330/426) | 86% (367/426) | 2% (5/284) | 0% (0/284) | 44% (62/142) |
| fw-distil-small.en | full, 170 wpm, SPEAK | 75 | 95% (71/75) | 83% (62/75) | 100% (75/75) / 100% (75/75) | 95% (71/75) | 100% (75/75) | - | - | 5% (4/75) |
| fw-distil-small.en | full, 449 wpm, SPEAK | 65 | 14% (9/65) | 0% (0/65) | 100% (65/65) / 100% (65/65) | 14% (9/65) | 22% (14/65) | - | - | 86% (56/65) |
| fw-distil-small.en | full, CHAR | 2 | 0% (0/2) | 0% (0/2) | 100% (2/2) / 100% (2/2) | 0% (0/2) | 100% (2/2) | - | - | 100% (2/2) |
| fw-distil-small.en | cut >80 ms, 170 wpm, SPEAK | 40 | 88% (35/40) | 88% (35/40) | 98% (39/40) / 98% (39/40) | 88% (35/40) | 100% (40/40) | 0% (0/40) | 0% (0/40) | - |
| fw-distil-small.en | cut >80 ms, 449 wpm, SPEAK | 35 | 49% (17/35) | 46% (16/35) | 100% (35/35) / 100% (35/35) | 46% (16/35) | 77% (27/35) | 14% (5/35) | 0% (0/35) | - |
| fw-distil-small.en | cut ≤80 ms (near-empty), 170 wpm, SPEAK | 105 | 100% (105/105) | 100% (105/105) | 25% (26/105) / 25% (26/105) | 100% (105/105) | 100% (105/105) | 0% (0/105) | 0% (0/105) | - |
| fw-distil-small.en | cut ≤80 ms (near-empty), 449 wpm, SPEAK | 46 | 78% (36/46) | 78% (36/46) | 26% (12/46) / 26% (12/46) | 78% (36/46) | 100% (46/46) | 0% (0/46) | 0% (0/46) | - |
| fw-distil-small.en | cut ≤80 ms (near-empty), CHAR | 58 | 100% (58/58) | 100% (58/58) | 53% (31/58) / 53% (31/58) | 100% (58/58) | 100% (58/58) | 0% (0/58) | 0% (0/58) | - |
| fw-small.en | all | 426 | 76% (325/426) | 76% (322/426) | 85% (364/426) / 85% (364/426) | 76% (325/426) | 86% (365/426) | 1% (3/284) | 0% (0/284) | 50% (71/142) |
| fw-small.en | full, 170 wpm, SPEAK | 75 | 91% (68/75) | 91% (68/75) | 100% (75/75) / 100% (75/75) | 91% (68/75) | 100% (75/75) | - | - | 9% (7/75) |
| fw-small.en | full, 449 wpm, SPEAK | 65 | 5% (3/65) | 0% (0/65) | 100% (65/65) / 100% (65/65) | 5% (3/65) | 20% (13/65) | - | - | 95% (62/65) |
| fw-small.en | full, CHAR | 2 | 0% (0/2) | 0% (0/2) | 100% (2/2) / 100% (2/2) | 0% (0/2) | 100% (2/2) | - | - | 100% (2/2) |
| fw-small.en | cut >80 ms, 170 wpm, SPEAK | 40 | 100% (40/40) | 100% (40/40) | 55% (22/40) / 55% (22/40) | 100% (40/40) | 100% (40/40) | 0% (0/40) | 0% (0/40) | - |
| fw-small.en | cut >80 ms, 449 wpm, SPEAK | 35 | 43% (15/35) | 43% (15/35) | 100% (35/35) / 100% (35/35) | 43% (15/35) | 74% (26/35) | 9% (3/35) | 0% (0/35) | - |
| fw-small.en | cut ≤80 ms (near-empty), 170 wpm, SPEAK | 105 | 100% (105/105) | 100% (105/105) | 78% (82/105) / 78% (82/105) | 100% (105/105) | 100% (105/105) | 0% (0/105) | 0% (0/105) | - |
| fw-small.en | cut ≤80 ms (near-empty), 449 wpm, SPEAK | 46 | 78% (36/46) | 78% (36/46) | 54% (25/46) / 54% (25/46) | 78% (36/46) | 100% (46/46) | 0% (0/46) | 0% (0/46) | - |
| fw-small.en | cut ≤80 ms (near-empty), CHAR | 58 | 100% (58/58) | 100% (58/58) | 100% (58/58) / 100% (58/58) | 100% (58/58) | 100% (58/58) | 0% (0/58) | 0% (0/58) | - |
| parakeet-tdt-0.6b-v2 | all | 426 | 80% (341/426) | 78% (333/426) | 69% (296/426) / 88% (374/426) | 79% (338/426) | 87% (372/426) | 0% (0/284) | 0% (0/284) | 42% (60/142) |
| parakeet-tdt-0.6b-v2 | full, 170 wpm, SPEAK | 75 | 96% (72/75) | 96% (72/75) | 100% (75/75) / 100% (75/75) | 96% (72/75) | 100% (75/75) | - | - | 4% (3/75) |
| parakeet-tdt-0.6b-v2 | full, 449 wpm, SPEAK | 65 | 12% (8/65) | 0% (0/65) | 100% (65/65) / 100% (65/65) | 12% (8/65) | 26% (17/65) | - | - | 88% (57/65) |
| parakeet-tdt-0.6b-v2 | full, CHAR | 2 | 100% (2/2) | 100% (2/2) | 100% (2/2) / 100% (2/2) | 100% (2/2) | 100% (2/2) | - | - | 0% (0/2) |
| parakeet-tdt-0.6b-v2 | cut >80 ms, 170 wpm, SPEAK | 40 | 100% (40/40) | 100% (40/40) | 98% (39/40) / 98% (39/40) | 100% (40/40) | 100% (40/40) | 0% (0/40) | 0% (0/40) | - |
| parakeet-tdt-0.6b-v2 | cut >80 ms, 449 wpm, SPEAK | 35 | 54% (19/35) | 54% (19/35) | 100% (35/35) / 100% (35/35) | 46% (16/35) | 83% (29/35) | 0% (0/35) | 0% (0/35) | - |
| parakeet-tdt-0.6b-v2 | cut ≤80 ms (near-empty), 170 wpm, SPEAK | 105 | 100% (105/105) | 100% (105/105) | 55% (58/105) / 92% (97/105) | 100% (105/105) | 100% (105/105) | 0% (0/105) | 0% (0/105) | - |
| parakeet-tdt-0.6b-v2 | cut ≤80 ms (near-empty), 449 wpm, SPEAK | 46 | 80% (37/46) | 80% (37/46) | 26% (12/46) / 83% (38/46) | 80% (37/46) | 100% (46/46) | 0% (0/46) | 0% (0/46) | - |
| parakeet-tdt-0.6b-v2 | cut ≤80 ms (near-empty), CHAR | 58 | 100% (58/58) | 100% (58/58) | 17% (10/58) / 40% (23/58) | 100% (58/58) | 100% (58/58) | 0% (0/58) | 0% (0/58) | - |

Most common raw outputs on near-empty cuts (heardMs <= 80):

- fw-distil-small.en: '(empty)' x140, 'you' x39, 'and' x17, "It's" x8, 'Bye.' x2, 'If' x2
- fw-small.en: 'You' x137, '(empty)' x44, 'and' x17, "It's" x7, 'Bye!' x1, 'If you like this video, please like, comment, and subscribe!' x1
- parakeet-tdt-0.6b-v2: 'Yeah.' x60, 'Um' x59, '(empty)' x51, 'Uh' x19, 'If' x7, 'Yep.' x5
<!-- /REAL_TABLES -->

## Findings

1. **Speech rate decides everything.** Every model is usable at 175 wpm and on Piper, and none is
   usable at 450 wpm. Best WER at 175 / 300 / 450 / Piper: Parakeet-TDT v2 17% / 43% / 69% / 10%;
   faster-whisper small.en 26% / 44% / 114% / 10%. False "cut" on complete utterances goes from
   6-11% (175 wpm, Piper) to 38-43% (450 wpm) for the best three (Parakeet v2, small.en,
   distil-small.en), and to 61-96% (450 wpm) for every other model. The real Orca clips agree: at 170 wpm Parakeet
   transcribes 72/75 complete SPEAK utterances to the last token; at 449 wpm only 8/65.
2. **The stated hypothesis is not supported: nobody completes the sentence.** Tail completion
   (at least 2 exact hits beyond k+1) is 0% for every model on every voice, on 1,640 synthetic
   trunc + mid clips per full-corpus model (376 per core-subset model) and on the 284 real cut
   clips. The brief's looser
   definition (any hit beyond k+1) is 0-1%, and every case inspected is a coincidental function
   word in unrelated junk ("I'll see you next time" hitting "will", "oh" -> "0"). For example
   "Skip to main content. link." cut after "Skip", "Skip to", "Skip to main", "Skip to main
   content" comes back from fw-small.en as exactly those prefixes, never with "link". What
   Whisper does instead is failure mode 1 below.
3. **Truncation is visible, but recognition errors blur where.** With the expected text known,
   "was it cut?" (k̂ < n) fires on 98-100% of cut clips for all models, so detection is not the
   problem; false alarms on complete clips are. Where the cut fell (k̂ exactly k) is right for
   69-70% of core cut clips with the best faster-than-real-time models (Parakeet v2, small.en;
   87-89% within one token), 83-92% at 175 wpm and Piper. large-v3-turbo does better (89% exact,
   98% within one, espeak175 only) at 17x Parakeet's cost.
4. **A one-token slack makes it a usable check at normal rates.** Flag "cut off" only when
   k̂_sim < n - 1 (two or more expected tokens missing). Parakeet v2, synthetic: false alarm
   1% (175) / 0% (Piper) / 8% (300) / 15% (450), and every cut that removed 2+ tokens is still
   caught. Real Orca at 170 wpm, for Parakeet v2, small.en and distil-small.en alike: 0/75 false
   alarms and 87/87 cuts with 2+ missing tokens detected. Real 449 wpm: 48-52 of 65 complete
   utterances still flagged, so not usable. (`tables_decision.md`)
5. **Mid-word cuts:** most models emit a guess for the half word (57-85% "guessed"; Canary
   mostly drops it) and complete it to the right word 7-25% of the time (Parakeet v2 25%, faster-whisper base 25%),
   e.g. "Navigation landmark list with fi-" -> "... with five". So a half-played last word cannot
   be told apart from a fully played one by transcript alone, at best ±1 token.
6. **Near-empty cuts (real corpus, heardMs <= 80, 209 clips):** no model completes anything, but
   they emit fillers on 0-80 ms of audio: faster-whisper small.en outputs something on 165/209 (mostly "You", 137),
   Parakeet on 158/209 raw ("Yeah." 60, "Um" 59, "Uh" 19; 80 after the normaliser drops um/uh),
   distil-small.en on 69/209 (it is empty on the other 140). Treat a single short token as "nothing heard" on such clips.

## Recommendation

- **Best CPU model for "did the user hear it": NVIDIA Parakeet-TDT-0.6b-v2, int8 ONNX via
  onnx-asr** (CC-BY-4.0: fine for an MIT tool if the weights are downloaded at run time with
  attribution, not vendored). Lowest (Piper: tied) WER at every rate over all 336 full clips among the models that run
  faster than real time, no hallucination on any of the 24 silence/noise clips, no sentence completion, word-level token timestamps (coarse, 80 ms frames).
  Cost on 4 E-cores: RTF 0.38, median 0.54 s per clip (0.47 s for clips under 1.2 s), 2.6 s
  cold load, 661 MB on disk, 1.2 GB peak RSS. Deterministic (40/40 x3, and identical in another
  process).
- **Runner-up (pure MIT): faster-whisper small.en int8**: equal truncation accuracy, worse WER
  at 175 wpm (26% vs 17%), much worse at 450 wpm (repetition loops), hallucinates on 17 of 24
  silence/noise clips ("You", "Thank you."), and is ~4x slower (RTF 1.36, 2.1 s per clip) because Whisper always
  encodes a 30 s window (latency is ~2 s whether the clip says "tab" or a whole sentence).
  distil-small.en is barely faster (RTF 1.26), slightly less accurate, and quieter on silence
  (9/24). Cheapest usable option: Moonshine base (RTF 0.12) or Vosk small (0.10), at clearly
  lower accuracy (35-44% false "cut" on full clips).
- **Most accurate, but too slow for CPU CI: faster-whisper large-v3-turbo int8** (MIT, 1.6 GB).
  On the same 158 clips it is close to Parakeet v2 on WER at 175 wpm (14% vs 11%), clearly better at
  placing the cut (89% vs 81% exact) and at 450 wpm (WER 42% vs 58%), but it costs 10 s per clip on 4
  E-cores (RTF 6.6, 2 GB RSS) and still hallucinates on silence (14/24).
- **Is ASR viable?** Yes, as a **soft check at normal speech rates** (Orca's default 175 wpm, a
  neural voice at default rate): compare the transcript with the text guidepup already knows,
  and flag "cut off" only when two or more expected tokens are missing. It is marginal at 300 wpm
  (Parakeet v2 8% false alarms with the slack rule, synthetic only) and **not viable at 450 wpm**
  with any model tested (15%+ synthetic, 74% real at 449 wpm), and it cannot resolve the last
  word (mid-word vs whole) or single letters / key echo ("c" -> "See", "shift tab" -> "Shit
  fam.", 57% exact at best among the practical models on 1-2 token utterances).
- Suggested next experiment (not built): since the expected text is known, score it against the
  audio with **CTC forced alignment** (the MMS_FA aligner used to build this corpus, or
  Parakeet's CTC head) instead of open transcription. Per-word alignment confidence for the
  expected words should beat transcription at 450 wpm and on single letters, and has no
  hallucination channel.

## Failure modes (with examples)

1. **Whisper repetition loops / unrelated hallucination at fast rates** (the reason WER exceeds
   100%): espeak 450 "Email. edit text. required. invalid entry." -> "He made it that way, he
   made it that way, ..." (fw-base.en, 186 edits); espeak 300 "Screen Reader A11y Workflows" ->
   "three, three, three, ..."; "testing testing 123" at 450 -> "That's exactly what I would like
   to be." (fw-tiny.en). Temperature fallback (which would re-decode on high compression ratio)
   was deliberately off for determinism; it would change these outputs, not necessarily fix them.
2. **Silence hallucination (faster-whisper and Vosk lgraph):** on the 24 silence/noise clips,
   fw-base.en 19/24 ("You", "Okay.", "All right."), vosk lgraph 18/24 ("the"), fw-small.en 17/24
   ("You", "Thank you."), large-v3-turbo 14/24 ("Thank you.", "Amen."), distil-small.en 9/24, vosk
   small 8/24 ("huh"), fw-tiny.en 3/24. Clean (0/24): Parakeet v2, Canary, Moonshine tiny/base,
   zipformer, and whisper.cpp (which emits the marker "[BLANK_AUDIO]" / "(buzzing)", stripped by
   the normaliser as bracketed text). Parakeet v3 2/24 ("Yeah."), moonshine-voice small 1/24. On
   real near-empty clips small.en once produced "If you like this video, please like, comment,
   and subscribe!".
3. **Dropping short or fast speech:** Moonshine tiny returns nothing for 63/336 full clips
   (e.g. "Update. button.", "tab"); on 12 of them, raising max_len to 192 changed nothing and
   removing the 300 ms padding gave text for 6 (mostly wrong); Canary-180m-flash
   returns nothing for most 300/450 wpm clips (median hypothesis length 0). This shows up as
   false "cut" on complete clips.
4. **Last-word loss:** Vosk small drops a final word on complete clips ("Update. button." ->
   "update"); Parakeet "Place order button" -> "Place order ma" on a real Orca clip.
5. **Homophones on letters and key names:** "c" -> "See", "b" -> "Peace.", "3" -> "Free",
   "dash dash" -> "Mouse, mouse.", "period" -> "Damn it.".
6. **Normalisation artefacts that look like truncation:** "$42.50" (espeak reads "dollar forty
   two point five zero"; fixed in the normaliser), "Git Hub"/"GitHub", "twenty percent" -> "20%".
7. **Timestamps:** whisper.cpp word ends snap to segment ends (tiny.en: 613 of 725 last-word ends
   fall on a whole second); unusable without its DTW mode. zipformer's token times lag by ~0.4 s.
   faster-whisper (cross-attention DTW) is closest: median |last word end - aligned end of word k| 40-100 ms;
   Parakeet's token-start + 80 ms estimate is ~130 ms off.

8. **State carried across utterances (Vosk, moonshine-voice):** in-process repeats are identical,
   but the same clip gives a different transcript depending on what the recogniser decoded
   before. Vosk with one recogniser and `Reset()` between clips (as in the lgraph run and the
   determinism runs) vs a fresh recogniser per clip (vosk-small main run): 37/40 identical for
   small, 25/28 for lgraph ("company the" vs "company to the"); moonshine-voice small 4/6
   ("you Add to cart, lightning bolt" vs "Add to cart lightning bolt"). Use a fresh recogniser
   per utterance. Every other model gave identical text in another process on the other lane.

## Caveats

- CPUs 12-19 on this host are Alder Lake **E-cores** (i9-12900H, max 3.8 GHz, no SMT, two
  4-core clusters with shared L2). Absolute RTF here is not GitHub's ubuntu-latest runner;
  relative ordering is what transfers.
- onnxruntime pins its own worker threads and escapes `taskset`: it was found spreading Piper's
  threads onto cores 2-11 during corpus synthesis (about 28 s of wall time, before the check).
  Every later process ran under `tools/pin.sh`, an LD_PRELOAD shim that clamps
  `sched_setaffinity`/`pthread_setaffinity_np` to the starting mask; each run records its
  threads' allowed CPUs.
- Piper (`piper-tts` 1.8.0) is GPL-3.0; it is only corpus tooling here, not part of anything
  shipped.
- Not every model ran every clip: `all` = 2028 clips; `core` = 728 (all full clips, trunc/mid of
  the 15 brief phrases, silence/noise, 3 pairs per voice); `turbo` = 158 (all full clips of the
  brief phrases, their espeak175 trunc/mid, silence/noise), used for fw-large-v3-turbo (~12 s per
  clip here) and the two moonshine-voice streaming models (~3 s per clip). The headline truncation
  columns use the core clips so models compare on the same set.
- Decoding was pinned for determinism: Whisper temperature 0 only (no fallback), beam 5
  (faster-whisper) / greedy (whisper.cpp), no VAD, no previous-text conditioning. Production
  Whisper defaults (temperature fallback on compression ratio) would change the repetition-loop
  outputs.
- Thread control: faster-whisper `cpu_threads=4`; onnxruntime sessions `intra_op_num_threads=4`;
  sherpa-onnx `num_threads=4`; whisper.cpp `n_threads=4`. Vosk/Kaldi decodes on one thread.
  moonshine-voice exposes no thread option and ran 69 threads inside its 4-CPU mask. Every run
  logged its threads' allowed CPUs (`allowed_cpus` in each output's meta line): all inside 12-15
  or 16-19.
- Correctness runs used two 4-CPU lanes in parallel (12-15 and 16-19, separate E-core clusters);
  timing used a separate pass with nothing else of ours running. Unrelated host processes
  (temporal-server, protonmail bridge) were occasionally scheduled on CPUs 18-19.
- moonshine-voice downloads its quantised models from download.moonshine.ai, not Hugging Face;
  Vosk models come from alphacephei.com. Both anonymous.
- Parakeet word end times are estimated (token start + one 80 ms frame); onnx-asr gives only
  token start times.
- fw-large-v3-turbo was not run in the determinism pass (time); its "-" there means "not
  measured", not a failure.
- The scoring/summary scripts (light, single-threaded, a few seconds each) ran unpinned until
  about 04:05 PST; after that they were pinned to 16-19. No model inference ran unpinned.
- One timing pass was started too early by a faulty wait script (pid check) and ran briefly
  alongside the lanes; it was killed and its output deleted before the real timing pass.
- Synthetic TTS only (except the "Real Orca sessions" set, which is espeak-ng as Orca played it).
  Real VoiceOver/NVDA voices, room/codec effects and speech-rate changes
  mid-utterance are not covered.
