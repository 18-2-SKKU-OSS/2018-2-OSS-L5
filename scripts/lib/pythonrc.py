try:
    from django.conf import settings
    from zerver.models import *
    from zerver.lib.actions import *  # type: ignore # Otherwise have duplicate imports with previous line
    from analytics.models import *
except Exception:
    import traceback
    print("\nException importing Zulip core modules on startup!")
    traceback.print_exc()
else:
    print("\nSuccessfully imported Zulip settings, models, and actions functions.")
