import logging


class SafeRequestFilter(logging.Filter):
    """Never log query strings, form bodies, upstream errors or tracebacks.

    Django's development server normally logs callback query tokens verbatim.
    Only numeric HTTP status is retained; meaningful events live in the audit DB.
    """
    def filter(self, record):
        status = getattr(record, "status_code", None)
        record.msg = f"Local HTTP event: status {status}." if isinstance(status, int) else "Local application event (details suppressed)."
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True
