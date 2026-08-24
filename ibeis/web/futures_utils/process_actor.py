"""Process-backed actors implemented with public concurrent.futures APIs."""

from concurrent.futures import ProcessPoolExecutor

from ibeis.web.futures_utils import _base_actor


_PROCESS_ACTOR = None


def _initialize_process_actor(actor_class, args, kwargs):
    """Construct the persistent actor inside its dedicated worker process."""
    global _PROCESS_ACTOR
    _PROCESS_ACTOR = actor_class(*args, **kwargs)


def _handle_process_message(message):
    """Dispatch one message to the actor owned by this worker process."""
    if _PROCESS_ACTOR is None:
        raise RuntimeError('process actor worker was not initialized')
    return _PROCESS_ACTOR.handle(message)


class ProcessActorExecutor(_base_actor.ActorExecutor):
    """Manage one actor that processes messages serially in one process."""

    def __init__(self, actor_class, *args, **kwargs):
        self._pool = ProcessPoolExecutor(
            max_workers=1,
            initializer=_initialize_process_actor,
            initargs=(actor_class, args, kwargs),
        )

    def post(self, message):
        return self._pool.submit(_handle_process_message, message)

    def shutdown(self, wait=True, *, cancel_futures=False):
        return self._pool.shutdown(wait=wait, cancel_futures=cancel_futures)


class ProcessActor(_base_actor.Actor):
    """Actor whose state lives in a dedicated worker process."""

    @classmethod
    def executor(cls, *args, **kwargs):
        return ProcessActorExecutor(cls, *args, **kwargs)
