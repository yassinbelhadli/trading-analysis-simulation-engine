from telegram_bot.locales.en import MESSAGES as EN
from telegram_bot.locales.fr import MESSAGES as FR
from telegram_bot.locales.ar import MESSAGES as AR
from telegram_bot.locales.es import MESSAGES as ES


LANGUAGES = {
    "EN": EN,
    "FR": FR,
    "AR": AR,
    "ES": ES,
}


def get_lang(context) -> str:
    return context.user_data.get("language", "EN")


def tr(context, key: str, **kwargs) -> str:
    lang = get_lang(context)
    messages = LANGUAGES.get(lang, EN)

    text = messages.get(key, EN.get(key, key))

    if kwargs:
        return text.format(**kwargs)

    return text