import asyncio
import importlib
import os
import re
import traceback
from collections import OrderedDict
from typing import Awaitable, Callable, MutableMapping, MutableSequence, Iterable, TypedDict, NotRequired

from oono_akira.log import log
from oono_akira.slack.context import SlackContext

Callback = Callable[[], Awaitable[None]]
HandlerFunction = Callable[[SlackContext], Awaitable[None]]
HandlerOption = TypedDict("HandlerOption", {"queue": NotRequired[str], "lock": NotRequired[bool]})
Handler = tuple[HandlerFunction, HandlerOption] | None
HandlerConstructorOption = TypedDict("HandlerConstructorOption", {"is_locked": bool, "has_access": bool})
HandlerConstructor = Callable[[SlackContext, HandlerConstructorOption], Handler]

ExecutorQueue = asyncio.Queue[tuple[SlackContext, HandlerFunction, Callback | None] | None]
ExecutorTask = asyncio.Task[None]

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
        self._executor: MutableMapping[str,tuple[ExecutorQueue, ExecutorTask]] = {}
        return self

    async def __aexit__(self, *_):
        for queue, task in self._executor.values():
            await queue.put(None)
            await task

    def iterate_modules(self, capability: str) -> Iterable[tuple[str, HandlerConstructor]]:
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
        await self._executor[name][0].put((context, handler_func, callback_func))

    def _ensure_queue(self, name: str):
        if name not in self._executor:
            queue: ExecutorQueue = asyncio.Queue()
            task: ExecutorTask = asyncio.create_task(self._run(name, queue), name=name)
            self._executor[name] = (queue, task)
            task.add_done_callback(lambda task: self._delete_queue(task.get_name()))

    def _delete_queue(self, name: str):
        del self._executor[name]

    async def _run(self, name: str, queue: ExecutorQueue):
        log(f"Executor started, name={name}")
        while True:
            try:
                async with asyncio.timeout(60):
                    item = await queue.get()
            except TimeoutError:
                log(f"Executor exiting due to timeout, name={name}")
                break
            if item is None:
                log(f"Executor exiting due to normal exit, name={name}")
                break
            context, handler_func, callback_func = item
            try:
                await handler_func(context)
                if callback_func:
                    await callback_func()
            except Exception:
                traceback.print_exc()


register = ModulesManager.register
