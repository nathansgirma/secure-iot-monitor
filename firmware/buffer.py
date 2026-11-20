"""Keep readings in memory until they are sent. Oldest readings are dropped when full."""


class ReadingBuffer:
    def __init__(self, maxlen=100):
        self._maxlen = maxlen
        self._items = []

    def add(self, msg):
        self._items.append(msg)
        if len(self._items) > self._maxlen:
            self._items.pop(0)

    def peek(self):
        return self._items[0] if self._items else None

    def pop(self):
        if self._items:
            self._items.pop(0)

    def __len__(self):
        return len(self._items)
