import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from telegram_bot.onboarding import telegram_onboarding


fake_update = {
    "message": {
        "message_id": 1,
        "from": {
            "id": 123456789,
            "is_bot": False,
            "first_name": "Yassin",
            "last_name": "Client",
            "username": "test_user",
            "language_code": "en",
        },
        "chat": {
            "id": 123456789,
            "type": "private",
        },
        "text": "/start",
    }
}

result = telegram_onboarding.register_from_update(fake_update)

print(result.to_dict())