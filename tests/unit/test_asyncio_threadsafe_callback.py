import asyncio
import threading
import time

import pytest


@pytest.mark.asyncio
async def test_delayed_call_soon_threadsafe_wakes_waiting_future():
    loop = asyncio.get_running_loop()
    future = loop.create_future()

    def worker():
        time.sleep(0.05)
        loop.call_soon_threadsafe(future.set_result, "ok")

    thread = threading.Thread(target=worker)
    thread.start()
    try:
        result = await asyncio.wait_for(future, timeout=0.5)
    finally:
        thread.join()

    assert result == "ok"
