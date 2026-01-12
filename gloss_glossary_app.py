import os
import hmac
import re
import streamlit as st
import pandas as pd

# =========================
# 0) Password Gate (Streamlit Cloud Secrets: APP_PASSWORD="...")
# =========================
def check_password():
    if "password_ok" not in st.session_state:
        st.session_state["password_ok"] = False

    def on_enter():
        if hmac.compare_digest(st.session_state.get("pw", ""), os.environ.get("APP_PASSWORD", "")):
            st.session_state["password_ok"] = True
            st.session_state["pw"] = ""
        else:
            st.session_state["password_ok"] = False

    if st.session_state["password_ok"]:
        return True

    st.text_input("Password", type="password", key="pw", on_change=on_enter)
    if "pw" in st.session_state and st.session_state["pw"] and not st.session_state["password_ok"]:
        st.error("Password incorrect")
    return False

if not check_password():
    st.stop()


# =========================
# 1) Glossary / Categories
# =========================
DEFAULT_GLOSSARY = {
    # person (auto-fill requested)
    "1": "1st person",
    "2": "2nd person",
    "3": "3rd person",

    # number
    "SG": "singular",
    "PL": "plural",

    # possession
    "POSS": "possessive",

    # cases
    "ACC": "accusative",
    "DAT": "dative",
    "GEN": "genitive",
    "ABL": "ablative",
    "LOC": "locative",
    "INS": "instrumental",

    # other common
    "VN": "verbal noun",
    "IMP": "imperative",
    "PROG": "progressive",
    "Q": "question particle",

    # verbal morphology parts
    "PTCP": "participle",
    "PAST": "past",
    "NPST": "non-past",
    "CVB": "converb",
    "SEQ": "sequential",
    "CNT": "continuative",

    # convenient combined labels (optional)
    "PTCP.PAST": "past participle",
    "PTCP.NPST": "non-past participle",
    "CVB.SEQ": "sequential converb",
    "CVB.CNT": "continuative converb",

    # person+number combos (optional; decomposition will also add parts)
    "1SG": "1st person singular",
    "2SG": "2nd person singular",
    "3SG": "3rd person singular",
    "1PL": "1st person plural",
    "2PL": "2nd person plural",
    "3PL": "3rd person plural",

    # common compounded forms (optional)
    "1SG.POSS": "1st person singular possessive",
    "2SG.POSS": "2nd person singular possessive",
    "3SG.POSS": "3rd person singular possessive",
    "1PL.POSS": "1st person plural possessive",
    "2PL.POSS": "2nd person plural possessive",
    "3PL.POSS": "3rd person plural possessive",
}

PERSON_SET = {"1", "2", "3"}
NUMBER_SET = {"SG", "PL"}
CASE_SET = {"ACC", "DAT", "GEN", "ABL", "LOC", "INS"}
POSSESSION_SET = {"POSS"}
VERB_MORPH_SET = {"PTCP", "CVB", "VN", "IMP"}
TAM_ASPECT_SET = {"PAST", "NPST", "PROG"}
MISC_SET = {"Q", "SEQ", "CNT"}

def categorize_abbr(abbr: str) -> str:
    if abbr in PERSON_SET:
        return "person"
    if abbr in NUMBER_SET:
        return "number"
    if abbr in CASE_SET:
        return "case"
    if abbr in POSSESSION_SET:
        return "possession"
    if abbr in VERB_MORPH_SET:
        return "verbal morphology"
    if abbr in TAM_ASPECT_SET:
        return "tense/aspect/mood"
    if abbr in MISC_SET:
        return "other"
    # fallbacks
    if re.fullmatch(r"[0-9]+", abbr):
        return "person"
    if re.fullmatch(r"[0-9]+[A-Z]+", abbr):
        return "agreement"
    if "." in abbr:
        return "compound"
    return ""


# =========================
# 2) Gloss line extraction (noise reduction)
#    Now considers '-' OR '=' tokens.
# =========================
def extract_gloss_lines(text: str, min_marked_tokens: int = 2) -> list[str]:
    """
    Extract only 'gloss-like' lines.
    Heuristic: a line containing at least N tokens with '-' OR '=' is considered a gloss line.
    """
    gloss_lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        tokens = re.split(r"\s+", s)
        marked_tokens = [t for t in tokens if ("-" in t or "=" in t)]
        if len(marked_tokens) >= min_marked_tokens:
            gloss_lines.append(s)
    return gloss_lines


# =========================
# 3) Abbreviation extraction + decomposition
#    Handles BOTH '-' and '='
# =========================
# Accept forms like: ACC, 3SG, 1PL, 2PL.POSS, PTCP.PAST, CVB.SEQ, 3.POSS
ABBR_PATTERN = re.compile(r"^(?:[0-9]*[A-Z]+(?:\.[A-Z0-9]+)*)$")
NUM_ALPHA_PATTERN = re.compile(r"^([0-9]+)([A-Z]+)$")  # 3SG -> 3 + SG

def _add_decomposed_units(abbr: str, out: list[str]) -> None:
    """
    Decompose:
      - dot compounds: PTCP.PAST -> PTCP, PAST
      - numeric+alpha: 3SG -> 3, SG
      - nested: 2PL.POSS -> 2PL, POSS, 2, PL
    """
    dot_parts = abbr.split(".") if "." in abbr else [abbr]
    for part in dot_parts:
        part = part.strip()
        if not part:
            continue

        # keep the dot-part itself (e.g. 2PL from 2PL.POSS)
        if ABBR_PATTERN.match(part):
            out.append(part)

        # numeric+alpha decomposition (3SG -> 3 + SG)
        m = NUM_ALPHA_PATTERN.match(part)
        if m:
            out.append(m.group(1))  # 3
            out.append(m.group(2))  # SG

def extract_abbreviations_from_gloss_lines(gloss_lines: list[str], enable_decomp: bool) -> list[str]:
    """
    Extract abbreviations from gloss lines.

    Handles BOTH '-' and '=':
      - lie-PROG=3SG  -> PROG, 3SG (and if enable_decomp: 3, SG)
    """
    abbreviations: list[str] = []

    for line in gloss_lines:
        tokens = re.split(r"\s+", line)
        for token in tokens:
            # split by '=' FIRST, because right side can be an abbreviation itself
            eq_parts = token.split("=")

            for part_eq in eq_parts:
                part_eq = part_eq.strip(".,;:()[]{}\"'")

                # (A) if the whole segment itself is an abbreviation (e.g. "3SG"), take it
                if ABBR_PATTERN.match(part_eq):
                    abbreviations.append(part_eq)
                    if enable_decomp:
                        _add_decomposed_units(part_eq, abbreviations)

                # (B) also look at hyphen suffixes (e.g. "lie-PROG" -> "PROG")
                parts_hy = part_eq.split("-")
                for suf in parts_hy[1:]:
                    suf = suf.strip(".,;:()[]{}\"'")
                    if not ABBR_PATTERN.match(suf):
                        continue
                    abbreviations.append(suf)
                    if enable_decomp:
                        _add_decomposed_units(suf, abbreviations)
