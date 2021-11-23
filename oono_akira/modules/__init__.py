import os
import re
import importlib
import asyncio
from typing import Iterable, Any, Optional, Tuple

from oono_akira.log import log
from oono_akira.slack import SlackAPI, SlackContext

class ModulesManager:

    def __init__(self) -> None:
        self._location = os.path.dirname(__file__)
        self._modules = {}
        self._capabilities = {}

        for file in sorted(os.listdir(self._location)):
            if "__" in file:
                continue
            if not re.fullmatch(r"_[0-9a-z_]+\.py", file):
                continue
            mod_name = file.split(".")[0]
            mod = importlib.import_module(f"oono_akira.modules.{mod_name}")
            mod_class = mod.MODULE  # type: ignore
            self._modules[mod_name] = {
                "module": mod,
                "class": mod_class,
                "name": mod_class.__name__  # type: str
            }
            capas = []
            for func in dir(mod_class):
                if not (callable(getattr(mod_class, func)) and func.startswith("check_")):
                    continue
                capability = func[len("check_"):]
                capas.append(capability)
                if capability not in self._capabilities:
                    self._capabilities[capability] = []
                self._capabilities[capability].append(mod_name)

            log(f"Loaded module {mod_name}, class name = {self._modules[mod_name]['name']}, capability = {capas}")

        log(f"Loaded module manager at {self._location}")

    async def __aenter__(self):
        self._queue = {}
        return self

    async def __aexit__(self, *_):
        for queue in self._queue.values():
            await queue["queue"].put(None)
        for queue in self._queue.values():
            await queue["future"]

    def iterate_modules(self, capability: str) -> Iterable[dict]:
        if capability in self._capabilities:
            for item in self._capabilities[capability]:
                yield self._modules[item]

    def get_module(self, name: str):
        return self._modules.get(name)

    async def queue(self, name: str, module: Any, api: SlackAPI, context: SlackContext, ack: asyncio.Queue):
        self._ensure_queue(name, module)
        await self._queue[name]["queue"].put((api, context, ack))

    def _ensure_queue(self, name: str, module: Any):
        if name not in self._queue:
            self._queue[name] = {
                "name": name,
                "module": module,
                "queue": asyncio.Queue(),
            }
            self._queue[name]["future"] = asyncio.create_task(self._run(name))

    async def _run(self, name: str):
        module = self._queue[name]["module"]
        queue = self._queue[name]["queue"]  # type: asyncio.Queue
        while True:
            item = await queue.get()  # type: Optional[Tuple[SlackAPI, SlackContext, asyncio.Queue]]
            if item is None:
                break
            api, context, ack = item
            result = await module["class"](api, context).process()  # type: Optional[dict]
            await ack.put((context["id"], result))
