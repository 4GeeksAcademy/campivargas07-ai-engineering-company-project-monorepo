"""Suppress exception details from libraries that log SQL/connection payloads."""
import logging
import re

from celery.signals import after_setup_logger, after_setup_task_logger


class SafeWorkerLogs(logging.Filter):
    def filter(self, record):
        # The worker's own structured logs contain only UUID, counters and safe
        # errors. Libraries sometimes include full SQL, parameters or exceptions.
        if record.name != "brasaland.tasks" and (record.exc_info or record.levelno >= logging.ERROR):
            record.msg = "Task library error (details suppressed)"
            record.args = ()
        elif record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(type(arg).__name__ if isinstance(arg, BaseException) else arg for arg in record.args)
        message = record.getMessage()
        message = re.sub(r"([a-zA-Z][a-zA-Z0-9+.-]*://)[^\s/@]+:[^\s/@]+@", r"\1[redacted]@", message)
        if "[SQL:" in message or "[parameters:" in message:
            message = "Task library error (SQL details suppressed)"
        record.msg, record.args = message, ()
        record.exc_info = None
        record.exc_text = None
        return True


@after_setup_logger.connect
@after_setup_task_logger.connect
def configure_safe_logs(logger, **kwargs):
    # Prefect installs its own handlers after the first flow starts. Sanitize at
    # record creation as well, so those handlers cannot bypass our root filter.
    factory = logging.getLogRecordFactory()
    if not getattr(factory, "_brasaland_safe", False):
        def safe_factory(*args, **kwargs):
            record = factory(*args, **kwargs)
            SafeWorkerLogs().filter(record)
            return record
        safe_factory._brasaland_safe = True
        logging.setLogRecordFactory(safe_factory)
    for handler in logger.handlers:
        handler.addFilter(SafeWorkerLogs())
