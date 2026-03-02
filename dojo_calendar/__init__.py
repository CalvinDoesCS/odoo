from . import models


def _backfill_session_calendar_events(env):
    """Create / update calendar.event for all sessions that don't have one yet.
    Runs automatically on module install via post_init_hook.
    """
    sessions = env["dojo.class.session"].search([("calendar_event_id", "=", False)])
    if sessions:
        sessions._sync_calendar_event()
