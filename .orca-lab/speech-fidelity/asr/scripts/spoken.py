"""Spoken forms of the corpus's non-letter reference tokens, for character CTC models."""
import re

# How espeak-ng en-us speaks the corpus's non-letter reference tokens (checked with `espeak-ng -x`).
SPOKEN = {
    "0": "zero", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven",
    "24": "twenty four", "123": "one hundred twenty three", "2nd": "second",
    "20%": "twenty percent", "50%": "fifty percent", "75%": "seventy five percent",
    "42.50": "forty two point five zero", "a11y": "a eleven y",
}


def spoken(tok):
    s = SPOKEN.get(tok, tok)
    if not re.fullmatch(r"[a-z' ]+", s):
        raise ValueError(f"no spoken form for {tok!r}")
    return s.replace(" ", "")
