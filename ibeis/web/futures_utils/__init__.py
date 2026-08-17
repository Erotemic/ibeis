"""IBEIS-owned stateful actor helpers built on :mod:`concurrent.futures`."""

from ibeis.web.futures_utils._base_actor import Actor, ActorExecutor
from ibeis.web.futures_utils.process_actor import ProcessActor, ProcessActorExecutor
from ibeis.web.futures_utils.thread_actor import ThreadActor, ThreadActorExecutor

__all__ = [
    'Actor',
    'ActorExecutor',
    'ProcessActor',
    'ProcessActorExecutor',
    'ThreadActor',
    'ThreadActorExecutor',
]
