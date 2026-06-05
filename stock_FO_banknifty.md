# AstraOS — Stock, F&O & Bank Nifty Master Reference

## Knowledge Sources (Institutional-Grade)

### Value Investing & Stock Analysis
| # | Book | Author | Core Skill |
|---|---|---|---|
| 1 | Security Analysis, 7th Ed | Graham, Dodd, Klarman | Deep fundamental equity analysis |
| 2 | Investment Valuation, 4th Ed | Aswath Damodaran | DCF, relative, real-option models |
| 3 | Financial Statement Analysis for Value Investing | Penman, Pope | Accounting → stock edge |
| 4 | Valuation, 8th Ed (McKinsey) | Koller, Goedhart, Wessels | Institutional company analysis |
| 5 | Financial Shenanigans, 4th Ed | Schilit, Perler, Engelhart | Accounting fraud detection |
| 6 | Common Stocks & Uncommon Profits | Philip Fisher | Business quality & scuttlebutt |
| 7 | Expected Returns | Antti Ilmanen | Factor returns & allocation |
| 8 | Asset Management | Andrew Ang | Systematic factor investing |
| 9 | Trading and Exchanges | Larry Harris | Market microstructure |
| 10 | The Intelligent Investor | Benjamin Graham | Investment philosophy |

### F&O, Options & Bank Nifty
| # | Book | Author | Core Skill |
|---|---|---|---|
| 1 | Option Volatility & Pricing, 2nd Ed | Natenberg | IV, Greeks, risk, position mgmt |
| 2 | Options as a Strategic Investment, 5th Ed | McMillan | Structures, hedging, spreads |
| 3 | Trading Options Greeks, 2nd Ed | Passarelli | Delta, gamma, theta, vega mgmt |
| 4 | Volatility Trading, 2nd Ed | Sinclair | IV forecasting, stat edge |
| 5 | Technical Analysis of Financial Markets | Murphy | Charts, indicators, timing |
| 6 | Mind Over Markets | Dalton, Jones, Dalton | Market profile, auction theory |
| 7 | High Probability Trading Strategies | Miner | Entry-to-exit trade plans |
| 8 | Japanese Candlestick Charting | Nison | Pattern reading |
| 9 | Trading in the Zone | Douglas | Psychology & discipline |
| 10 | Dynamic Hedging | Taleb | Exotic options, tail risk |

### India-Specific Certifications
- NSE NCFM Derivatives Market (Dealers)
- NSE NCFM Options Trading Strategies
- NSE NCFM Options Trading (Advanced)
- NSE NCFM Derivatives (Advanced)
- NISM-VIII Equity Derivatives Certification
- Zerodha Varsity: Futures, Options Theory, Strategies, Technical Analysis

---

## Bank Nifty Trading Framework

### 3 Core Setups (Master These Only)

#### 1. Trend Day Setup
- **Identification**: Gap open > 100pts, OI buildup in direction, ADX > 25
- **Entry**: Pullback to VWAP or previous support/resistance flip
- **Options**: Buy ATM/slightly ITM CE (bullish) or PE (bearish)
- **Stop**: Below/above opening range
- **Target**: 1.5-2x ATR or trailing stop at VWAP
- **Risk**: Max 1% of capital per trade

#### 2. Opening Range Breakout/Failure
- **Identification**: First 15-min high/low defines range
- **Entry**: Break above high (buy) or below low (sell) with volume
- **Failure**: Re-entry into range after false break = fade trade
- **Options**: Directional debit spread (limited risk)
- **Stop**: Opposite end of opening range
- **Target**: Range width projected from breakpoint

#### 3. Range Day Premium Selling
- **Identification**: No clear trend, VIX normal, narrow opening range
- **Entry**: Sell OTM strangle or iron condor at ±2σ strikes
- **Adjustment**: Roll tested side if Bank Nifty approaches short strike
- **Stop**: Close if short strike breached; max loss = 2x premium received
- **Target**: 50-70% of premium collected

### Regime Classification for Strategy Selection
| Regime | VIX | Bank Nifty Behavior | Best Strategy |
|---|---|---|---|
| Trending | 12-18 | Strong directional | Setup 1: trend following |
| Breakout | 18-25 | Volatile, directional | Setup 2: breakout/failure |
| Range | < 15 | Sideways, mean-reverting | Setup 3: premium selling |
| Crisis | > 25 | High vol, gap moves | Reduce size or sit out |
| Expiry | Any | Thursday gamma squeeze | Directional scalp + tight SL |

### F&O Lot Sizes
- NIFTY: 25 × ₹24,750 = ~₹6.2L notional
- BANKNIFTY: 15 × ₹52,000 = ~₹7.8L notional
- FINNIFTY: 25 × ₹24,000 = ~₹6.0L notional

### 90-Day Study Roadmap
**Days 1-30**: Market structure (NSE Derivatives + Zerodha TA + Futures)
**Days 31-60**: Options mastery (Zerodha Options Theory + Natenberg)
**Days 61-90**: Strategy framework (Advanced modules + Greeks + paper trading)

---

## Value Investing Checklist (Graham-Dodd-Fisher-Damodaran)

### Quantitative Screens (Graham)
- [ ] P/E < 15 (or < industry median)
- [ ] P/B < 1.5 (or P/E × P/B < 22.5)
- [ ] Current ratio > 2.0
- [ ] Debt/Equity < 0.5
- [ ] 10-year earnings growth > 0
- [ ] Dividend history > 5 years

### Business Quality (Fisher)
- [ ] Does the company have products/services with market potential?
- [ ] Is management determined to develop new products?
- [ ] How effective is the company's R&D relative to size?
- [ ] Does the company have an above-average sales organization?
- [ ] Does the company have a worthwhile profit margin?
- [ ] Is management transparent with investors during setbacks?

### Financial Shenanigans Red Flags (Schilit)
- [ ] Revenue growing much faster than cash from operations
- [ ] Large "other income" or one-time gains inflating profit
- [ ] Rising DSO (days sales outstanding)
- [ ] Aggressive capitalization of expenses
- [ ] Sudden accounting policy changes
- [ ] Related-party transactions > 5% of revenue
- [ ] Auditor changes or qualification

### DCF Valuation Framework (Damodaran)
1. Estimate free cash flow (FCFF or FCFE)
2. Project growth rate (historical, analyst consensus, sustainable)
3. Determine WACC (cost of equity via CAPM + cost of debt)
4. Calculate terminal value (Gordon growth or exit multiple)
5. Discount to present value
6. Margin of safety: buy only at > 25% discount to intrinsic value
