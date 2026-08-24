import sys

from ibeis import main_module


def _captured_exception():
    try:
        raise RuntimeError('qt callback exploded')
    except RuntimeError:
        return sys.exc_info()


def test_installs_ibeis_exception_hook(monkeypatch):
    monkeypatch.setattr(sys, 'excepthook', sys.__excepthook__)

    main_module._install_exception_hook()

    assert sys.excepthook is main_module._ibeis_excepthook


def test_exception_hook_routes_traceback_through_loguru(monkeypatch):
    calls = []
    queued = []

    class DummyLogger:
        def opt(self, **kwargs):
            calls.append(('opt', kwargs))
            return self

        def critical(self, message):
            calls.append(('critical', message))

    monkeypatch.setattr(main_module, 'logger', DummyLogger())
    monkeypatch.setattr(
        main_module,
        '_queue_exception_dialog',
        lambda exc_type, exc_value, report: queued.append(
            (exc_type, exc_value, report)
        ),
    )
    exc_info = _captured_exception()

    main_module._ibeis_excepthook(*exc_info)

    assert calls[0][0] == 'opt'
    assert calls[0][1]['exception'] == exc_info
    assert calls[1] == ('critical', 'Unhandled exception')
    assert len(queued) == 1
    assert queued[0][0] is RuntimeError
    assert str(queued[0][1]) == 'qt callback exploded'
    assert 'RuntimeError: qt callback exploded' in queued[0][2]


def test_exception_hook_falls_back_to_python_hook(monkeypatch):
    calls = []

    class BrokenLogger:
        def opt(self, **kwargs):
            raise RuntimeError('logger failed')

    def fallback(exc_type, exc_value, tb):
        calls.append((exc_type, exc_value, tb))

    monkeypatch.setattr(main_module, 'logger', BrokenLogger())
    monkeypatch.setattr(sys, '__excepthook__', fallback)
    exc_info = _captured_exception()

    main_module._ibeis_excepthook(*exc_info)

    assert calls == [exc_info]


def test_exception_report_contains_support_context():
    exc_info = _captured_exception()

    report = main_module._format_exception_report(*exc_info)

    assert 'IBEIS unexpected error report' in report
    assert 'IBEIS version:' in report
    assert 'Python:' in report
    assert 'Platform:' in report
    assert 'RuntimeError: qt callback exploded' in report
