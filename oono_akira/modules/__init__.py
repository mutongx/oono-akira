import os
import re
import importlib
from typing import Iterable

from oono_akira.log import log

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
                "name": mod_class.__name__  # type: ignore
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

    def iterate_modules(self, capability: str) -> Iterable[dict]:
        if capability in self._capabilities:
            for item in self._capabilities[capability]:
                yield self._modules[item]

    def get_module(self, name: str):
        return self._modules.get(name)
