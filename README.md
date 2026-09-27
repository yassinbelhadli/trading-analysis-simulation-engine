# Trading Analysis & Simulation Engine

A modular trading analysis, backtesting, simulation, and execution-support platform built around ICT/SMC-style market analysis.

The project is designed as an end-to-end engineering system rather than a single trading script. It separates market analysis, setup scoring, execution simulation, risk controls, analytics, external integrations, and presentation layers into dedicated components.

> **Status:** Active portfolio project
> **Primary focus:** Trading analysis, deterministic simulation, risk controls, analytics, and system integration

---

## Overview

The system processes market data through a modular analysis pipeline and converts detected market conditions into structured trading setups that can be evaluated, simulated, analyzed, and exposed through APIs and user interfaces.

The architecture includes:

* Market structure detection
* Liquidity analysis
* Fair Value Gap (FVG) detection
* Order Block detection
* Candle and volume analysis
* Premium/discount analysis
* Setup scoring and ranking
* Entry and execution management
* Partial closes and trailing stops
* Risk and drawdown controls
* Backtesting and historical analysis
* Performance analytics
* News and fundamental-event filtering
* MT5 integration
* Telegram integration
* REST/WebSocket API components
* Authentication and security components
* Client/admin dashboard components
* Licensing and subscription infrastructure

---

## Architecture

The core analysis flow is organized around a separation between detection, decision support, execution simulation, and reporting.

```text
Market Data
    │
    ▼
┌─────────────────────────────┐
│ Market Analysis / Detection │
│                             │
│ • Market Structure          │
│ • Liquidity                 │
│ • FVG                       │
│ • Order Blocks              │
│ • Candle Patterns           │
│ • Volume Imbalance          │
│ • Premium / Discount        │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Scoring & Setup Ranking     │
│                             │
│ • Confidence Score          │
│ • Score Breakdown           │
│ • Setup Ranker              │
│ • HTF Filters               │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Entry & Execution Layer     │
│                             │
│ • Entry Manager             │
│ • Execution Engine          │
│ • Trade Manager             │
│ • Partial Close             │
│ • Break Even                │
│ • Trailing Stop             │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Risk Management             │
│                             │
│ • Lot Calculation           │
│ • Daily Loss Guard          │
│ • Drawdown Protection       │
│ • Max Loss Guard            │
│ • Trade Limits              │
│ • Symbol Validation         │
│ • Weekend Guard             │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Simulation / Backtesting    │
│                             │
│ • Historical Tests          │
│ • Execution Simulation     │
│ • Monte Carlo               │
│ • Optimization              │
│ • Trade Analysis            │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│ Analytics & Reporting       │
│                             │
│ • Performance Metrics       │
│ • Drawdown Analysis         │
│ • Win Rate                  │
│ • Profit Factor             │
│ • Setup Statistics          │
│ • Trade Statistics          │
└─────────────────────────────┘
```

---

## Core Components

### 1. Market Analysis

The detection layer contains independent modules for:

* Market structure
* Liquidity
* Fair Value Gaps
* Order Blocks
* Candle patterns
* Liquidity voids
* Premium/discount zones
* Support/resistance
* Volume imbalance

This modular design allows individual detectors to be tested and evolved independently.

### 2. Scoring Engine

Detected conditions are transformed into structured scoring information.

Relevant components include:

```text
core_engine/scoring/
├── confidence_score.py
├── score_breakdown.py
├── score_engine.py
└── setup_ranker.py
```

The scoring layer is separated from raw market detection so that analysis signals can be evaluated consistently.

### 3. Execution Simulation

The execution layer models trade lifecycle behavior rather than treating every setup as a simple entry/exit event.

It includes:

* Entry management
* Trade management
* Partial closes
* Break-even handling
* Trailing stops
* Execution state handling

### 4. Risk Management

Risk controls are implemented as dedicated modules:

```text
core_engine/risk/
├── account_profile.py
├── daily_loss_guard.py
├── drawdown_protection.py
├── funded_risk.py
├── global_trade_limiter.py
├── lot_calculator.py
├── max_loss_guard.py
├── risk_validator.py
├── symbol_validator.py
└── weekend_guard.py
```

This separation keeps risk constraints independent from the signal-detection logic.

### 5. Backtesting & Simulation

The backtesting layer supports historical analysis, diagnostics, optimization, and simulation workflows.

It includes areas for:

* Historical testing
* Monte Carlo analysis
* Optimization
* CSV/data providers
* Execution testing
* Risk testing
* Signal diagnostics
* Performance analysis

The repository also contains extensive automated test modules covering individual detection and execution components.

### 6. Analytics

