"""Small actor abstraction built on the public :mod:`concurrent.futures` API."""

from concurrent.futures import Executor


class ActorExecutor(Executor):
    """Executor that owns exactly one persistent actor instance."""

    def post(self, message):
        """Schedule ``actor.handle(message)`` and return a Future."""
        raise NotImplementedError('use ProcessActorExecutor or ThreadActorExecutor')


class Actor(object):
    """Base class for stateful single-worker actors."""

    @classmethod
    def executor(cls, *args, **kwargs):
        """Create an asynchronous instance of this actor and its executor."""
        raise NotImplementedError('use ProcessActor or ThreadActor')

    def handle(self, message):
        """Handle one message and return its response."""
        raise NotImplementedError('must implement message handler')
