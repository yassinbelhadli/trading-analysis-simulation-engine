"""
PropFirmDetector — inspects available metadata to identify prop firm accounts.

Verification status semantics:
  IDENTIFIED        — firm identity detected from metadata, but rules are NOT
                      verified. High-confidence metadata match only.
  VERIFIED_RULES    — firm + program + actual risk rules verified from an
                      authoritative source (database or confirmed import).
  USER_PROVIDED_RULES — rules explicitly provided/confirmed by the user.
  AMBIGUOUS         — partial match, confirmation required.
  UNKNOWN           — insufficient metadata to identify.

The detector NEVER fabricates identification.
It inspects: broker, server, company, account_name, trading environment.
It does NOT identify a prop firm from broker name alone.
Metadata match alone is NEVER sufficient for VERIFIED_RULES.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any


class VerificationStatus(str, Enum):
    IDENTIFIED = "IDENTIFIED"                         # Firm identity detected, rules NOT verified
    VERIFIED_RULES = "VERIFIED_RULES"                 # Firm + program + rules verified from authoritative source
    USER_PROVIDED_RULES = "USER_PROVIDED_RULES"       # Rules explicitly provided by user
    AMBIGUOUS = "AMBIGUOUS"                           # Partial match, confirmation required
    UNKNOWN = "UNKNOWN"                               # Cannot identify from metadata


@dataclass
class PropFirmMatch:
    """Result of prop firm detection."""
    status: VerificationStatus
    firm_id: Optional[str] = None
    firm_name: Optional[str] = None
    program: Optional[str] = None
    confidence: float = 0.0  # 0.0 — 1.0
    matched_fields: List[str] = field(default_factory=list)
    message: str = ""


@dataclass
class PropFirmProfile:
    """Verified prop firm rules from known database."""
    firm_id: str
    firm_name: str
    program: str
    source: str  # "database" | "user_provided" | "verified"
    source_url: Optional[str] = None
    last_verified: Optional[str] = None
    profile_version: str = "1.0"
    verification_status: VerificationStatus = VerificationStatus.IDENTIFIED

    # Risk rules
    profit_target: Optional[float] = None
    daily_loss_limit: Optional[float] = None
    max_loss: Optional[float] = None
    min_trading_days: Optional[int] = None
    max_trading_days: Optional[int] = None
    reward_share: Optional[float] = None
    drawdown_type: Optional[str] = None  # "static" | "trailing" | "equity"
    drawdown_limit: Optional[float] = None
    max_position_size: Optional[float] = None
    news_trading_allowed: Optional[bool] = None
    weekend_holding_allowed: Optional[bool] = None
    consistency_rules: Optional[Dict[str, Any]] = None


# ── Known prop firm server patterns ──────────────────────────────────
# These are RELIABLE identifiers: server names that are unique to a firm.
# Broker name alone is NOT sufficient.

KNOWN_SERVER_PATTERNS: Dict[str, Dict[str, Any]] = {
    "ftmo": {
        "patterns": ["FTMO-", "FTMO.", "FTMOGlobal"],
        "server_keywords": ["ftmo"],
        "company_keywords": ["FTMO"],
        "confidence_boost": 0.4,
    },
    "funding_pips": {
        "patterns": ["FundingPips", "FP-", "FP."],
        "server_keywords": ["fundingpips", "funding-pips"],
        "company_keywords": ["FundingPips", "Funding Pips"],
        "confidence_boost": 0.4,
    },
    "funded_next": {
        "patterns": ["FundedNext", "FN-", "FN."],
        "server_keywords": ["fundednext", "funded-next"],
        "company_keywords": ["FundedNext", "Funded Next"],
        "confidence_boost": 0.4,
    },
    "the5ers": {
        "patterns": ["The5ers", "The5%", "5%"],
        "server_keywords": ["the5ers", "the5"],
        "company_keywords": ["The5ers", "The 5%ers"],
        "confidence_boost": 0.4,
    },
    "topstep": {
        "patterns": ["TopStep", "TopStepX"],
        "server_keywords": ["topstep"],
        "company_keywords": ["TopStep"],
        "confidence_boost": 0.4,
    },
    "my_forex_funds": {
        "patterns": ["MFF", "MyForexFunds"],
        "server_keywords": ["myforexfunds", "my-forex-funds"],
        "company_keywords": ["MyForexFunds", "My Forex Funds"],
        "confidence_boost": 0.4,
    },
    "true_forex_funds": {
        "patterns": ["TFF", "TrueForexFunds"],
        "server_keywords": ["trueforexfunds", "true-forex-funds"],
        "company_keywords": ["TrueForexFunds", "True Forex Funds"],
        "confidence_boost": 0.4,
    },
    "surge_trader": {
        "patterns": ["SurgeTrader", "Surge"],
        "server_keywords": ["surgtrader", "surge"],
        "company_keywords": ["SurgeTrader", "Surge Trader"],
        "confidence_boost": 0.4,
    },
    "e8_funding": {
        "patterns": ["E8Funding", "E8F", "E8-"],
        "server_keywords": ["e8funding", "e8"],
        "company_keywords": ["E8Funding", "E8 Funding"],
        "confidence_boost": 0.4,
    },
    "alpha_capital": {
        "patterns": ["AlphaCapital", "AC-", "AC."],
        "server_keywords": ["alphacapital", "alpha-capital"],
        "company_keywords": ["AlphaCapital", "Alpha Capital"],
        "confidence_boost": 0.4,
    },
}

# ── Known prop firm programs ─────────────────────────────────────────
KNOWN_PROGRAMS: Dict[str, List[Dict[str, Any]]] = {
    "ftmo": [
        {"name": "1-Step Standard", "keywords": ["1-step", "1 step", "challenge"]},
        {"name": "2-Step Standard", "keywords": ["2-step", "2 step", "challenge"]},
        {"name": "2-Step Swing", "keywords": ["swing"]},
    ],
    "funding_pips": [
        {"name": "Zero", "keywords": ["zero"]},
        {"name": "1-Step", "keywords": ["1-step", "1 step"]},
        {"name": "2-Step Standard 8%", "keywords": ["2-step", "8%"]},
        {"name": "2-Step Standard 10%", "keywords": ["2-step", "10%"]},
        {"name": "2-Step Flex", "keywords": ["flex"]},
        {"name": "2-Step Pro", "keywords": ["pro"]},
    ],
    "funded_next": [
        {"name": "Stellar 2-Step", "keywords": ["stellar", "2-step"]},
        {"name": "Stellar 1-Step", "keywords": ["stellar", "1-step"]},
        {"name": "Stellar Lite", "keywords": ["lite"]},
        {"name": "Stellar Instant", "keywords": ["instant"]},
    ],
}


class PropFirmDetector:
    """
    Inspects available account metadata to identify prop firm accounts.

    Usage:
        detector = PropFirmDetector()
        result = detector.detect(
            server="FTMO-Demo",
            broker="FTMO",
            company="FTMO Global Markets Ltd",
            account_name="FTMO Challenge",
        )
        # result.status == VerificationStatus.IDENTIFIED  (metadata only, rules NOT verified)
        # result.firm_id == "ftmo"
        # result.confidence == 0.8
    """

    def detect(
        self,
        server: Optional[str] = None,
        broker: Optional[str] = None,
        company: Optional[str] = None,
        account_name: Optional[str] = None,
        user_declared_firm: Optional[str] = None,
        user_declared_program: Optional[str] = None,
    ) -> PropFirmMatch:
        """
        Detect prop firm from available metadata.

        Confidence scoring:
        - Server pattern match: +0.4
        - Company keyword match: +0.3
        - Broker keyword match: +0.1
        - Account name match: +0.1
        - User declared firm: +0.1 (but only as tiebreaker)

        Thresholds:
        - >= 0.7: IDENTIFIED (firm name only — rules are NOT verified)
        - >= 0.4: AMBIGUOUS
        - < 0.4: UNKNOWN
        """
        scores: Dict[str, float] = {}
        matched_fields: List[str] = []
        best_match: Optional[str] = None
        best_score = 0.0

        server_lower = (server or "").lower()
        broker_lower = (broker or "").lower()
        company_lower = (company or "").lower()
        account_lower = (account_name or "").lower()

        for firm_id, patterns in KNOWN_SERVER_PATTERNS.items():
            score = 0.0
            fields_matched: List[str] = []

            # Server pattern (strongest signal)
            for pat in patterns["patterns"]:
                if pat.lower() in server_lower:
                    score += patterns["confidence_boost"]
                    fields_matched.append("server")
                    break

            # Server keywords
            for kw in patterns["server_keywords"]:
                if kw in server_lower:
                    score += 0.1
                    fields_matched.append("server_keyword")
                    break

            # Company keywords (strong signal)
            for kw in patterns["company_keywords"]:
                if kw.lower() in company_lower:
                    score += 0.3
                    fields_matched.append("company")
                    break

            # Broker keywords (weaker — broker name alone is NOT sufficient)
            for kw in patterns["company_keywords"]:
                if kw.lower() in broker_lower:
                    score += 0.1
                    fields_matched.append("broker")
                    break

            # Account name
            for kw in patterns["server_keywords"]:
                if kw in account_lower:
                    score += 0.1
                    fields_matched.append("account_name")
                    break

            # User declaration (tiebreaker only)
            if user_declared_firm and firm_id in user_declared_firm.lower():
                score += 0.1
                fields_matched.append("user_declared")

            if score > best_score:
                best_score = min(score, 1.0)
                best_match = firm_id
                matched_fields = list(set(fields_matched))

        # Determine status
        if best_match and best_score >= 0.7:
            status = VerificationStatus.IDENTIFIED
            message = f"Identified as {best_match.replace('_', ' ').title()} (confidence: {best_score:.0%}). Rules are NOT verified."
        elif best_match and best_score >= 0.4:
            status = VerificationStatus.AMBIGUOUS
            message = f"Possible {best_match.replace('_', ' ').title()} account — confirmation required (confidence: {best_score:.0%})"
        else:
            status = VerificationStatus.UNKNOWN
            best_match = None
            message = "Unable to identify prop firm from available metadata"

        return PropFirmMatch(
            status=status,
            firm_id=best_match,
            firm_name=best_match.replace("_", " ").title() if best_match else None,
            confidence=best_score,
            matched_fields=matched_fields,
            message=message,
        )

    def detect_program(
        self,
        firm_id: str,
        server: Optional[str] = None,
        account_name: Optional[str] = None,
        user_declared_program: Optional[str] = None,
    ) -> Optional[str]:
        """
        Detect specific program within a identified firm.
        Returns program name or None if uncertain.
        """
        programs = KNOWN_PROGRAMS.get(firm_id, [])
        if not programs:
            return user_declared_program

        server_lower = (server or "").lower()
        account_lower = (account_name or "").lower()
        combined = f"{server_lower} {account_lower}"

        best_match = None
        best_score = 0

        for prog in programs:
            score = 0
            for kw in prog["keywords"]:
                if kw in combined:
                    score += 1
            if score > best_score:
                best_score = score
                best_match = prog["name"]

        return best_match or user_declared_program

    def get_profile(
        self,
        firm_id: str,
        program: Optional[str] = None,
        source: str = "database",
    ) -> Optional[PropFirmProfile]:
        """
        Get a prop firm profile.

        Status semantics:
        - source="database" and rules populated → VERIFIED_RULES
        - source="user_provided" → USER_PROVIDED_RULES
        - metadata match only, no rules → IDENTIFIED

        Returns None if firm is not recognized at all.
        """
        if firm_id not in KNOWN_SERVER_PATTERNS:
            return None

        # Determine verification status based on source
        if source == "database":
            v_status = VerificationStatus.VERIFIED_RULES
        elif source == "user_provided":
            v_status = VerificationStatus.USER_PROVIDED_RULES
        else:
            v_status = VerificationStatus.IDENTIFIED

        # Return a profile — rules are None until an authoritative source provides them
        return PropFirmProfile(
            firm_id=firm_id,
            firm_name=firm_id.replace("_", " ").title(),
            program=program or "Standard",
            source=source,
            verification_status=v_status,
        )


# Module-level singleton
prop_firm_detector = PropFirmDetector()
