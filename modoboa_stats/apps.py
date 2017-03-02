"""AppConfig for stats."""

from django.apps import AppConfig


class StatsConfig(AppConfig):
    """App configuration."""

    name = "modoboa_stats"
    verbose_name = "Modoboa graphical statistics"

    def ready(self):
        from . import handlers
