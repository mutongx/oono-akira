import os
import re
import importlib
from typing import List

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
            self._modules[mod_name] = {
                "module": mod,
                "class": mod.MODULE,
                "name": mod.MODULE.__name__
            }
            capas = []
            for func in dir(mod.MODULE):
                if not (callable(getattr(mod.MODULE, func)) and func.startswith("check_")):
                    continue
                capa = func[len("check_"):]
                capas.append(capa)
                if capa not in self._capabilities:
                    self._capabilities[capa] = []
                self._capabilities[capa].append(mod_name)

            log(f"Loaded module {mod_name}, class name = {self._modules[mod_name]['name']}, capability = {capas}")

        log(f"Loaded module manager at {self._location}")

    def get_capable_modules(self, capa: str) -> List[str]:
        return self._capabilities.get(capa, [])

    def get_module(self, name: str):
        return self._modules.get(name)
