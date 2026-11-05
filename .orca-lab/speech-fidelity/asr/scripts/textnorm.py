"""The one normaliser used for every reference and every hypothesis.

1. openai-whisper's EnglishTextNormalizer (via the `whisper-normalizer` package, MIT):
   lowercase, strip punctuation, spelled numbers -> digits ("one hundred twenty three" -> "123",
   "second" -> "2nd"), British -> US spelling, drops fillers ("hmm", "uh").
2. A few compound aliases for spellings the corpus produces both ways
   ("git hub"/"github", "a b c"/"abc", "a p i"/"api", "a 11 y"/"a11y", "guide pup"/"guidepup").
3. Text is split at sentence/comma punctuation (". ", ", ", ...) and each piece is normalised
   separately, so "level two. twenty four results" stays "level 2 24 results" instead of the
   whisper normaliser merging it into "224".
4. Currency written by the model ("$42.50", "Subtotal$42.50") becomes "dollar 42.50", which is
   how espeak reads "$42.50" and how the references spell it (references never contain "$").
5. Standalone "1" -> "one" (the whisper normaliser keeps a lone "one" as a word but leaves
   "1" alone in some contexts; this makes the two agree).
"""
import re
from whisper_normalizer.english import EnglishTextNormalizer

_N = EnglishTextNormalizer()
ALIASES = [
    (r"\bgit hub\b", "github"),
    (r"\ba b c\b", "abc"),
    (r"\ba p i\b", "api"),
    (r"\ba 11 y\b", "a11y"),
    (r"\bguide pup\b", "guidepup"),
]


def _norm_piece(piece: str) -> list[str]:
    s = _N(piece)
    for pat, rep in ALIASES:
        s = re.sub(pat, rep, s)
    return s.split()


def norm(text: str) -> list[str]:
    text = re.sub(r"(\w)\$", r"\1 $", text or "")
    toks = []
    for piece in re.split(r"[.,;:!?]+(?:\s+|$)", text or ""):
        toks += _norm_piece(piece)
    out = []
    for t in toks:
        if t == "1":
            out.append("one")
        elif re.fullmatch(r"\$[\d.,]+", t):
            out += ["dollar", t[1:]]
        else:
            out.append(t)
    return out
