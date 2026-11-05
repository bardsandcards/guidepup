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
