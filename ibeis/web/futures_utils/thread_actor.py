"""Thread-backed actors implemented with public concurrent.futures APIs."""

from concurrent.futures import ThreadPoolExecutor
import threading

from ibeis.web.futures_utils import _base_actor


_THREAD_ACTOR_STATE = threading.local()


def _initialize_thread_actor(actor_class, args, kwargs):
    """Construct the actor inside its dedicated worker thread."""
    _THREAD_ACTOR_STATE.actor = actor_class(*args, **kwargs)


def _handle_thread_message(message):
    """Dispatch one message to the actor owned by this worker thread."""
    actor = _THREAD_ACTOR_STATE.actor
    return actor.handle(message)


class ThreadActorExecutor(_base_actor.ActorExecutor):
    """Manage one actor that processes messages serially in one thread."""

    def __init__(self, actor_class, *args, **kwargs):
        self._pool = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix='ibeis-actor',
            initializer=_initialize_thread_actor,
            initargs=(actor_class, args, kwargs),
        )

    def post(self, message):
        return self._pool.submit(_handle_thread_message, message)

    def shutdown(self, wait=True, *, cancel_futures=False):
        return self._pool.shutdown(wait=wait, cancel_futures=cancel_futures)


class ThreadActor(_base_actor.Actor):
    """Actor whose state lives in a dedicated worker thread."""

    @classmethod
    def executor(cls, *args, **kwargs):
        return ThreadActorExecutor(cls, *args, **kwargs)
