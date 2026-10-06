"""Runtime contract; distro adapters do not contain authentication logic."""
from abc import ABC, abstractmethod


class AgentRuntime(ABC):
    @abstractmethod
    def authenticated(self): ...

    @abstractmethod
    def login(self, method, secret=None): ...

    @abstractmethod
    def start(self): ...

    @abstractmethod
    def forget(self): ...


def load_runtime(name, **kwargs):
    if name == 'codex':
        from runtimes.codex.runtime import CodexRuntime
        return CodexRuntime(**kwargs)
    raise ValueError(f'Runtime {name!r} is not integrated; no fallback credentials or agent will be used.')
