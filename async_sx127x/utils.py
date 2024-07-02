

from threading import RLock
from typing import Callable, Type


class Signal:

    lock: RLock = RLock()
    def __init__(self, *args: Type) -> None:
        self.listeners: list[Callable] = []
        self.args: tuple[Type, ...] = args

    def connect(self, func: Callable) -> None:
        if func not in self.listeners:
            self.listeners.append(func)

    def disconnect(self, func: Callable) -> None:
        if func in self.listeners:
            self.listeners.remove(func)

    def emit(self, *args) -> None:
        with self.lock:
            if len(args) == len(self.args):
                if any(not isinstance(arg, self_arg) for arg, self_arg in zip(args, self.args)):
                    raise TypeError(f'This signal should emit next types: {self.args}, but you try to emit {args}.')
            else:
                raise TypeError(f'This signal should emit next types: {self.args}, but you try to emit {args}.')
            _ = [callback(*args) for callback in self.listeners]
