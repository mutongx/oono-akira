import asyncio
import importlib
import os
import re
import traceback
from collections import OrderedDict
from typing import Awaitable, Callable, MutableMapping, MutableSequence, Iterable, Tuple, TypedDict, NotRequired

from oono_akira.log import log
from oono_akira.slack.context import SlackContext

Callback = Callable[[], Awaitable[None]]
HandlerFunction = Callable[[SlackContext], Awaitable[None]]
HandlerOption = TypedDict("HandlerOption", queue=NotRequired[str], lock=NotRequired[bool])
Handler = Tuple[HandlerFunction, HandlerOption] | None
HandlerConstructorOption = TypedDict("HandlerConstructorOption", locked=bool, granted=bool)
HandlerConstructor = Callable[[SlackContext, HandlerConstructorOption], Handler]


class ModulesManager:
    CAPABILITIES: MutableMapping[str, MutableSequence[HandlerConstructor]] = {}
    CAPABILITIES_MAPPING: MutableMapping[str, MutableMapping[str, HandlerConstructor]] = {}

    @staticmethod
    def register(type: str) -> Callable[[HandlerConstructor], HandlerConstructor]:
        def _register(type: str, func: HandlerConstructor):
            if type not in ModulesManager.CAPABILITIES:
                ModulesManager.CAPABILITIES[type] = []
            if func.__module__ not in ModulesManager.CAPABILITIES_MAPPING:
                ModulesManager.CAPABILITIES_MAPPING[func.__module__] = {}
            ModulesManager.CAPABILITIES[type].append(func)
            ModulesManager.CAPABILITIES_MAPPING[func.__module__][type] = func
            return func

        return lambda func: _register(type, func)

    def __init__(self) -> None:
        # Module import to module name
        self._modules_mapping: MutableMapping[str, str] = {}
        # Module name to module import
        modules: MutableMapping[str, str] = OrderedDict()
        location = os.path.dirname(__file__)
        for file in sorted(os.listdir(location)):
            if "__" in file:
                continue
            match = re.fullmatch(r"(_[0-9]+_([0-9a-z_]+))\.py", file)
            if not match:
                continue
            mod_name = match.group(2)
            mod_import = f"oono_akira.modules.{match.group(1)}"
            if mod_name in modules:
                raise RuntimeError(f"duplicate module name: {mod_name}")
            modules[mod_name] = mod_import
        for mod_name, mod_import in modules.items():
            mod = importlib.import_module(mod_import)
            self._modules_mapping[mod_import] = mod_name
            log(f"Loaded module {mod_name}, capability = {sorted(self.CAPABILITIES_MAPPING[mod.__name__])}")
        log(f"Finished loading module at {location}")

    async def __aenter__(self):
        self._queue: MutableMapping[
            str,
            asyncio.Queue[Tuple[SlackContext, HandlerFunction, Callback | None] | None],
        ] = {}
        self._future: MutableMapping[str, asyncio.Task[None]] = {}
        return self

    async def __aexit__(self, *_):
        for queue in self._queue.values():
            await queue.put(None)
        for future in self._future.values():
            await future

    def iterate_modules(self, capability: str) -> Iterable[Tuple[str, HandlerConstructor]]:
        if capability in self.CAPABILITIES:
            for item in self.CAPABILITIES[capability]:
                yield self._modules_mapping[item.__module__], item

    async def queue(
        self,
        name: str,
        context: SlackContext,
        handler_func: HandlerFunction,
        callback_func: Callback | None = None,
    ):
        self._ensure_queue(name)
        await self._queue[name].put((context, handler_func, callback_func))

    def _ensure_queue(self, name: str):
        if name not in self._queue:
            self._queue[name] = asyncio.Queue()
            self._future[name] = asyncio.create_task(self._run(name))

    async def _run(self, name: str):
        # TODO: Add garbage collection
        queue = self._queue[name]
        while True:
            item = await queue.get()
            if item is None:
                break
            context, handler_func, callback_func = item
            try:
                await handler_func(context)
                if callback_func:
                    await callback_func()
            except Exception:
                traceback.print_exc()


register = ModulesManager.register
