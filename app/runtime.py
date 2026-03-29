import asyncio
import logging
import threading
from typing import Any, Callable, Dict, Optional


class ManagedAsyncServer:
    def __init__(self, name: str, factory: Callable[["ManagedAsyncServer"], Any]) -> None:
        self.name = name
        self.factory = factory
        self.logger = logging.getLogger(f"runtime.{name}")
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._server: Optional[asyncio.base_events.Server] = None
        self._running = False
        self._last_error = ""
        self._last_started_at: Optional[float] = None
        self._last_stopped_at: Optional[float] = None

    def attach(self, loop: asyncio.AbstractEventLoop, server: asyncio.base_events.Server) -> None:
        with self._lock:
            self._loop = loop
            self._server = server
            self._running = True
            self._last_error = ""

    def set_running(self, running: bool, error: str = "") -> None:
        with self._lock:
            self._running = running
            if error:
                self._last_error = error

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "running": self._running,
                "last_error": self._last_error,
                "last_started_at": self._last_started_at,
                "last_stopped_at": self._last_stopped_at,
                "thread_alive": self._thread.is_alive() if self._thread else False,
            }

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._run, daemon=True, name=f"{self.name}-server")
            self._last_started_at = __import__('time').time()
            self._thread.start()

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        with self._lock:
            self._loop = loop
        try:
            server_obj = self.factory(self)
            loop.run_until_complete(server_obj.start(self))
        except Exception as exc:
            self.logger.error("%s server error: %s", self.name, exc)
            self.set_running(False, str(exc))
        finally:
            with self._lock:
                self._running = False
                self._server = None
                self._loop = None
                self._last_stopped_at = __import__('time').time()
            try:
                loop.stop()
            except Exception:
                pass
            loop.close()

    def stop(self, timeout: float = 5.0) -> bool:
        with self._lock:
            loop = self._loop
            server = self._server
            thread = self._thread
        if not loop or not server or not thread:
            return True

        done = threading.Event()

        def _shutdown() -> None:
            async def _close() -> None:
                server.close()
                await server.wait_closed()
                done.set()
            asyncio.create_task(_close())

        loop.call_soon_threadsafe(_shutdown)
        done.wait(timeout)
        thread.join(timeout)
        with self._lock:
            self._running = False
            self._server = None
            self._loop = None
            self._last_stopped_at = __import__('time').time()
        return not thread.is_alive()

    def restart(self) -> Dict[str, Any]:
        stopped = self.stop()
        self.start()
        return {"stopped": stopped, **self.status()}
