from typing import Dict, Any, Callable
# Placeholder for mapping custom extension parsers
class ParserRegistry:
    def __init__(self):
        self._handlers = {}

    def register(self, pattern_name: str, handler: Callable):
        self._handlers[pattern_name] = handler

    def get_handler(self, pattern_name: str) -> Optional[Callable]:
        return self._handlers.get(pattern_name)

registry = ParserRegistry()
