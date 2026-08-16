"""IBEIS application logging policy.

Libraries in the IBEIS workspace import :mod:`loguru` directly and only emit
records.  Sink ownership lives here at the application boundary.
"""
import inspect
import logging
import sys

from loguru import logger
import utool as ut

_APP_SINK_IDS = []
_GUI_SINK_IDS = set()
_DEFAULT_SINK_REMOVED = False


class _InterceptHandler(logging.Handler):
    """Route standard-library logging records through IBEIS Loguru sinks."""

    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame = inspect.currentframe()
        depth = 0
        while frame is not None:
            filename = frame.f_code.co_filename
            is_logging = filename == logging.__file__
            is_frozen = 'importlib' in filename and '_bootstrap' in filename
            if depth > 0 and not (is_logging or is_frozen):
                break
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _configure_stdlib_bridge():
    """Make third-party stdlib logging share the application-owned sinks."""
    logging.basicConfig(
        handlers=[_InterceptHandler()],
        level=0,
        force=True,
    )


def _remove_app_sinks():
    global _APP_SINK_IDS
    for sink_id in _APP_SINK_IDS:
        try:
            logger.remove(sink_id)
        except ValueError:
            pass
    _APP_SINK_IDS = []


def configure_logging(enable_file=True, appname='ibeis', log_dir=None):
    """Configure IBEIS console and persistent-file sinks.

    This function is intentionally safe to call again after changing the IBEIS
    log directory.  Only application-owned sinks are replaced; GUI or other
    runtime sinks remain attached.
    """
    global _DEFAULT_SINK_REMOVED

    if not _DEFAULT_SINK_REMOVED:
        # Loguru ships with sink 0 writing to stderr.  IBEIS replaces it with a
        # plain-message console sink so legacy diagnostic output stays readable.
        try:
            logger.remove(0)
        except ValueError:
            pass
        _DEFAULT_SINK_REMOVED = True

    _remove_app_sinks()
    logger.configure(extra={'utool_indent': ''})

    stream = sys.stderr or getattr(sys, '__stderr__', None)
    if stream is not None:
        _APP_SINK_IDS.append(
            logger.add(
                stream,
                level='INFO',
                format='{extra[utool_indent]}{message}',
                colorize=None,
                backtrace=False,
                diagnose=False,
            )
        )

    log_fpath = None
    if enable_file:
        log_fpath = ut.get_log_fpath(num='next', appname=appname, log_dir=log_dir)
        _APP_SINK_IDS.append(
            logger.add(
                log_fpath,
                level='DEBUG',
                format='[{time:HH:mm:ss}]{extra[utool_indent]}{message}',
                encoding='utf-8',
                mode='a',
                backtrace=True,
                diagnose=False,
            )
        )
        # Preserve this small utool compatibility surface for callers that ask
        # where the current application log lives.
        ut.util_logging.set_current_log_fpath(log_fpath)
        logger.info('logging to log_fpath={!r}', log_fpath)
    else:
        ut.util_logging.set_current_log_fpath(None)

    _configure_stdlib_bridge()
    return log_fpath

def attach_gui_output(output_widget):
    """Attach an IBEIS-owned Loguru sink to a guitool log-output widget."""
    sink = output_widget.make_logging_sink()
    sink_id = logger.add(
        sink,
        level='DEBUG',
        format='{message}',
        backtrace=False,
        diagnose=False,
    )
    _GUI_SINK_IDS.add(sink_id)

    def remove_sink(*args):
        if sink_id in _GUI_SINK_IDS:
            try:
                logger.remove(sink_id)
            except ValueError:
                pass
            _GUI_SINK_IDS.discard(sink_id)

    output_widget.destroyed.connect(remove_sink)
    return sink_id

