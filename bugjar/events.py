

class EventSource(object):
    """A source of GUI events.

    An event source can receive handlers for events, and
    can emit events.
    """
    _events = {}

    @classmethod
    def bind(cls, event, handler):
        cls._events.setdefault(cls, {}).setdefault(event, []).append(handler)

    def emit(self, event, **data):
        try:
            for handler in self._events[self.__class__][event]:
                handler(self, **data)
        except KeyError:
            # No handler registered for event.
            pass
