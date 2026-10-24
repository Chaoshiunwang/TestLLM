# 學測英文單字＋字根地圖

以 [copper0722/gsat-vocabulary-map](https://github.com/copper0722/gsat-vocabulary-map) 為參考，保留「補地基／高報酬／長尾挑戰」與今日 20 字的學習模式，新增字根搜尋、卡片字根資訊與 8 類字根練習。

## 新增功能

- 單字搜尋同時搜尋字根家族、核心字根、字根中文義與字根分類。
- 單字卡直接顯示「字根分類＋字根說明」。
- 詳細視窗顯示字根家族、拆解、構詞說明與分析可信度。
- 今日 20 字保留：
  - 補地基
  - 高報酬
  - 長尾挑戰
- 另增加 8 類字根選單：
  1. 感官動作
  2. 身體器官
  3. 手部動作
  4. 腳部動作
  5. 移動
  6. 展延或開合
  7. 各類動作
  8. 部分與全部
- 短字根與容易誤判的字形標為「候選」，避免把字母巧合當成確定字源。
- 學習進度只存在瀏覽器 LocalStorage，可匯出 JSON。

## 資料來源

網站優先讀取 repo 內的 `data/vocabulary.json`；若本機沒有資料，會退回讀取原專案公開資料。

下載本機資料：

```bash
bash scripts/fetch-data.sh
python3 -m http.server 8000
```

然後打開 `http://localhost:8000/`。

## GitHub Pages

已附 Pages workflow。合併到 `main` 後，在 **Settings → Pages → Source** 選擇 **GitHub Actions**。

## 字根分析原則

本版採 32 組高頻核心字根與 8 個上位分類。字根功能以高中記憶輔助為目的，不把所有英文字都強制拆解。介面中：

- 一般字根：可作主要構詞線索。
- 「候選」：只表示字形可能相關，建議再用可靠字典／字源工具複核。

## Attribution

原始詞頻資料與學習路線概念來自 `copper0722/gsat-vocabulary-map`（MIT）。本專案重新撰寫前端與字根分析模組，並保留來源與權利說明。
