from pathlib import Path

import guitool_ibeis as gt

from ibeis.gui import guiback
from ibeis.tests.fixtures import IBEISControllerFixture


def _menu_action(menu, text):
    matches = [action for action in menu.actions() if action.text() == text]
    assert len(matches) == 1, (text, [action.text() for action in menu.actions()])
    return matches[0]


def _dispose_backend(back):
    if getattr(back.front, 'data_load_timer', None) is not None:
        back.front.data_load_timer.stop()
    back.mainwin.hide()
    back.mainwin.deleteLater()


def test_gui_database_state_transitions(tmp_path, monkeypatch):
    gt.ensure_qtapp()

    # Keep this lifecycle test isolated from the user's persistent last-opened
    # database cache while still checking every transition.
    default_dbdir = {'value': 'previous-database'}
    monkeypatch.setattr(
        guiback.sysres,
        'set_default_dbdir',
        lambda dbdir: default_dbdir.__setitem__('value', dbdir),
    )

    back = guiback.MainWindowBackend(ibs=None)
    try:
        front = back.front
        mainwin = back.mainwin

        assert back.ibs is None
        assert front.ibs is None
        assert not front.no_database_widget.isHidden()
        assert front.vsplitter.isHidden()
        assert not front.vsplitter.isEnabled()
        assert not mainwin.acceptDrops()

        assert _menu_action(mainwin.menuFile, 'New Database').isEnabled()
        assert _menu_action(mainwin.menuFile, 'Open Database').isEnabled()
        assert not _menu_action(mainwin.menuFile, 'Close Database').isEnabled()
        assert not _menu_action(
            mainwin.menuFile, 'Import Images (select file(s))').isEnabled()
        assert not mainwin.menuActions.isEnabled()
        assert not _menu_action(
            mainwin.menuActions, 'Query Single Annotation').isEnabled()
        assert not mainwin.menuOptions.isEnabled()

        # Timer callbacks are harmless before a controller is attached.
        front.data_load_loop()

        warnings = []
        monkeypatch.setattr(
            back, 'user_warning', lambda **kwargs: warnings.append(kwargs))
        assert back.open_database(str(tmp_path)) is False
        assert back.ibs is None
        assert warnings
        assert warnings[-1]['title'] == 'Cannot Open Database'

        with IBEISControllerFixture() as ibs:
            back.connect_ibeis_control(ibs)
            assert back.ibs is ibs
            assert front.ibs is ibs
            assert front.no_database_widget.isHidden()
            assert not front.vsplitter.isHidden()
            assert front.vsplitter.isEnabled()
            assert mainwin.acceptDrops()
            assert _menu_action(mainwin.menuFile, 'Close Database').isEnabled()
            assert _menu_action(
                mainwin.menuFile, 'Import Images (select file(s))').isEnabled()
            assert mainwin.menuActions.isEnabled()
            assert _menu_action(
                mainwin.menuActions, 'Query Single Annotation').isEnabled()
            assert mainwin.menuOptions.isEnabled()

            # The user-facing Close Database action must perform the same state
            # transition and release the controller handles.
            assert back.close_database() is True
            assert back.ibs is None
            assert front.ibs is None
            assert ibs.db is None
            assert ibs.staging is None
            assert not front.no_database_widget.isHidden()
            assert front.vsplitter.isHidden()
            assert not mainwin.acceptDrops()
            assert not _menu_action(mainwin.menuFile, 'Close Database').isEnabled()
            assert default_dbdir['value'] is None

            # Closing evicts the released handle from the controller cache, so
            # opening the same path produces a fresh usable controller.
            dbdir = str(ibs.get_dbdir())
            assert back.open_database(dbdir) is True
            reopened_ibs = back.ibs
            assert reopened_ibs is not ibs
            assert reopened_ibs.db is not None
            assert default_dbdir['value'] == dbdir
            assert _menu_action(mainwin.menuFile, 'Close Database').isEnabled()
            assert back.close_database() is True
            assert default_dbdir['value'] is None
    finally:
        _dispose_backend(back)


def test_new_database_dialog_has_strict_create_semantics(tmp_path):
    gt.ensure_qtapp()
    chosen = []

    def on_chosen(dbdir):
        chosen.append(Path(dbdir))
        return True

    widget = guiback.NewDatabaseWidget(back=None, on_chosen=on_chosen)
    try:
        widget.location_row.edit.setText(str(tmp_path))
        widget.dbname_row.edit.setText('FieldStudy2026')
        widget.update_state()

        expected = tmp_path / 'FieldStudy2026'
        assert widget.create_but.isEnabled()
        assert str(expected) in widget.validation_label.text()

        expected.mkdir()
        widget.update_state()
        assert not widget.create_but.isEnabled()
        assert 'already exists' in widget.validation_label.text()
        assert chosen == []

        expected.rmdir()
        widget.update_state()
        assert widget.create_but.isEnabled()
        widget.create_database()
        assert chosen == [expected]
    finally:
        widget.hide()
        widget.deleteLater()
