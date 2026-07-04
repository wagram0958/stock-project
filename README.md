# Stock Screener

A simple stock screening project that ranks stocks by valuation, growth,
dividend yield, price trend, and trading volume.

This project is designed as a clean starter version for a GitHub portfolio or
for later expansion into a Taiwan stock screening tool.

It also includes a Codex instruction file, `AGENTS.md`, that guides future
analysis toward a semiconductor and technology supply-chain research style.
The goal is to evolve this from a simple screener into a research assistant for
Taiwan stocks, AI infrastructure, robotics, and semiconductor supply chains.

For the longer-term product direction, see `RESEARCH_SYSTEM.md`. For companies
under active financial statement and conference call monitoring, see
`EARNINGS_WATCHLIST.md`.

## Features

- Load stock fundamentals and technical indicators from a CSV file
- Screen stocks by practical investment conditions
- Generate a score for each stock
- Sort candidates by score
- Show clear reasons for why each stock passed the screen

## Screening Rules

The current screener gives points for:

| Rule | Default Condition | Points |
|---|---:|---:|
| Reasonable PE ratio | PE <= 25 | 1 |
| Revenue growth | Revenue growth >= 10% | 1 |
| Dividend yield | Dividend yield >= 3% | 1 |
| Price trend | Price > 60-day moving average | 1 |
| Volume strength | Volume ratio >= 1.2 | 1 |

The maximum score is 5.

## Project Structure

```text
.
├── AGENTS.md
├── EARNINGS_WATCHLIST.md
├── RESEARCH_SYSTEM.md
├── data/
│   └── sample_stocks.csv
├── stock_screener.py
├── requirements.txt
└── README.md
```

## Codex Analysis Framework

This repository includes an `AGENTS.md` file for Codex. When working inside
this project, Codex should use a senior semiconductor analyst style for stock
and supply-chain questions:

- Confirm industry trends and demand direction
- Map the supply chain from upstream to downstream
- Compare company fundamentals, margins, customers, and competitive position
- Separate short-term themes from long-term fundamentals
- Use valuation methods such as PE, PB, EV/EBITDA, or DCF where appropriate
- Provide conservative, base, and optimistic valuation scenarios when enough
  data is available

The current Python script is still a starter screener. The analysis framework
is intended to guide future expansion into deeper semiconductor and Taiwan
equity research.

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the screener with sample data:

```bash
python stock_screener.py
```

Run with your own CSV file:

```bash
python stock_screener.py --file data/sample_stocks.csv
```

Only show stocks with at least 4 points:

```bash
python stock_screener.py --min-score 4
```

## CSV Format

Your CSV file should include these columns:

| Column | Description |
|---|---|
| symbol | Stock ticker |
| name | Company name |
| pe_ratio | Price-to-earnings ratio |
| revenue_growth | Revenue growth percentage |
| dividend_yield | Dividend yield percentage |
| price | Latest price |
| ma60 | 60-day moving average |
| volume_ratio | Current volume divided by average volume |

Example:

```csv
symbol,name,pe_ratio,revenue_growth,dividend_yield,price,ma60,volume_ratio
2330,TSMC,22.5,18.2,2.1,980,910,1.4
```

## Example Output

```text
Top stock candidates

2330 TSMC | Score: 4/5
- PE ratio is reasonable
- Revenue growth is strong
- Price is above MA60
- Trading volume is stronger than average
```

## Roadmap

- Add Taiwan stock market data import
- Add technical indicators such as RSI and MACD
- Add industry-based ranking
- Add semiconductor supply-chain category tags
- Add valuation scenario output
- Add analyst-style report generation
- Export results to Excel
- Build a web dashboard
- Add backtesting

## Disclaimer

This project is for learning and research only. It is not financial advice.
