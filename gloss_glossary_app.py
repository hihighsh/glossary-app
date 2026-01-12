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
    # person (requested auto-fill)
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

    # convenient combined labels (optional; you can keep/extend)
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
VERB_MORPH_SET = {"PTCP", "CVB", "VN", "IMP", "PROG"}
TAM_ASPECT_SET = {"PAST", "NPST", "PROG"}  # PROG is aspect but keep it here as well
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
        return "person"  # safe default for plain digits
    if re.fullmatch(r"[0-9]+[A-Z]+", abbr):
        return "agreement"
    if "." in abbr:
        return "compound"
    return ""


# =========================
# 2) Gloss line extraction (noise reduction)
# =========================
def extract_gloss_lines(text: str, min_hyphen_tokens: int = 2) -> list[str]:
    """Heuristic: a line containing at least N tokens with '-' is considered a gloss line."""
    gloss_lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        tokens = re.split(r"\s+", s)
        hyphen_tokens = [t for t in tokens if "-" in t]
        if len(hyphen_tokens) >= min_hyphen_tokens:
            gloss_lines.append(s)
    return gloss_lines


# =========================
# 3) Abbreviation extraction + decomposition
# =========================
# Accept forms like: ACC, 3SG, 1PL, 2PL.POSS, PTCP.PAST, CVB.SEQ, 3.POSS
ABBR_PATTERN = re.compile(r"^(?:[0-9]*[A-Z]+(?:\.[A-Z0-9]+)*)$")
NUM_ALPHA_PATTERN = re.compile(r"^([0-9]+)([A-Z]+)$")  # 3SG -> 3 + SG

def extract_abbreviations_from_gloss_lines(gloss_lines: list[str], enable_decomp: bool) -> list[str]:
    """
    Extract abbreviations from gloss lines.

    If enable_decomp:
      - PTCP.PAST -> also add PTCP and PAST
      - 2PL.POSS  -> also add 2PL and POSS, then 2 and PL
      - 3SG       -> also add 3 and SG
      - 3.POSS    -> also add 3 and POSS
    """
    abbreviations: list[str] = []

    for line in gloss_lines:
        tokens = re.split(r"\s+", line)
        for token in tokens:
            for peq in token.split("="):          # split by '='
                parts_hy = peq.split("-")         # split by '-'
                for ph in parts_hy[1:]:           # suffix parts only
                    ph = ph.strip(".,;:()[]{}\"'")
                    if not ABBR_PATTERN.match(ph):
                        continue

                    # Always include the original abbreviation
                    abbreviations.append(ph)

                    if not enable_decomp:
                        continue

                    # Decompose dot-compounds into parts (PTCP.PAST -> PTCP, PAST)
                    dot_parts = ph.split(".") if "." in ph else [ph]

                    for part in dot_parts:
                        # If numeric+alpha, decompose further (3SG -> 3, SG)
                        m = NUM_ALPHA_PATTERN.match(part)
                        if m:
                            abbreviations.append(m.group(1))  # 3
                            abbreviations.append(m.group(2))  # SG
                            # also include the combined part itself (3SG) if not already
                            # (it already is included as ph; but part could be 2PL inside 2PL.POSS)
                            abbreviations.append(part)
                        else:
                            abbreviations.append(part)

    return abbreviations


# =========================
# 4) Table builder
# =========================
def build_glossary_table(abbreviations: list[str], glossary_dict: dict) -> pd.DataFrame:
    freq: dict[str, int] = {}
    for abbr in abbreviations:
        freq[abbr] = freq.get(abbr, 0) + 1

    rows = []
    for abbr, count in sorted(freq.items(), key=lambda x: (-x[1], x[0])):
        meaning = glossary_dict.get(abbr, "")
        category = categorize_abbr(abbr)
        rows.append({
            "Category": category,
            "Abbreviation": abbr,
            "Meaning": meaning,
            "Count": count,
        })

    return pd.DataFrame(rows)[["Category", "Abbreviation", "Meaning", "Count"]]


# =========================
# 5) Streamlit UI
# =========================
st.set_page_config(page_title="Glossary Generator", layout="wide")
st.title("📌 グロス略号辞書（Abbreviation Glossary）生成")

if "input_text" not in st.session_state:
    st.session_state["input_text"] = """(1) aravakaš-lar ġala-ni bozor-ġa al-ïb bor-a
coachman-PL grain-ACC bazaar-DAT take-CVB.SEQ go-CVB.CNT
yat-ïb=dur.
lie-PROG=3SG
「御者は穀物をバザールに持って行っているところだ。」
"""

top_left, top_right = st.columns([1, 2])
with top_left:
    if st.button("🧹 Clear（入力を即消去）"):
        st.session_state["input_text"] = ""
        st.rerun()

with top_right:
    show_gloss_lines = st.checkbox("抽出されたグロス行を表示（事故防止のためデフォルトOFF）", value=False)

text_input = st.text_area(
    "📥 ここにテキストを貼り付けてください",
    key="input_text",
    height=260
)

col1, col2, col3 = st.columns([1, 1.4, 2])
with col1:
    min_hyphen_tokens = st.number_input("グロス行判定：ハイフン語数", min_value=1, max_value=10, value=2)
with col2:
    enable_decomp = st.checkbox("略号を分解して個別略号も一覧化（PTCP.PAST→PTCP+PAST / 3SG→3+SG）", value=True)
with col3:
    run_button = st.button("🔍 Glossary生成", use_container_width=True)

if run_button:
    gloss_lines = extract_gloss_lines(text_input, min_hyphen_tokens=int(min_hyphen_tokens))
    if not gloss_lines:
        st.warning("グロス行が見つかりませんでした。ハイフン語数の閾値を下げると改善する場合があります。")
        st.stop()

    if show_gloss_lines:
        st.subheader("✅ 抽出されたグロス行")
        st.code("\n".join(gloss_lines))

    abbreviations = extract_abbreviations_from_gloss_lines(gloss_lines, enable_decomp=enable_decomp)
    if not abbreviations:
        st.warning("略号が見つかりませんでした。テキスト形式を確認してください。")
        st.stop()

    df = build_glossary_table(abbreviations, DEFAULT_GLOSSARY)

    st.subheader("✅ 略号一覧（Category/Meaning は編集可能）")
    edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

    csv = edited_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ CSVとしてダウンロード",
        data=csv,
        file_name="abbreviation_glossary.csv",
        mime="text/csv"
    )
