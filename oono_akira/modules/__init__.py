import asyncio
import importlib
import os
import re
import traceback
from typing import Awaitable, Callable, Dict, Iterable, List, Optional, Tuple

from oono_akira.log import log
from oono_akira.slack import SlackAPI, SlackContext

HandlerFunctionType = Callable[[SlackContext, SlackAPI], Awaitable[None]]
HandlerType = Optional[Tuple[str, HandlerFunctionType]]
HandlerConstructorType = Callable[[SlackContext], HandlerType]


def register(type: str) -> Callable[[HandlerConstructorType], HandlerConstructorType]:
    def make(type: str, func: HandlerConstructorType):
        if type not in ModulesManager.CAPABILITIES:
            ModulesManager.CAPABILITIES[type] = []
        if func.__module__ not in ModulesManager.CAPABILITIES_MAPPING:
            ModulesManager.CAPABILITIES_MAPPING[func.__module__] = {}
        ModulesManager.CAPABILITIES[type].append(func)
        ModulesManager.CAPABILITIES_MAPPING[func.__module__][type] = func
        return func

    return lambda func: make(type, func)


class ModulesManager:

    CAPABILITIES: Dict[str, List[HandlerConstructorType]] = {}
    CAPABILITIES_MAPPING: Dict[str, Dict[str, HandlerConstructorType]] = {}

    def __init__(self) -> None:
        self._location = os.path.dirname(__file__)

        for file in sorted(os.listdir(self._location)):
            if "__" in file:
                continue
            if not re.fullmatch(r"_[0-9a-z_]+\.py", file):
                continue
            mod_name, _, _ = file.rpartition(".")
            mod = importlib.import_module(f"oono_akira.modules.{mod_name}")
            log(
                f"Loaded module {mod_name}, capability = {sorted(self.CAPABILITIES_MAPPING[mod.__name__])}"
            )

        log(f"Finished loading module at {self._location}")

    async def __aenter__(self):
        self._queue: Dict[
            str,
            asyncio.Queue[Optional[Tuple[SlackContext, SlackAPI, HandlerFunctionType]]],
        ] = {}
        self._future: Dict[str, asyncio.Task[None]] = {}
        return self

    async def __aexit__(self, *_):
        for queue in self._queue.values():
            await queue.put(None)
        for future in self._future.values():
            await future

    def iterate_modules(self, capability: str) -> Iterable[HandlerConstructorType]:
        if capability in self.CAPABILITIES:
            for item in self.CAPABILITIES[capability]:
                yield item

    async def queue(
        self,
        name: str,
        context: SlackContext,
        api: SlackAPI,
        handler_func: HandlerFunctionType,
    ):
        self._ensure_queue(name)
        await self._queue[name].put((context, api, handler_func))

    def _ensure_queue(self, name: str):
        if name not in self._queue:
            self._queue[name] = asyncio.Queue()
            self._future[name] = asyncio.create_task(self._run(name))

    async def _run(self, name: str):
        queue = self._queue[name]
        while True:
            item = await queue.get()
            if item is None:
                break
            context, api, handler_func = item
            try:
                await handler_func(context, api)
            except Exception:
                traceback.print_exc()
