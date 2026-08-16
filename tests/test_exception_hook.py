import io
import sys

from ibeis import main_module


def _captured_exception():
    try:
        raise RuntimeError('qt callback exploded')
    except RuntimeError:
        return sys.exc_info()


def test_windows_installs_ibeis_exception_hook(monkeypatch):
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(sys, 'excepthook', sys.excepthook)

    main_module._install_exception_hook()

    assert sys.excepthook is main_module._ibeis_excepthook


def test_ibeis_exception_hook_writes_traceback_to_stderr(monkeypatch):
    stream = io.StringIO()
    monkeypatch.setattr(sys, 'stderr', stream)

    main_module._ibeis_excepthook(*_captured_exception())

    text = stream.getvalue()
    assert 'Traceback (most recent call last)' in text
    assert 'RuntimeError: qt callback exploded' in text


def test_ibeis_exception_hook_falls_back_to_file_logger(monkeypatch):
    messages = []

    class DummyLogger:
        def error(self, message):
            messages.append(message)

    monkeypatch.setattr(sys, 'stderr', None)
    monkeypatch.setattr(sys, '__stderr__', None)
    monkeypatch.setattr(main_module.ut, 'get_utool_logger', lambda: DummyLogger())

    main_module._ibeis_excepthook(*_captured_exception())

    assert len(messages) == 1
    assert 'RuntimeError: qt callback exploded' in messages[0]
