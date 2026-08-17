"""Regression tests for IBEIS's vendored actor implementation."""

from ibeis.web.futures_utils.tests import (
    TestProcessActor as _TestProcessActor,
    TestThreadActor as _TestThreadActor,
)


def _check_actor_lifecycle(actor_class):
    executor = actor_class.executor(3, factor=2)
    try:
        initial = executor.post({'action': 'debug'}).result(timeout=10)
        assert initial.state['a'] == 6

        assert executor.post({'action': 'start'}).result(timeout=10) == 'started'
        updated = executor.post({'action': 'debug'}).result(timeout=10)
        assert updated.state['a'] == 3
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_thread_actor_persistent_state():
    _check_actor_lifecycle(_TestThreadActor)


def test_process_actor_persistent_state():
    _check_actor_lifecycle(_TestProcessActor)
