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

        # Event used to signal the loop to shut down
        self._shutdown_event = threading.Event()

        # Thread running the event loop
        super().__init__()

    def run(self):
        """Target function for the thread that runs the event loop."""
        asyncio.set_event_loop(self._loop)
        while not self._shutdown_event.is_set():
            # Run the loop for a short period, then check shutdown flag
            self._loop.run_until_complete(asyncio.sleep(0.1))
        # Close the loop after shutdown
        if self._loop.is_running():
            self._loop.stop()
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
        # Signal the event loop thread to shut down
        self._shutdown_event.set()

        # Join the thread with a timeout to prevent indefinite blocking
        self.join(timeout=5.0)

        # Check if thread is still alive after timeout
        if self.is_alive():
            logger.warning("ThreadedAsyncLoop thread did not terminate within timeout")

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
