import gc

from ibeis.control import IBEISControl


class _DummyController:
    def __init__(self):
        self.observer_weakref_list = []


class _Observer:
    pass


def test_controller_observer_weakref_lifecycle():
    ibs = _DummyController()
    observer = _Observer()

    assert IBEISControl.IBEISController.register_observer(ibs, observer) is True
    assert len(ibs.observer_weakref_list) == 1
    assert ibs.observer_weakref_list[0]() is observer

    # Registering twice must not create duplicate callbacks.
    assert IBEISControl.IBEISController.register_observer(ibs, observer) is False
    assert len(ibs.observer_weakref_list) == 1

    # Removal is by referent identity even though the list stores weakrefs.
    assert IBEISControl.IBEISController.remove_observer(ibs, observer) is True
    assert ibs.observer_weakref_list == []
    assert IBEISControl.IBEISController.remove_observer(ibs, observer) is False


def test_controller_observer_registration_prunes_dead_refs():
    ibs = _DummyController()
    dead_observer = _Observer()
    IBEISControl.IBEISController.register_observer(ibs, dead_observer)
    del dead_observer
    gc.collect()
    assert ibs.observer_weakref_list[0]() is None

    live_observer = _Observer()
    IBEISControl.IBEISController.register_observer(ibs, live_observer)
    assert len(ibs.observer_weakref_list) == 1
    assert ibs.observer_weakref_list[0]() is live_observer
