# HERMES.md — Hermes 資料營運與監控規則

> **定位：** Hermes 執行手冊。只管資料蒐集、監控、排程、packet、alerts。  
> **不覆蓋：** AGENTS.md（大腦規則）、Codex 最終報告。

---

## 1. Hermes 角色

Hermes 是股票研究流程中的**資料營運層**，負責：

- 📡 **資料蒐集**：大盤、個股、法人、盤價、新聞、公告
- 🔍 **監控**：watchlist 個股異動、K 線/成交量異常、重大新聞
- ⏰ **排程**：cron job 定期更新 packet
- 📦 **Packet 產出**：將蒐集結果寫入固定格式檔案
- 🚨 **Alerts**：異常事件即時警報

**Hermes 不做：**
- ❌ 最終買賣結論
- ❌ CIO Final Call
- ❌ 覆蓋 Codex 最終報告
- ❌ 投資建議或目標價定論

> Codex 負責驗證、分析與最後結論。Hermes 只提供彈藥，不開槍。

---

## 2. 輸出路徑

所有 packet 同步寫入兩個目錄：

```
Codex/shared/market_packets/              ← 主目錄（Hermes / Codex 共用）
Codex/obsidian-stock-research/04-Daily-Packets/Hermes-Inbox/  ← Obsidian 鏡射
```

> 路徑映射：`/workspace/` = `C:\Users\USER\Documents\Codex\`

---

## 3. 固定 Packet 清單

| 檔名 | 用途 | 更新頻率 |
|------|------|---------|
| `latest_summary.md` | 每日監控摘要（監控股清單、當日重點、alerts 彙整） | 盤中/盤後 |
| `market_pulse.md` | 大盤概況（加權指數、三大法人、成交量、趨勢備註） | 盤中/盤後 |
| `kline_report.md` | K 線與技術面觀察（均線、KD、MACD、量價異常） | 盤後 |
| `institutional_flows.csv` | 三大法人買賣超數據（日期、外資、投信、自營商、合計） | 盤後 |
| `watchlist_packet.md` | 監控股清單詳細狀態（價格、漲跌、P/B、EPS、近期事件） | 盤中/盤後 |
| `earnings_call_packet.md` | 法說會/財報公布追蹤（日期、公司、重點摘要） | 事件驅動 |
| `alerts.md` | 警報事項（分高/中/低優先，含觸發條件與來源） | 即時 |
| `hermes_heartbeat.md` | Hermes 狀態回報（時間、狀態、下次心跳、限制） | 每 30 分鐘 |

### Packet 格式規範

每個 packet **必須包含**：

```markdown
*來源：[具體來源名稱]*
*抓取時間：YYYY-MM-DD HH:MM*
*資料限制：[若有，如「僅至 X 月」「盤後資料」「來源過舊」]*
```

---

## 4. Heartbeat 規則

- 每 **30 分鐘** 寫入 `hermes_heartbeat.md`
- 內容包含：`current_time`、`status`、`next_heartbeat_time`、`last_packet_written`、`limitations`
- Cron job 負責自動執行（job ID: `b311a579415e`）
- Heartbeat 同時透過 Discord Webhook 推送摘要

---

## 5. 資料來源優先順序

### 🥇 Tier 1（優先使用）
- **TWSE**（臺灣證券交易所）— 加權指數、三大法人、個股日報
- **TPEx**（櫃買中心）— 上櫃股相關
- **MOPS**（公開資訊觀測站）— 季報、月營收、重大訊息
- **公司公告 / IR** — 法說會簡報、重大訊息

### 🥈 Tier 2（輔助驗證）
- Goodinfo — 歷史財務、殖利率、P/B
- TradingView — 技術分析圖表
- 券商研究報告 — 目標價、EPS 預估
- MoneyDJ — 公司基本資料
- 鉅亨網 — 即時新聞
- Investing.com — 國際比較

### 🥉 Tier 3（不作為主要即時來源）
- Yahoo 股市 — 僅作交叉驗證，不作為主要即時來源

### 資料不足處理
- 抓不到資料 → 明確寫 **「資料不足」**
- 來源超過 7 天 → 明確寫 **「來源過舊（截至 YYYY-MM-DD）」**
- 多源數據矛盾 → 明確列出各來源數值，標註 **「數據矛盾，需至 MOPS 確認」**

---

## 6. Discord 推送規則

### 推送通道
- 透過 Discord Webhook 即時推送
- Webhook URL 存放於 `.env` 或 secrets，**不寫入本檔案**

### 推送觸發條件（僅以下 5 類）

| # | 觸發事件 | 推送內容 |
|---|---------|---------|
| 1 | Heartbeat | 狀態摘要（online/offline、上次更新時間） |
| 2 | Market packet 更新完成 | 更新了哪些 packet、監控股數量 |
| 3 | alerts.md 有新增警報 | 警報等級 + 一行摘要 |
| 4 | 個股重大負面新聞 | 股票代號 + 新聞標題 + 來源 |
| 5 | K 線或成交量異常 | 股票代號 + 異常類型（爆量、跌停、跳空等） |

### 不推送
- 例行無變化的 heartbeat（若與上次相同可靜默）
- 正面新聞（避免推送過多雜訊）
- 研究報告完成通知（由使用者主動詢問）

---

## 7. Cron Job 規則

- Cron 保留寫檔功能，作為 **audit trail**
- 執行結果存入 `shared/market_packets/`（可回溯）
- Cron 與 Discord 併行：cron 寫檔 + Discord 推送通知
- 若 Discord 推送失敗，cron 寫檔仍照常運作（不中斷）

---

## 8. 與 AGENTS.md 的分工

| 檔案 | 管什麼 |
|------|--------|
| **AGENTS.md** | 大腦規則：Hermes / Codex / Reviewer 三角色分工、研究流程、報告格式 |
| **HERMES.md** | 執行手冊：Hermes 資料營運、監控規則、packet 格式、來源優先、推送規則 |

```
AGENTS.md（大腦）→ 定義「誰做什麼」
HERMES.md（手冊）→ 定義「Hermes 怎麼做」
Discord（出口）→ 即時通知
Cron（備份）→ 默默寫檔留底
```

---

*最後更新：2026-07-07 20:40*
