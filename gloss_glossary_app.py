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
# 1) Base Glossary
# =========================
BASE_GLOSSARY = {
    "1": "1st person",
    "2": "2nd person",
    "3": "3rd person",

    "SG": "singular",
    "PL": "plural",
    "POSS": "possessive",

    "ACC": "accusative",
    "DAT": "dative",
    "GEN": "genitive",
    "ABL": "ablative",
    "LOC": "locative",
    "INS": "instrumental",

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

    "PTCP.PAST": "past participle",
    "PTCP.NPST": "non-past participle",
    "CVB.SEQ": "sequential converb",
    "CVB.CNT": "continuative converb",

    "1SG": "1st person singular",
    "2SG": "2nd person singular",
    "3SG": "3rd person singular",
    "1PL": "1st person plural",
    "2PL": "2nd person plural",
    "3PL": "3rd person plural",
}

# category sets (used as fallback when CSV doesn't provide Category)
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
    if re.fullmatch(r"[0-9]+", abbr):
        return "person"
    if re.fullmatch(r"[0-9]+[A-Z]+", abbr):
        return "agreement"
    if "." in abbr:
        return "compound"
    return ""


# =========================
# 2) Load glossary CSV (optional)
# =========================
def load_glossary_csv(uploaded_file) -> tuple[dict, dict]:
    """
    Returns:
      (abbr_to_meaning, abbr_to_category)
    Accepts CSVs with at least Abbreviation, Meaning.
    Category is optional.
    """
    df = pd.read_csv(uploaded_file)
    cols = {c.lower(): c for c in df.columns}

    if "abbreviation" not in cols:
        raise ValueError("CSVに 'Abbreviation' 列が見つかりません。")
    if "meaning" not in cols:
        raise ValueError("CSVに 'Meaning' 列が見つかりません。")

    abbr_col = cols["abbreviation"]
    meaning_col = cols["meaning"]
    cat_col = cols.get("category")

    abbr_to_meaning = {}
    abbr_to_category = {}

    for _, row in df.iterrows():
        abbr = str(row.get(abbr_col, "")).strip()
        if not abbr:
            continue
        meaning = str(row.get(meaning_col, "")).strip()
        if meaning and meaning.lower() != "nan":
            abbr_to_meaning[abbr] = meaning
        if cat_col:
            cat = str(row.get(cat_col, "")).strip()
            if cat and cat.lower() != "nan":
                abbr_to_category[abbr] = cat

    return abbr_to_meaning, abbr_to_category


# =========================
# 3) Gloss line extraction (noise reduction) '-' OR '='
# =========================
def extract_gloss_lines(text: str, min_marked_tokens: int = 2) -> list[str]:
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
# 4) Abbreviation extraction + decomposition (handles '-' and '=')
# =========================
ABBR_PATTERN = re.compile(r"^(?:[0-9]*[A-Z]+(?:\.[A-Z0-9]+)*)$")
NUM_ALPHA_PATTERN = re.compile(r"^([0-9]+)([A-Z]+)$")  # 3SG -> 3 + SG

def _add_decomposed_units(abbr: str, out: list[str]) -> None:
    dot_parts = abbr.split(".") if "." in abbr else [abbr]
    for part in dot_parts:
        part = part.strip()
        if not part:
            continue
        if ABBR_PATTERN.match(part):
            out.append(part)
        m = NUM_ALPHA_PATTERN.match(part)
        if m:
            out.append(m.group(1))  # 3
            out.append(m.group(2))  # SG

def extract_abbreviations_from_gloss_lines(gloss_lines: list[str], enable_decomp: bool) -> list[str]:
    abbreviations: list[str] = []

    for line in gloss_lines:
        tokens = re.split(r"\s+", line)
        for token in tokens:
            eq_parts = token.split("=")
            for part_eq in eq_parts:
                part_eq = part_eq.strip(".,;:()[]{}\"'")

                # whole segment itself (e.g., "3SG")
                if ABBR_PATTERN.match(part_eq):
                    abbreviations.append(part_eq)
                    if enable_decomp:
                        _add_decomposed_units(part_eq, abbreviations)

                # hyphen suffixes (e.g., lie-PROG -> PROG)
                parts_hy = part_eq.split("-")
                for suf in parts_hy[1:]:
                    suf = suf.strip(".,;:()[]{}\"'")
                    if not ABBR_PATTERN.match(suf):
                        continue
                    abbreviations.append(suf)
                    if enable_decomp:
                        _add_decomposed_units(suf, abbreviations)

    return abbreviations


