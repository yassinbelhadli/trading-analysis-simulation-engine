PAGE_MAIN = "MAIN_MENU"
PAGE_ACCOUNTS = "MY_ACCOUNTS"
PAGE_ACTIVE = "ACTIVE_ACCOUNTS"
PAGE_ACCOUNT_DETAIL = "ACCOUNT_DETAIL"
PAGE_SETTINGS = "SETTINGS"
PAGE_LICENSE = "LICENSE"
PAGE_SUPPORT = "SUPPORT"
PAGE_STATUS = "STATUS"
PAGE_PERFORMANCE = "PERFORMANCE"


def push_page(context, page: str):
    stack = context.user_data.setdefault("nav_stack", [])
    if not stack or stack[-1] != page:
        stack.append(page)


def pop_page(context) -> str:
    stack = context.user_data.setdefault("nav_stack", [])
    if len(stack) <= 1:
        return PAGE_MAIN
    stack.pop()
    return stack[-1]


def reset_navigation(context):
    context.user_data["nav_stack"] = [PAGE_MAIN]


def current_page(context) -> str:
    stack = context.user_data.get("nav_stack", [])
    return stack[-1] if stack else PAGE_MAIN
