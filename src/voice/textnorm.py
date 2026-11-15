"""Arabic text helpers: normalisation for scoring speech recognition, error rates, and cleaning text for speech.

Scoring compares what was said with what the recogniser wrote. Arabic spelling has several equally valid surface
forms (with or without diacritics, hamza on alef or not, ة or ه at the end of a word), so both sides are reduced
to one form first. The normalisation is for SCORING ONLY: nothing the user hears or the model reads goes through it.
"""

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# Tashkeel (fathatan .. sukun and the rarer marks), superscript alef, Quranic annotation signs.
_DIACRITICS = re.compile("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_TATWEEL = "\u0640"
_LETTERS = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ة": "ه",
    }
)
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_ARABIC_LETTER = re.compile("[\u0621-\u064a\u0671-\u06d3]")


def normalize(text: str) -> str:
    """One canonical form for scoring: no diacritics, no punctuation, unified alef / ya / ta marbuta, Latin digits."""
    text = unicodedata.normalize("NFKC", text)  # presentation forms -> letters, combining hamza/madda -> composed
    text = _DIACRITICS.sub("", text).replace(_TATWEEL, "")
    text = text.translate(_LETTERS).translate(_DIGITS).lower()
    # Everything that is not a letter or a digit (punctuation, symbols, control characters) separates words.
    text = "".join(ch if unicodedata.category(ch)[0] in "LN" else " " for ch in text)
    return " ".join(text.split())


def edit_distance(ref: Sequence, hyp: Sequence) -> int:
    """Levenshtein distance: substitutions + insertions + deletions needed to turn `ref` into `hyp`."""
    previous = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        current = [i]
        for j, h in enumerate(hyp, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (r != h)))
        previous = current
    return previous[-1]


@dataclass(frozen=True)
class Score:
    """Errors and reference lengths, so that several scores can be summed into a corpus-level rate."""

    word_errors: int
    ref_words: int
    char_errors: int
    ref_chars: int

    @property
    def wer(self) -> float:
        return self.word_errors / self.ref_words if self.ref_words else float(self.word_errors > 0)

    @property
    def cer(self) -> float:
        return self.char_errors / self.ref_chars if self.ref_chars else float(self.char_errors > 0)


def score(reference: str, hypothesis: str) -> Score:
    """Word and character errors after normalisation. Characters are compared without spaces, so a wrong word
    boundary costs word errors but no character errors."""
    ref, hyp = normalize(reference), normalize(hypothesis)
    ref_words, hyp_words = ref.split(), hyp.split()
    ref_chars, hyp_chars = ref.replace(" ", ""), hyp.replace(" ", "")
    return Score(
        word_errors=edit_distance(ref_words, hyp_words),
        ref_words=len(ref_words),
        char_errors=edit_distance(ref_chars, hyp_chars),
        ref_chars=len(ref_chars),
    )


def total(scores: Iterable[Score]) -> Score:
    """Corpus-level score: errors and lengths summed (long sentences weigh more than short ones)."""
    scores = list(scores)
    return Score(
        word_errors=sum(s.word_errors for s in scores),
        ref_words=sum(s.ref_words for s in scores),
        char_errors=sum(s.char_errors for s in scores),
        ref_chars=sum(s.ref_chars for s in scores),
    )


def arabic_ratio(text: str) -> float:
    """Share of the letters in `text` that are Arabic letters (0.0 for text without letters)."""
    letters = [ch for ch in text if unicodedata.category(ch).startswith("L")]
    if not letters:
        return 0.0
    return sum(1 for ch in letters if _ARABIC_LETTER.match(ch)) / len(letters)


_MARKDOWN_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"https?://\S+")
_LIST_MARKER = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s+", re.MULTILINE)
_EMPHASIS = re.compile(r"[*_`~]+")  # removed without a space: **كلمة**. keeps its full stop attached
_BLOCK_MARKUP = re.compile(r"[#>|]+")


def clean_for_speech(text: str) -> str:
    """Remove what a text-to-speech voice would read aloud or stumble over: markdown, links, list markers, emoji."""
    text = _MARKDOWN_LINK.sub(r"\1", text)
    text = _URL.sub(" ", text)
    text = _LIST_MARKER.sub("", text)
    text = _EMPHASIS.sub("", text)
    text = _BLOCK_MARKUP.sub(" ", text)
    # Symbols (emoji, arrows, box drawing) and control/format characters, except whitespace.
    text = "".join(" " if unicodedata.category(ch) in ("So", "Sk", "Cf", "Cc", "Co", "Cn") else ch for ch in text)
    return " ".join(text.split())
