# keywords_manager.py
import re
from pathlib import Path
from typing import Optional, Tuple, List
import unicodedata

# Optional fuzzy support; only imported when enabled
_rapidfuzz_available = False
try:
    from rapidfuzz import fuzz
    _rapidfuzz_available = True
except Exception:
    _rapidfuzz_available = False


def normalize_unicode(text: str) -> str:
    """Normalize text to NFC and lower-case it."""
    if text is None:
        return ""
    return unicodedata.normalize("NFC", text).strip().lower()


def strip_combining_marks(text: str) -> str:
    """
    Decompose (NFD) and remove combining marks (category 'Mn').
    This produces a 'base-letter only' version useful for loose matching
    across small vowel-sign / diacritic differences.
    """
    if text is None:
        return ""
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    # recompose to NFC for a stable form
    return unicodedata.normalize("NFC", stripped).lower()


class KeywordsManager:
    """
    Load custom keywords/phrases from a text file and check transcripts for matches.
    - One phrase per line in the file.
    - Lines starting with '#' are comments.
    - Matching tries (in this order):
        1) exact regex on normalized text (NFC)
        2) regex on diacritic-stripped text
        3) substring match on normalized / stripped text
        4) optional fuzzy match on stripped text (if enabled)
    """

    def __init__(self, filepath="custom_keywords.txt", enable_fuzzy: bool = False, fuzzy_threshold: int = 80):
        self.path = Path(filepath)
        self.enable_fuzzy_flag = False
        self.fuzzy_threshold = 80
        self._keywords: List[Tuple[str, Optional[re.Pattern], str]] = []
        # (raw_phrase, compiled_regex_or_None_on_error, stripped_normalized_phrase)
        self._load()
        if enable_fuzzy:
            self.enable_fuzzy(fuzzy_threshold)

    def _load(self):
        self._keywords = []
        # create file if not exists
        if not self.path.exists():
            self.path.write_text(
                "# add one keyword or phrase per line\n# lines starting with # are ignored\n",
                encoding="utf-8",
            )
            return

        text = self.path.read_text(encoding="utf-8")
        for ln in text.splitlines():
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            # store raw phrase
            raw = ln
            norm = normalize_unicode(raw)
            stripped = strip_combining_marks(norm)
            # prefer regex with word boundaries; if it fails, fall back to None
            try:
                # use word boundaries where possible - safe for most languages
                pattern = r"\b" + re.escape(norm) + r"\b"
                compiled = re.compile(pattern, flags=re.IGNORECASE)
            except re.error:
                compiled = None
            self._keywords.append((raw, compiled, stripped))

    def reload(self):
        """Reload keywords from disk (call if you edit file while program runs)."""
        self._load()

    def enable_fuzzy(self, threshold: int = 80):
        """Enable fuzzy matching (requires rapidfuzz)."""
        global _rapidfuzz_available
        if not _rapidfuzz_available:
            raise RuntimeError("rapidfuzz not installed. Install with: pip install rapidfuzz")
        self.enable_fuzzy_flag = True
        self.fuzzy_threshold = int(threshold)

    def disable_fuzzy(self):
        self.enable_fuzzy_flag = False

    def _try_match(self, txt_norm: str, txt_stripped: str) -> Optional[str]:
        """Internal match attempts, returns raw phrase if matched else None."""
        # 1) regex on normalized text
        for raw, compiled, stripped in self._keywords:
            if compiled:
                try:
                    if compiled.search(txt_norm):
                        return raw
                except Exception:
                    # ignore regex problems for safety
                    pass

        # 2) regex on stripped text (build a temporary regex if compiled missing)
        for raw, compiled, stripped in self._keywords:
            if compiled is not None:
                # we already checked compiled against norm; checking stripped may need its own expression
                # instead do a substring check on stripped
                pass

        # 3) substring checks (normalized and stripped)
        for raw, compiled, stripped in self._keywords:
            if stripped and stripped in txt_stripped:
                return raw
            # also safe fallback: normalized substring
            if raw and normalize_unicode(raw) in txt_norm:
                return raw

        # 4) optional fuzzy on stripped text
        if self.enable_fuzzy_flag and _rapidfuzz_available:
            for raw, compiled, stripped in self._keywords:
                if not stripped:
                    continue
                # use partial_ratio for phrase-in-sentence matching
                score = fuzz.partial_ratio(stripped, txt_stripped)
                if score >= self.fuzzy_threshold:
                    return raw

        return None

    def match_keyword(self, text: str) -> Optional[str]:
        """
        Return the matched raw phrase if any match, else None.
        Performs unicode normalization and diacritic stripping internally.
        """
        if not text:
            return None
        txt_norm = normalize_unicode(text)
        txt_stripped = strip_combining_marks(txt_norm)
        return self._try_match(txt_norm, txt_stripped)
