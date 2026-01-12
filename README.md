グロス略号辞書生成アプリ
Gloss Abbreviation Glossary Generator

本アプリは、言語学的なグロス付き例文（IGT）から
略号（ACC, PL, 3SG, PTCP.PAST など）を自動抽出し、
略号一覧（Abbreviation Glossary）を生成する Web アプリです。

研究・論文執筆・教材作成を主な用途として設計されています。

────────────────────────
主な機能
────────────────────────

1. グロス略号の自動抽出
- ハイフン「-」およびイコール「=」を含む語を持つ行を
  グロス行として自動判定
- 例：
  lie-PROG=3SG
  → PROG, 3SG

2. 略号の階層分解（ON/OFF 切替）
- ドット分解
  PTCP.PAST → PTCP, PAST
- 人称・数分解
  3SG → 3, SG
  2PL.POSS → 2PL, POSS, 2, PL

3. 自動意味補完
- 1 / 2 / 3 → 1st / 2nd / 3rd person
- SG / PL / ACC / DAT などは内蔵辞書で自動補完
- 未定義略号は空欄のまま表示（後で編集可能）

4. 略号カテゴリ分類
- person, number, case, tense/aspect/mood などを自動付与
- 略号辞書CSVに Category 列があればそれを優先

5. 略号辞書CSVの取り込み（任意）
- 既存の略号一覧CSVをアップロード可能
- 必須列：Abbreviation, Meaning
- 任意列：Category
- 文字コードは UTF-8 / UTF-8-BOM / CP932 / Shift_JIS に自動対応

6. CSVとしてダウンロード
- 編集後の略号一覧をCSVで保存
- 保存したCSVは次回以降、辞書として再利用可能

7. 安全設計
- 入力した例文テキストは一切保存されません
- ページ更新・再起動で内容は消去されます
- CSVは利用者のローカル環境にのみ保存されます

────────────────────────
公開形態
────────────────────────

- Streamlit Community Cloud 上で稼働
- アプリ内パスワード認証あり（Secrets使用）
- URLを知っていてもパスワードなしでは利用不可

────────────────────────
使い方
────────────────────────

1. テキスト欄にグロス付き例文を貼り付ける
2. （任意）略号辞書CSVをサイドバーからアップロード
3. 「Glossary生成」をクリック
4. 略号一覧を確認・編集
5. CSVとしてダウンロード

────────────────────────
対応する入力例
────────────────────────

lie-PROG=3SG
read-PTCP.PAST
side-3.POSS-LOC

分解ON時の出力例：

Category: person
Abbreviation: 3
Meaning: 3rd person

Category: number
Abbreviation: SG
Meaning: singular

Category: tense/aspect/mood
Abbreviation: PROG
Meaning: progressive

────────────────────────
設計方針
────────────────────────

- Leipzig Glossing Rules を意識した略号処理
- 未公開コーパスでも安全に使用可能
- 「貼る → 一覧 → CSV → 終了」の一時利用を前提

────────────────────────
技術情報
────────────────────────

- Python 3.10 以上
- Streamlit
- pandas

────────────────────────
ライセンス
────────────────────────

研究・教育目的での利用を想定。
必要に応じてライセンスを明示してください（例：MIT License）。

────────────────────────
作者
────────────────────────

日髙　晋介（ひだか　しんすけ；筑波大学　人文社会系）
