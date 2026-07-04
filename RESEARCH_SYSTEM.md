# Investment Research System Roadmap

This project is intended to evolve from a basic stock screener into an
investment research system for Taiwan equities, semiconductors, AI
infrastructure, robotics, and related supply chains.

The system should combine market data, company fundamentals, industry research,
news, and analyst-style reasoning into repeatable research workflows.

## Target Outcome

The long-term goal is to generate structured research output such as:

- Stock screening results
- Supply-chain maps
- Company comparison tables
- Fundamental quality scores
- Valuation scenarios
- Risk summaries
- Analyst-style research notes

The system should help answer questions like:

- Which Taiwan stocks benefit from a specific semiconductor or AI trend?
- Where does a company sit in the supply chain?
- Is the stock driven by short-term market hype or durable fundamentals?
- What valuation range is reasonable under conservative, base, and optimistic
  assumptions?
- What risks could break the investment thesis?

## Data Sources

Start with sources that are accessible and useful for Taiwan equity research.

| Source | Role | Notes |
|---|---|---|
| TWSE OpenAPI | Official Taiwan listed stock data | Includes listed company data, daily trading data, PER/PBR, monthly revenue, financial statements, major announcements, and ESG-related datasets. |
| MOPS | Official company filings and announcements | Useful for financial reports, material information, and public company disclosures. |
| FinMind | Fast development data layer | Offers Taiwan market technical, fundamental, institutional, derivatives, real-time, and news datasets. Good for early prototyping. |
| Company IR pages | Primary company context | Useful for presentations, earnings calls, product strategy, and investor materials. |
| Industry news and reports | Trend detection | Useful for AI servers, advanced packaging, robotics, memory, foundry, equipment, and materials themes. |

Reference links:

- [TWSE OpenAPI](https://openapi.twse.com.tw/)
- [FinMind documentation](https://finmind.github.io/en/)

## System Layers

### 1. Data Collection Layer

Collect raw data from multiple sources:

- Daily price and volume
- PER, PBR, dividend yield
- Monthly revenue
- Income statement, balance sheet, cash flow
- Institutional investor activity
- Major announcements
- Company basic information
- Industry and supply-chain notes

Early implementation can use CSV files. Later versions should move to a local
database such as SQLite.

### 2. Data Cleaning Layer

Normalize all inputs into consistent formats:

- Stock code
- Company name
- Industry category
- Supply-chain category
- Report period
- Currency
- Revenue, margin, EPS, cash flow, and valuation fields

The system should keep raw data separate from cleaned data so errors can be
traced back to their source.

### 3. Supply-Chain Mapping Layer

Each company should eventually have tags such as:

- Foundry
- IC design
- Semiconductor equipment
- Materials
- PCB and substrate
- Advanced packaging
- AI server
- Robotics component
- Automation equipment
- Thermal solution
- Power supply
- Connector and cable

The goal is to answer not only whether a stock is strong, but why it benefits
from a trend.

### 4. Fundamental Analysis Layer

Score companies using financial and business quality indicators:

- Revenue growth
- Gross margin and operating margin
- EPS trend
- Free cash flow
- Debt level
- Inventory risk
- Customer concentration
- Capital expenditure cycle
- Dividend policy
- Historical valuation range

The model should separate:

- Quality
- Growth
- Valuation
- Momentum
- Risk

### 5. Valuation Layer

Use different valuation methods depending on company type:

| Company Type | Primary Valuation Method |
|---|---|
| Stable dividend stocks | Dividend yield, PE, PB |
| Semiconductor leaders | PE, EV/EBITDA, DCF |
| Cyclical component makers | Mid-cycle PE, PB, margin normalization |
| High-growth AI or robotics names | Revenue growth, margin path, scenario analysis |
| Asset-heavy manufacturers | PB, ROE, cash flow cycle |

Every valuation output should include:

- Conservative case
- Base case
- Optimistic case
- Key assumptions
- Downside risks

### 6. Research Report Layer

The final output should follow a repeatable research format:

1. Investment conclusion
2. Industry trend
3. Supply-chain position
4. Company fundamentals
5. Valuation
6. Catalysts
7. Risks
8. Watchlist decision

Decision labels:

- Worth tracking
- Wait for a better entry
- High risk

## Development Phases

### Phase 1: Better Screener

- Add more sample Taiwan stocks
- Add industry and supply-chain tags
- Add valuation columns
- Export results to CSV or Excel

### Phase 2: Data Import

- Add TWSE or FinMind data import
- Store data in SQLite
- Add update commands for price, revenue, and valuation data

### Phase 3: Semiconductor Research Engine

- Build supply-chain category mapping
- Add company comparison reports
- Add semiconductor theme screens such as AI server, advanced packaging,
  robotics, and equipment

### Phase 4: Report Generator

- Generate Markdown research notes
- Add conservative, base, and optimistic valuation scenarios
- Add risk and catalyst sections

### Phase 5: Dashboard

- Build a web dashboard
- Add filters by sector, supply-chain role, valuation, growth, and risk
- Add watchlist management

## Near-Term Priority

The next useful upgrade is to add supply-chain category fields to the sample
CSV and make the screener rank stocks by:

- Fundamental score
- Valuation score
- Momentum score
- Supply-chain theme

This keeps the project simple while moving it toward a true research system.
