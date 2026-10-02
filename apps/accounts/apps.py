from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = "apps.accounts"

    def ready(self):
        from apps.accounts import schema  # noqa: F401
