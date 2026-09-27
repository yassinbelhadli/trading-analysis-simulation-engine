# ICT Funded EA Pro — AI Development Rules

## Project Overview

This project is a production-grade algorithmic trading ecosystem.

Components:

- Telegram Bot
- MT4 / MT5 Integration
- Python Backend
- PostgreSQL
- Dashboard
- License System
- Subscription System
- Risk Engine
- SMC / ICT Trading Engine
- Notification System

The project targets reliability, security and capital protection before profit.

---

# GENERAL RULES

Before generating ANY code, verify that every rule below is respected.

Never ignore these rules.

---

# ARCHITECTURE

Always respect the project architecture.

Never place business logic inside Telegram handlers.

Never duplicate code.

Every feature must be placed inside its proper module.

Example:

Telegram
↓

Service

↓

Database

↓

Trading Engine

---

# SECURITY

Never expose:

API Keys

Telegram Tokens

License Keys

Passwords

Database credentials

Broker credentials

Always use environment variables.

Never hardcode secrets.

Encrypt sensitive account information before storing.

---

# DATABASE

Database: PostgreSQL

Never delete client data automatically.

Always validate before INSERT or UPDATE.

Use transactions for critical operations.

Never trust client-side data.

---

# TELEGRAM BOT

All user messages MUST support:

Arabic

English

French

Spanish

Never hardcode multilingual text inside handlers.

Always use:

translator.py

Every message must support language switching instantly.

---

# MT4 / MT5

Support BOTH:

MetaTrader 4

MetaTrader 5

Never assume MT5 only.

Always detect platform automatically or ask the user.

---

# ACCOUNT VALIDATION

Before activating the bot:

Verify credentials.

Verify broker.

Verify account type.

Verify balance.

Verify funded rules.

Verify available symbols.

Verify permissions.

Never activate trading before verification.

---

# RISK MANAGEMENT

Capital protection has priority.

If any funded rule is violated:

Stop trading.

Notify the client.

Never ignore:

Daily Loss

Maximum Loss

Profit Target

Minimum Trading Days

Maximum Drawdown

---

# TRADING ENGINE

No trade is allowed unless:

Market Structure

Liquidity

FVG

Order Block

Confirmation

Risk Filters

News Filter

Spread Filter

are validated.

---

# NEWS

High impact news must pause trading automatically.

---

# LICENSE

Always validate license before bot activation.

Expired license:

Disable trading.

Notify user.

---

# LOGGING

Log every important action.

Examples:

Login

License activation

Broker connection

Trade opened

Trade closed

Risk stop

Errors

Never log passwords.

Never log tokens.

---

# ERROR HANDLING

Never expose internal errors.

Users receive simple messages.

Detailed logs remain server-side.

---

# CODE QUALITY

Follow SOLID principles.

Prefer composition over duplication.

Use typing.

Write modular code.

Avoid giant files.

---

# PERFORMANCE

Optimize for:

Low latency

Low RAM usage

Fast startup

Minimal API calls

---

# DOCUMENTATION

Every public function should contain a short docstring.

Complex logic must include comments explaining WHY, not WHAT.

---

# FUTURE COMPATIBILITY

Every new feature must remain compatible with:

Telegram Bot

Dashboard

Mobile

MT4

MT5

Future Web Platform

---

# FINAL RULE

If a generated solution violates one of these rules:

DO NOT generate it.

Generate a compliant implementation instead.

# AI CONSISTENCY

Before creating a new file:

Check if a similar module already exists.

Before creating a new function:

Check if it already exists.

Never duplicate business logic.

Always reuse existing services when possible.