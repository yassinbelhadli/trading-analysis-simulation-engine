# telegram_bot/onboarding.py
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class TelegramUser:
    telegram_user_id: str
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    language_code: Optional[str]
    registered_at: str

    def to_dict(self):
        return asdict(self)


@dataclass
class OnboardingResult:
    success: bool
    state: str
    message: str
    user: Optional[TelegramUser] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self):
        return asdict(self)


class TelegramOnboarding:

    def register_from_update(self, update: Dict[str, Any]) -> OnboardingResult:
        """
        Register user from Telegram /start update.
        Later this will connect with API + License system.
        """

        try:
            message = update.get("message") or {}
            from_user = message.get("from") or {}

            telegram_user_id = str(from_user.get("id", "")).strip()

            if not telegram_user_id:
                return OnboardingResult(
                    success=False,
                    state="INVALID_UPDATE",
                    message="Telegram user id not found.",
                    metadata={"update": update},
                )

            user = TelegramUser(
                telegram_user_id=telegram_user_id,
                username=from_user.get("username"),
                first_name=from_user.get("first_name"),
                last_name=from_user.get("last_name"),
                language_code=from_user.get("language_code"),
                registered_at=datetime.utcnow().isoformat(),
            )

            return OnboardingResult(
                success=True,
                state="USER_REGISTERED",
                message="Telegram user registered successfully.",
                user=user,
                metadata={
                    "chat_id": str((message.get("chat") or {}).get("id", "")),
                    "text": message.get("text", ""),
                },
            )

        except Exception as e:
            return OnboardingResult(
                success=False,
                state="ONBOARDING_ERROR",
                message=str(e),
                metadata={"update": update},
            )


telegram_onboarding = TelegramOnboarding()