# =========================
# 5) Table builder (uses merged glossary + optional category overrides)
# =========================
def build_glossary_table(abbreviations: list[str], abbr_to_meaning: dict, abbr_to_category: dict) -> pd.DataFrame:
    freq: dict[str, int] = {}
    for abbr in abbreviations:
        freq[abbr] = freq.get(abbr, 0) + 1

    rows = []
    for abbr, count in sorted(freq.items(), key=lambda x: (-x[1], x[0])):
        meaning = abbr_to_meaning.get(abbr, "")
        category = abbr_to_category.get(abbr, "") or categorize_abbr(abbr)
        rows.append({
            "Category": category,
            "Abbreviation": abbr,
            "Meaning": meaning,
            "Count": count,
        })

    return pd.DataFrame(rows)[["Category", "Abbreviation", "Meaning", "Count"]]


# =========================
# 6) Streamlit UI
# =========================
st.set_page_config(page_title="Glossary Generator", layout="wide")
st.title("📌 グロス略号辞書（Abbreviation Glossary）生成")

# ---- Sidebar: glossary CSV upload
st.sidebar.header("📚 略号辞書CSVの取り込み（任意）")
uploaded = st.sidebar.file_uploader("CSVをアップロード", type=["csv"])

use_uploaded_glossary = st.sidebar.checkbox("アップロードした辞書を使用", value=True)
prefer_uploaded = st.sidebar.checkbox("同じ略号がある場合、アップロード辞書を優先", value=True)

# Load uploaded glossary (if provided)
uploaded_meaning = {}
uploaded_category = {}
upload_error = None

if uploaded is not None and use_uploaded_glossary:
    try:
        uploaded_meaning, uploaded_category = load_glossary_csv(uploaded)
        st.sidebar.success(f"読み込みOK：{len(uploaded_meaning)}件（Meaning） / {len(uploaded_category)}件（Category）")
    except Exception as e:
        upload_error = str(e)
        st.sidebar.error(upload_error)

# Merge glossary meanings
if prefer_uploaded:
    # uploaded overwrites base
    MERGED_MEANING = {**BASE_GLOSSARY, **uploaded_meaning}
else:
    # base overwrites uploaded
    MERGED_MEANING = {**uploaded_meaning, **BASE_GLOSSARY}

# Categories: uploaded categories override if provided
MERGED_CATEGORY = dict(uploaded_category)  # only explicit overrides live here


# ---- Main input and controls
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
    min_marked_tokens = st.number_input("グロス行判定： '-' または '=' を含む語数", min_value=1, max_value=10, value=2)
with col2:
    enable_decomp = st.checkbox("略号を分解して個別略号も一覧化（PTCP.PAST→PTCP+PAST / 3SG→3+SG）", value=True)
with col3:
    run_button = st.button("🔍 Glossary生成", use_container_width=True)

if run_button:
    if upload_error:
        st.warning("辞書CSVの読み込みに失敗しているため、アップロード辞書は使用されません。")

    gloss_lines = extract_gloss_lines(text_input, min_marked_tokens=int(min_marked_tokens))
    if not gloss_lines:
        st.warning("グロス行が見つかりませんでした。閾値（語数）を下げると改善する場合があります。")
        st.stop()

    if show_gloss_lines:
        st.subheader("✅ 抽出されたグロス行")
        st.code("\n".join(gloss_lines))

    abbreviations = extract_abbreviations_from_gloss_lines(gloss_lines, enable_decomp=enable_decomp)
    if not abbreviations:
        st.warning("略号が見つかりませんでした。テキスト形式を確認してください。")
        st.stop()

    df = build_glossary_table(abbreviations, MERGED_MEANING, MERGED_CATEGORY)

    st.subheader("✅ 略号一覧（Category/Meaning は編集可能）")
    edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

    csv = edited_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ CSVとしてダウンロード",
        data=csv,
        file_name="abbreviation_glossary.csv",
        mime="text/csv"
    )
