"""Phrase list for the ASR benchmark.

Each entry: (id, source, text). `text` is what the screen reader sent.
`say` (derived) is what we feed the TTS: digits spelled out the way espeak-ng
1.52 reads them (verified with `espeak-ng -x`, see check_say.sh), punctuation
kept so the TTS keeps its pauses.
"""
import json, re, sys
from pathlib import Path

BRIEF = [
    "Update. button.",
    "testing testing 123",
    "Name. entry.. Focus mode",
    "heading level 2 Get Started",
    "Skip to main content. link.",
    "navigation landmark. list with 5 items",
    "Guidepup Logo. image.",
    "check box not checked. Subscribe to newsletter",
    "tab",
    "link",
    "Second button. button.",
    "Your cart has 3 items. Subtotal $42.50",
    "Add to cart, Lightning Bolt, Near Mint. button.",
    "Search. combo box. collapsed.",
    "leaving list. main landmark.",
]

EXTRA = [
    "Submit. button. unavailable.",
    "Email. edit text. required. invalid entry.",
    "heading level 1 Bards and Cards",
    "banner landmark",
    "complementary landmark. Filters",
    "footer landmark",
    "Remember me. check box. checked.",
    "Dark mode. toggle button. pressed.",
    "Sort by. combo box. Price, low to high. expanded.",
    "Next page. link. visited.",
    "table with 4 rows and 3 columns",
    "row 2. column 3. Price",
    "list item. 2 of 7",
    "dialog. Confirm deletion",
    "alert. Your session will expire in 5 minutes",
    "menu. File. 6 items",
    "Open. menu item. Control O",
    "Settings. tab. 3 of 4. selected.",
    "Volume. slider. 50 percent",
    "progress bar. 75 percent",
    "Search results. heading level 2. 24 results",
    "graphic. Card back",
    "out of list",
    "comma",
    "period",
    "exclamation",
    "left paren",
    "dash dash",
    "shift tab",
    "escape",
    "backspace",
    "space",
    "down arrow",
    "enter",
]

SNAPSHOT_GLOB = "examples/**/*spokenPhrase*.snapshot.json"
UPSTREAM = Path.home() / "projects/guidepup-wt/upstream-main"

ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def int_words(n: int) -> str:
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("" if n % 10 == 0 else " " + ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return ONES[n // 100] + " hundred" + ("" if rest == 0 else " " + int_words(rest))
    raise ValueError(n)


# espeak-ng 1.52 en-us readings checked by phoneme output (-x):
#   "$42.50" -> "dollar forty two point five zero"; "A11y" -> "A eleven y";
#   "Abc" -> "A B C"; "GitHub" -> "Git Hub".
SPECIAL = {
    "$42.50": "dollar forty two point five zero",
    "A11y": "A eleven y",
    "Abc": "A B C",
}


def say(text: str) -> str:
    s = text
    for k, v in SPECIAL.items():
        s = s.replace(k, v)
    s = re.sub(r"\d+", lambda m: int_words(int(m.group())), s)
    return s


def load():
    out, seen = [], set()

    def add(src, t):
        if t in seen:
            return
        seen.add(t)
        out.append({"id": f"p{len(out):03d}", "source": src, "text": t, "say": say(t)})

    for t in BRIEF:
        add("brief", t)
    for t in EXTRA:
        add("extra", t)
    for f in sorted(UPSTREAM.glob(SNAPSHOT_GLOB)):
        rel = str(f.relative_to(UPSTREAM))
        for t in json.loads(f.read_text()):
            add("snapshot:" + rel, t)
    return out


if __name__ == "__main__":
    ps = load()
    json.dump(ps, sys.stdout, indent=1)
    print(file=sys.stderr)
    print(len(ps), "phrases", file=sys.stderr)
