import os
import hmac
import streamlit as st

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

import re
import streamlit as st
import pandas as pd

# ---------------------------------------------------
# 1) 基本略号辞書（必要に応じて増やす）
# ---------------------------------------------------
DEFAULT_GLOSSARY = {
    "ACC": "accusative",
    "DAT": "dative",
    "GEN": "genitive",
    "ABL": "ablative",
    "LOC": "locative",
    "INS": "instrumental",
    "PL": "plural",
    "SG": "singular",
    "POSS": "possessive",
    "IMP": "imperative",
    "PROG": "progressive",
    "Q": "question particle",
    "VN": "verbal noun",

    # person/number shorthand
    "1": "1st person",
    "2": "2nd person",
    "3": "3rd person",
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
    "PTCP": "participle",
    "PTCP.PAST": "past participle",
    "PTCP.NPST": "non-past participle",
    "CVB": "converb",
    "CVB.SEQ": "sequential converb",
    "CVB.CNT": "continuative converb",
}

# ---------------------------------------------------
# 2) グロス行抽出（ノイズ除去）
# ---------------------------------------------------
def extract_gloss_lines(text, min_hyphen_tokens=2):
    """
    「グロス行っぽい行」だけを抽出する。
    ルール：ハイフン付きトークンが一定数以上含まれる行をグロス行とみなす。
    """
    gloss_lines = []
    for line in text.splitlines():
        line_strip = line.strip()
        if not line_strip:
            continue

        # ハイフンを含むトークン数
        tokens = re.split(r"\s+", line_strip)
        hyphen_tokens = [t for t in tokens if "-" in t]

        # 例: coachman-PL grain-ACC bazaar-DAT ...
        if len(hyphen_tokens) >= min_hyphen_tokens:
            gloss_lines.append(line_strip)

    return gloss_lines


# ---------------------------------------------------
# 3) 略号抽出
# ---------------------------------------------------
ABBR_PATTERN = re.compile(r"^(?:[0-9]*[A-Z]+(?:\.[A-Z0-9]+)*)$")

def extract_abbreviations_from_gloss_lines(gloss_lines):
    """
    グロス行から略号を抽出する。
    ・単語をハイフンやイコールで割り、後半側を候補にする
    ・さらに '.' 区切りで複合略号も拾う
    """
    abbreviations = []

    for line in gloss_lines:
        # 記号で分割（空白、タブ）
        tokens = re.split(r"\s+", line)

        for token in tokens:
            # まず "=" を分割
            parts_eq = token.split("=")
            for peq in parts_eq:
                # "-" で分割（最初は語幹なので後ろ側を主に見る）
                parts_hy = peq.split("-")

                # 2PL.POSS-GEN みたいな場合
                for ph in parts_hy[1:]:  # 後ろ側だけ
                    ph = ph.strip(".,;:()[]{}\"'")

                    # さらに "." で複合略号を拾う（PTCP.PASTなど）
                    # "2PL.POSS" はそのまま1つとしても採る
                    if ABBR_PATTERN.match(ph):
                        abbreviations.append(ph)

                    # もし "2PL.POSS" 内の要素も欲しければ分割して拾う:
                    # 例: 2PL.POSS → 2PL, POSS も拾う
                    if "." in ph:
                        subparts = ph.split(".")
                        for sp in subparts:
                            if ABBR_PATTERN.match(sp):
                                abbreviations.append(sp)

    return abbreviations


def build_glossary_table(abbreviations, glossary_dict):
    """
    略号リストから (Abbreviation, Meaning, Count) テーブルを作る
    """
    freq = {}
    for abbr in abbreviations:
        freq[abbr] = freq.get(abbr, 0) + 1

    rows = []
    for abbr, count in sorted(freq.items(), key=lambda x: (-x[1], x[0])):
        meaning = glossary_dict.get(abbr, "")
        rows.append({"Abbreviation": abbr, "Meaning": meaning, "Count": count})

    return pd.DataFrame(rows)


# ---------------------------------------------------
# Streamlit UI
# ---------------------------------------------------
st.set_page_config(page_title="Glossary Generator", layout="wide")
st.title("📌 グロス略号辞書（Abbreviation Glossary）自動生成アプリ")

st.markdown("""
このアプリは以下を自動で行います：

✅ **グロス行だけを抽出**（訳文・参考文献などのノイズを除外）  
✅ **略号を抽出**（ACC, PL だけでなく **1PL, 3SG, 2PL.POSS, PTCP.PAST** なども拾う）  
✅ **略号→意味を自動補完**（辞書にあるものはMeaningが自動入力）  
✅ **表を編集してCSVで出力**
""")

example_text = """(1) aravakaš-lar ġala-ni bozor-ġa al-ïb bor-a
coachman-PL grain-ACC bazaar-DAT take-CVB.SEQ go-CVB.CNT
yat-ïb=dur.
lie-PROG=3SG
「御者は穀物をバザールに持って行っているところだ。」
"""

text_input = st.text_area("📥 ここにテキストを貼り付けてください", value=example_text, height=260)

col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    min_hyphen_tokens = st.number_input("グロス行判定：ハイフン語数", min_value=1, max_value=10, value=2)

with col2:
    run_button = st.button("🔍 Glossary生成")

if run_button:
    gloss_lines = extract_gloss_lines(text_input, min_hyphen_tokens=min_hyphen_tokens)

    st.subheader("✅ 抽出されたグロス行")
    if gloss_lines:
        st.code("\n".join(gloss_lines))
    else:
        st.warning("グロス行が見つかりませんでした。ハイフン語数の閾値を下げると改善する場合があります。")
        st.stop()

    abbreviations = extract_abbreviations_from_gloss_lines(gloss_lines)
    if not abbreviations:
        st.warning("略号が見つかりませんでした。テキスト形式を確認してください。")
        st.stop()

    df = build_glossary_table(abbreviations, DEFAULT_GLOSSARY)

    st.subheader("✅ 略号一覧（Meaningは編集可能）")
    edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")

    # CSVダウンロード
    csv = edited_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ CSVとしてダウンロード",
        data=csv,
        file_name="abbreviation_glossary.csv",
        mime="text/csv"
    )
