import asyncio
import logging
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ThreadedAsyncLoop(threading.Thread):
    """A context-managed async event loop running in a separate thread."""

    def __init__(self, debug: bool = False):
        """Initialise the threaded async loop.

        Args:
            debug: Whether to enable debug mode for the event loop
        """
        self._loop = asyncio.new_event_loop()
        if debug:
            self._loop.set_debug(True)

        # Thread running the event loop
        super().__init__()

    def run(self):
        """Target function for the thread that runs the event loop."""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()
        # Close the loop after shutdown
        if not self._loop.is_closed():
            self._loop.close()

    def __enter__(self):
        """Enter the context manager.

        Returns:
            The ThreadedAsyncLoop instance.
        """
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager and shut down the event loop."""
        # Schedule the loop to stop in a thread-safe manner
        self._loop.call_soon_threadsafe(self._loop.stop)

        # Join the thread with a timeout to prevent indefinite blocking
        self.join(timeout=5.0)

        # Check if thread is still alive after timeout
        if self.is_alive():
            logger.warning("ThreadedAsyncLoop thread did not terminate within timeout")

        # Ensure the loop is closed
        if not self._loop.is_closed():
            self._loop.close()

    def run_coroutine(self, coro, timeout: Optional[int | float] = None) -> Any:
        """Run a coroutine in the thread's event loop.

        Args:
            coro: The coroutine to run
            timeout: Optional timeout for the operation

        Returns:
            The result of the coroutine
        """
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)
