# event_bus.py

from collections import defaultdict
from typing import Callable, Dict, List, Any, Optional


class EventBus:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = defaultdict(list)

    def subscribe(self, event_name: str, callback: Callable):
        """
        Register new listener
        """
        if callback not in self._listeners[event_name]:
            self._listeners[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable):
        """
        Remove listener
        """
        if callback in self._listeners[event_name]:
            self._listeners[event_name].remove(callback)

    def publish(self, event_name: str, data: Any = None):
        """
        Send event to all listeners
        """
        listeners = self._listeners.get(event_name, [])

        for listener in listeners:
            try:
                listener(data)
            except Exception as e:
                print(f"[EVENT BUS ERROR] {event_name}: {e}")

    def clear(self):
        """
        Remove every listener
        """
        self._listeners.clear()

    def listeners_count(self, event_name: str) -> int:
        return len(self._listeners.get(event_name, []))


# Global Singleton
event_bus = EventBus()