The analytics layer provides reusable analysis components for:

* Daily trade analysis
* Drawdown analysis
* Performance metrics
* Profit factor
* Setup statistics
* Trade statistics
* Win-rate analysis

### 7. News & Fundamental Analysis

The project includes a dedicated news engine for integrating market-event information into the analysis pipeline.

It contains:

* Economic calendar handling
* Event aggregation
* Impact classification
* Fundamental analysis
* News filtering
* News caching
* External providers
* Scheduled updates

### 8. Integrations

The project contains integration layers for external trading and communication systems.

#### MetaTrader 5

The `mt5_bridge` contains an MQL5 Expert Advisor and supporting include modules for communication between the trading system and MT5.

#### Telegram

The Telegram layer supports bot commands, alerts, onboarding, screenshots, and subscription-related functionality.

#### API

The API layer exposes backend functionality through route modules and WebSocket support, including areas such as:

* Authentication
* Accounts
* Trades
* Statistics
* Licenses
* Subscriptions

---

## Security Architecture

Security-related components are isolated under dedicated modules.

The project includes functionality for:

* Access control
* Account binding
* Anti-sharing controls
* Encryption
* Authentication
* Password hashing
* Token-based authentication
* Two-factor authentication flows

Sensitive runtime configuration is expected to be supplied through environment variables or deployment secret-management mechanisms rather than committed credentials.

**Do not place real API keys, passwords, broker credentials, Telegram tokens, or other secrets in the repository.**

---

## Technology

The repository contains multiple application layers and technologies, including:

* **Python** — analysis, backtesting, APIs, risk, analytics, integrations
* **TypeScript / JavaScript** — dashboard and web application components
* **MQL5** — MetaTrader 5 bridge / Expert Advisor
* **SQL / PostgreSQL-oriented components** — persistence and migrations
* **REST / WebSocket** — application communication
* **Git** — source control

---

## Repository Structure

The main architectural areas are:

```text
analytics/          Performance and trade analytics
api/                API and backend routes
backtester/         Historical testing and simulation
billing/            Billing and payment components
core_engine/        Core detection, scoring, execution and risk logic
database/           Database models, sessions and migrations
detection/          Market-analysis detection modules
docs/               Architecture and implementation documentation
license_system/     Licensing and subscription logic
mt5_bridge/         MetaTrader 5 integration
news_engine/        News and fundamental-event processing
security/           Security and access-control components
telegram_bot/       Telegram integration
tests/              Unit, integration and stress tests
web/dashboard       Dashboard and web application components
```

---

## Testing

The repository contains dedicated tests for multiple layers of the system, including:

* Market structure
* Liquidity
* Fair Value Gaps
* Order Blocks
* Scoring
* Risk
* Execution
* Trade management
* News filtering
* Multi-symbol execution
* Analytics
* API/integration behavior

Examples of test modules include:

```text
test_market_structure.py
test_liquidity.py
test_fvg.py
test_order_blocks.py
test_score_engine.py
test_risk_layer.py
test_execution_layer.py
test_trade_manager.py
test_multi_symbol_execution.py
test_news_filter.py
```

The goal of the test architecture is to validate individual components independently before combining them into larger workflows.

---

## Local Development

### Requirements

Typical development requirements include:

* Python 3.x
* Node.js / npm for web components
* Git
* PostgreSQL-compatible database components where required
* MetaTrader 5 for MT5-specific functionality

### Python environment

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows:

```powershell
.venv\Scripts\Activate.ps1
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

### Configuration

Runtime configuration should be supplied through environment variables.

Do not commit:

```text
.env
API keys
passwords
broker credentials
Telegram tokens
private keys
database credentials
```

---

## Engineering Principles

The project follows several architectural principles:

* Modular separation of responsibilities
* Deterministic simulation
* Explicit risk controls
* Testable components
* Separation of detection from execution
* Separation of runtime configuration from source code
* Reusable analytics components
* Clear integration boundaries
* Defensive validation around execution and risk

The system is intended to make trading-system behavior inspectable and testable rather than hiding decisions inside a single monolithic strategy script.

---

## Project Documentation

Additional documentation is available under:

```text
docs/
```

including architecture, API, deployment, ICT rules, user guidance, and implementation reports.

---

## Important Note

This repository is a software engineering and research project for market analysis, simulation, and trading-system development.

Backtesting and simulated results do not guarantee future performance. Nothing in this repository should be interpreted as financial advice or a guarantee of profitability.

---

## Author

**Yassin Belhadli**

GitHub:
https://github.com/yassinbelhadli

Repository:
https://github.com/yassinbelhadli/trading-analysis-simulation-engine
