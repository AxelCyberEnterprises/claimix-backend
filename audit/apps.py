from django.apps import AppConfig


class AuditConfig(AppConfig):
    """Configuration for the audit app."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'audit'
    verbose_name = 'Audit Logs'
    
    def ready(self):
        """
        Override this to perform initialization tasks when the app is ready.
        This is where we import and connect our signals.
        """
        # Import signals to register them
        from . import signals  # noqa
        signals.connect_signals()
