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
# 1) Glossary dictionary
# =========================
DEFAULT_GLOSSARY = {
    # cases / agreement
    "ACC": "accusative",
    "DAT": "dative",
    "GEN": "genitive",
    "ABL": "ablative",
    "LOC": "locative",
    "INS": "instrumental",
    "POSS": "possessive",
    "PL": "plural",
    "SG": "singular",

    # person/number (as whole)
    "1SG": "1st person singular",
    "2SG": "2nd person singular",
    "3SG": "3rd person singular",
    "1PL": "1st person plural",
    "2PL": "2nd person plural",
    "3PL": "3rd person plural",

    # common compounded forms
    "1SG.POSS": "1st person singular possessive",
    "2SG.POSS": "2nd person singular possessive",
    "3SG.POSS": "3rd person singular possessive",
    "1PL.POSS": "1st person plural possessive",
    "2PL.POSS": "2nd person plural possessive",
    "3PL.POSS": "3rd person plural possessive",

    # verbal morphology
    "VN": "verbal noun",
    "IMP": "imperative",
    "PROG": "progressive",
    "Q": "question particle",

    "PTCP": "participle",
    "PAST": "past",
    "NPST": "non-past",

    "CVB": "converb",
    "SEQ": "sequential",
    "CNT": "continuative",

    # common combos
    "PTCP.PAST": "past participle",
    "PTCP.NPST": "non-past participle",
    "CVB.SEQ": "sequential converb",
    "CVB.CNT": "continuative converb",
}

# =========================
# 2) Gloss line extraction (noise reduction)
# =========================
def extract_gloss_lines(text: str, min_hyphen_tokens: int = 2) -> list[str]:
    """
    Extract only 'gloss-like' lines.
    Heuristic: a line containing at least N tokens with '-' is considered a gloss line.
    """
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
# 3) Abbreviation extraction
# =========================
# Accept forms like: ACC, 3SG, 1PL, 2PL.POSS, PTCP.PAST, CVB.SEQ
ABBR_PATTERN = re.compile(r"^(?:[0-9]*[A-Z]+(?:\.[A-Z0-9]+)*)$")

def extract_abbreviations_from_gloss_lines(gloss_lines: list[str]) -> list[str]:
    abbreviations = []
    for line in gloss_lines:
        tokens = re.split(r"\s+", line)
        for token in tokens:
            # split by '=' first
            for peq in token.split("="):
                # split by '-' (take suffix parts)
                parts_hy = peq.split("-")
                for ph in parts_hy[1:]:
                    ph = ph.strip(".,;:()[]{}\"'")
                    if ABBR_PATTERN.match(ph):
                        abbreviations.append(ph)
                    # also pick components of dot-compounds
                    if "." in ph:
                        for sp in ph.split("."):
                            if ABBR_PATTERN.match(sp):
                                abbreviations.append(sp)
    return abbreviations

# =========================
# 4) Hierarchical decomposition (PTCP.PAST -> PTCP + PAST)
# =========================
def decompose_abbr(abbr: str) -> list[str]:
    """Split dot-compounds into components; keep original as well handled elsewhere."""
    if "." in abbr:
        return [p for p in abbr.split(".") if p]
    return []

def meaning_for_parts(parts: list[str], glossary: dict) -> str:
    """
    Build a human-readable meaning string from parts, e.g.
    ['PTCP','PAST'] -> 'participle + past'
    """
    if not parts:
        return ""
    meanings = []
    for p in parts:
        meanings.append(glossary.get(p, ""))  # may be empty
    # show placeholders for unknown parts (optional; here we keep blank segments out)
    nonempty = [m for m in meanings if m]
    if not nonempty:
        return ""
    return " + ".join(nonempty)

def build_glossary_table(abbreviations: list[str], glossary_dict: dict, enable_decomp: bool) -> pd.DataFrame:
    # frequency
    freq: dict[str, int] = {}
    for abbr in abbreviations:
        freq[abbr] = freq.get(abbr, 0) + 1

    rows = []
    for abbr, count in sorted(freq.items(), key=lambda x: (-x[1], x[0])):
        meaning = glossary_dict.get(abbr, "")
        parts = decompose_abbr(abbr) if enable_decomp else []
        parts_str = ".".join(parts) if parts else ""
        parts_meaning = meaning_for_parts(parts, glossary_dict) if enable_decomp else ""

        rows.append({
            "Abbreviation": abbr,
            "Meaning": meaning,
            "Count": count,
            "Parts": parts_str,                  # e.g., PTCP.PAST -> PTCP.PAST parts shown as "PTCP.PAST"? No: "PTCP.PAST" parts are "PTCP.PAST"? we store joined: "PTCP.PAST" minus original => "PTCP.PAST" becomes "PTCP.PAST"? Actually parts are ["PTCP","PAST"] -> "PTCP.PAST"
            "Parts meaning": parts_meaning       # e.g., "participle + past"
        })

    df = pd.DataFrame(rows)

    # If decomposition disabled, hide columns by returning only core columns
    if not enable_decomp:
        df = df[["Abbreviation", "Meaning", "Count"]]
    else:
        # keep a sensible column order
        df = df[["Abbreviation", "Meaning", "Count", "Parts", "Parts meaning"]]

    return df


# =========================
# 5) Streamlit UI
# =========================
st.set_page_config(page_title="Glossary Generator", layout="wide")
st.title("📌 グロス略号辞書（Abbreviation Glossary）生成")

# Session state for the input box (so Clear can wipe it)
if "input_text" not in st.session_state:
    st.session_state["input_text"] = """(1) aravakaš-lar ġala-ni bozor-ġa al-ïb bor-a
coachman-PL grain-ACC bazaar-DAT take-CVB.SEQ go-CVB.CNT
yat-ïb=dur.
lie-PROG=3SG
「御者は穀物をバザールに持って行っているところだ。」
"""

top_left, top_right = st.columns([1, 1])
with top_left:
    if st.button("🧹 Clear（入力を消去）"):
        st.session_state["input_text"] = ""
        st.rerun()

with top_right:
    show_gloss_lines = st.checkbox("抽出されたグロス行を表示（事故防止のためデフォルトOFF）", value=False)

text_input = st.text_area(
    "📥 ここにテキストを貼り付けてください",
    key="input_text",
    height=260
)

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    min_hyphen_tokens = st.number_input("グロス行判定：ハイフン語数", min_value=1, max_value=10, value=2)
with col2:
    enable_decomp = st.checkbox("略号を階層分解（PTCP.PAST → PTCP + PAST）", value=True)
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

    abbreviations = extract_abbreviations_from_gloss_lines(gloss_lines)
    if not abbreviations:
        st.warning("略号が見つかりませんでした。テキスト形式を確認してください。")
        st.stop()

    df = build_glossary_table(abbreviations, DEFAULT_GLOSSARY, enable_decomp=enable_decomp)

    st.subheader("✅ 略号一覧（Meaningは編集可能）")
    edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

    csv = edited_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ CSVとしてダウンロード",
        data=csv,
        file_name="abbreviation_glossary.csv",
        mime="text/csv"
    )
