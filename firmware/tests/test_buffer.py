from buffer import ReadingBuffer


def test_buffer_keeps_last_100():
    buf = ReadingBuffer(maxlen=100)
    for i in range(1, 151):
        buf.add({"n": i})
    assert len(buf) == 100
    assert buf.peek() == {"n": 51}


def test_pop_order_fifo():
    buf = ReadingBuffer(maxlen=5)
    for i in range(3):
        buf.add({"n": i})
    seen = []
    while len(buf):
        seen.append(buf.peek()["n"])
        buf.pop()
    assert seen == [0, 1, 2]


def test_peek_empty_is_none():
    assert ReadingBuffer().peek() is None


def test_pop_empty_is_safe():
    buf = ReadingBuffer()
    buf.pop()
    assert len(buf) == 0
