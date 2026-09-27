# risk_validator.py
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from core_engine.risk.account_profile import AccountProfile


@dataclass
class RiskValidationResult:
    valid: bool
    risk_level: str
    warnings: List[str]
    errors: List[str]
    recommendations: Dict[str, Any]
    custom_settings_required_acknowledgement: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RiskValidator:
    def __init__(self):
        self.safe_ranges = {
            "FUNDED": {
                "risk_per_trade": (0.10, 0.50),
                "max_daily_loss": (1.00, 4.00),
                "max_account_loss": (4.00, 10.00),
                "preferred_rr": (2.00, 5.00),
            },
            "PERSONAL": {
                "risk_per_trade": (0.25, 1.00),
                "max_daily_loss": (2.00, 6.00),
                "max_account_loss": (8.00, 20.00),
                "preferred_rr": (1.50, 4.00),
            },
            "SMALL": {
                "risk_per_trade": (0.10, 0.50),
                "max_daily_loss": (1.00, 3.00),
                "max_account_loss": (5.00, 12.00),
                "preferred_rr": (1.80, 3.00),
            },
        }

        self.hard_limits = {
            "risk_per_trade": 5.00,
            "max_daily_loss": 20.00,
            "max_account_loss": 50.00,
            "preferred_rr_min": 1.00,
        }

    def _range_check(
        self,
        value: float,
        safe_min: float,
        safe_max: float,
        field_name: str,
        warnings: List[str],
        recommendations: Dict[str, Any],
    ):
        if value < safe_min:
            warnings.append(
                f"{field_name} is too low ({value}). Recommended minimum is {safe_min}."
            )
            recommendations[field_name] = safe_min

        elif value > safe_max:
            warnings.append(
                f"{field_name} is aggressive ({value}). Recommended maximum is {safe_max}."
            )
            recommendations[field_name] = safe_max

    def validate_profile(self, profile: AccountProfile) -> RiskValidationResult:
        warnings = []
        errors = []
        recommendations = {}

        account_type = profile.account_type.upper()

        if account_type not in self.safe_ranges:
            errors.append("Invalid account type. Use FUNDED, PERSONAL, or SMALL.")

            return RiskValidationResult(
                valid=False,
                risk_level="INVALID",
                warnings=warnings,
                errors=errors,
                recommendations=recommendations,
                custom_settings_required_acknowledgement=False,
            )

        if profile.balance <= 0:
            errors.append("Balance must be greater than 0.")

        if profile.equity <= 0:
            errors.append("Equity must be greater than 0.")

        if profile.min_lot <= 0:
            errors.append("Min lot must be greater than 0.")

        if profile.max_lot < profile.min_lot:
            errors.append("Max lot cannot be smaller than min lot.")

        if profile.lot_step <= 0:
            errors.append("Lot step must be greater than 0.")

        if profile.risk_per_trade <= 0:
            errors.append("Risk per trade must be greater than 0.")

        if profile.preferred_rr < self.hard_limits["preferred_rr_min"]:
            errors.append("Preferred RR must be at least 1.0.")

        if profile.risk_per_trade > self.hard_limits["risk_per_trade"]:
            errors.append("Risk per trade is extremely dangerous and above hard limit.")

        if profile.max_daily_loss > self.hard_limits["max_daily_loss"]:
            errors.append("Max daily loss is above hard limit.")

        if profile.max_account_loss > self.hard_limits["max_account_loss"]:
            errors.append("Max account loss is above hard limit.")

        safe = self.safe_ranges[account_type]

        self._range_check(
            profile.risk_per_trade,
            safe["risk_per_trade"][0],
            safe["risk_per_trade"][1],
            "risk_per_trade",
            warnings,
            recommendations,
        )

        self._range_check(
            profile.max_daily_loss,
            safe["max_daily_loss"][0],
            safe["max_daily_loss"][1],
            "max_daily_loss",
            warnings,
            recommendations,
        )

        self._range_check(
            profile.max_account_loss,
            safe["max_account_loss"][0],
            safe["max_account_loss"][1],
            "max_account_loss",
            warnings,
            recommendations,
        )

        self._range_check(
            profile.preferred_rr,
            safe["preferred_rr"][0],
            safe["preferred_rr"][1],
            "preferred_rr",
            warnings,
            recommendations,
        )

        if account_type == "FUNDED":
            if profile.risk_per_trade > 0.50:
                warnings.append(
                    "Funded account risk is high. Recommended risk is 0.25% - 0.50%."
                )

            if profile.max_daily_loss >= profile.max_account_loss:
                errors.append(
                    "For funded accounts, max_daily_loss must be smaller than max_account_loss."
                )

        if account_type == "SMALL":
            if profile.max_lot > 0.50:
                warnings.append(
                    "Small account max lot looks too high. Recommended max lot is 0.10 - 0.50."
                )
                recommendations["max_lot"] = 0.10

            if profile.risk_per_trade > 1.00:
                warnings.append(
                    "Small account risk is very aggressive and may destroy the account quickly."
                )

        if not profile.use_recommended_settings and warnings:
            custom_ack = not profile.custom_settings_acknowledged
        else:
            custom_ack = False

        risk_level = self._classify_risk_level(profile, warnings, errors)

        return RiskValidationResult(
            valid=len(errors) == 0,
            risk_level=risk_level,
            warnings=warnings,
            errors=errors,
            recommendations=recommendations,
            custom_settings_required_acknowledgement=custom_ack,
        )

    def _classify_risk_level(
        self,
        profile: AccountProfile,
        warnings: List[str],
        errors: List[str],
    ) -> str:
        if errors:
            return "INVALID"

        if profile.risk_per_trade >= 3.00:
            return "EXTREME"

        if profile.risk_per_trade >= 2.00:
            return "VERY_HIGH"

        if profile.risk_per_trade >= 1.00:
            return "HIGH"

        if warnings:
            return "MODERATE"

        return "SAFE"

    def validate_trade_request(
        self,
        profile: AccountProfile,
        requested_risk_percent: Optional[float] = None,
        requested_rr: Optional[float] = None,
        requested_lot: Optional[float] = None,
    ) -> RiskValidationResult:
        temp_data = profile.to_dict()

        if requested_risk_percent is not None:
            temp_data["risk_per_trade"] = float(requested_risk_percent)

        if requested_rr is not None:
            temp_data["preferred_rr"] = float(requested_rr)

        if requested_lot is not None:
            if requested_lot < profile.min_lot:
                temp_data["min_lot"] = requested_lot

            if requested_lot > profile.max_lot:
                temp_data["max_lot"] = requested_lot

        temp_profile = AccountProfile.from_dict(temp_data)
        return self.validate_profile(temp_profile)

    def generate_warning_message(self, result: RiskValidationResult) -> str:
        if result.valid and not result.warnings:
            return "Risk settings are safe."

        lines = []

        if result.errors:
            lines.append("❌ Critical Risk Errors:")
            for e in result.errors:
                lines.append(f"- {e}")

        if result.warnings:
            lines.append("⚠️ Risk Warnings:")
            for w in result.warnings:
                lines.append(f"- {w}")

        if result.recommendations:
            lines.append("✅ Recommended Adjustments:")
            for key, value in result.recommendations.items():
                lines.append(f"- {key}: {value}")

        if result.custom_settings_required_acknowledgement:
            lines.append(
                "Client must acknowledge custom risk settings before activation."
            )

        return "\n".join(lines)