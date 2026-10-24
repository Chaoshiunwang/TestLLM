# 學測英文單字＋字根地圖

以 `copper0722/gsat-vocabulary-map` 為參考，加入字根查詢、8 類字根分類、卡片字根說明，以及「今日 20 字」的字根分類練習。

## 功能
- 查單字、中文、字根、字根中文義、構詞拆解、字根分類。
- 單字卡直接顯示字根分類與構詞說明。
- 今日 20 字保留「補地基／高報酬／長尾挑戰」。
- 新增 8 類字根：感官動作、身體器官、手部動作、腳部動作、移動、展延或開合、各類動作、部分與全部。
- 候選字根會顯示「候選」，避免把字母巧合誤當成確定字源。
- 進度存在瀏覽器 LocalStorage，可匯出 JSON。

## 資料重建
```bash
python -m scripts.build_data
python scripts/enrich_roots.py
```

## GitHub Pages
repo 已附 `.github/workflows/pages.yml`。在 Settings → Pages 將 Source 設為 GitHub Actions 後即可部署。

## 來源
資料重建流程與官方來源快照沿用參考專案的可稽核設計；詳見 `NOTICE.md`。
