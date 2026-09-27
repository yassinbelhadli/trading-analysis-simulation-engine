import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from telegram_bot.onboarding_state import *

session = UserOnboardingSession(
    telegram_user_id="123456",
    state=OnboardingState.START,
    data={}
)

print(session.state)

session.next(OnboardingState.SELECT_LANGUAGE)

print(session.state)

session.save("language", "EN")

print(session.data)

print(LANGUAGES)

print(TRADING_MODES)