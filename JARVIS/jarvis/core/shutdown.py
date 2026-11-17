from __future__ import annotations

import asyncio


class SystemHalted(RuntimeError):
    pass


class ShutdownController:
    PHRASE = "jarvis, shutdown protocol"

    def __init__(self):
        self.halted = False
        self._tasks: set[asyncio.Task] = set()

    def register_task(self, task: asyncio.Task) -> None:
        if self.halted:
            task.cancel()
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def ensure_running(self) -> None:
        if self.halted:
            raise SystemHalted("JARVIS is halted. Restart the local process to resume.")

    async def trigger(self, phrase: str) -> int:
        if phrase.strip().casefold() != self.PHRASE:
            raise ValueError("Shutdown phrase did not match")
        self.halted = True
        current = asyncio.current_task()
        tasks = [task for task in self._tasks if task is not current and not task.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        return len(tasks)
