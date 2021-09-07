import os
import sys
import json
import asyncio
from oono_akira.oono import OonoAkira


def process_config(config: dict):
    config["server"]["ssl"]["cert"] = os.path.expanduser(config["server"]["ssl"]["cert"])
    config["server"]["ssl"]["key"] = os.path.expanduser(config["server"]["ssl"]["key"])
    config["db"]["path"] = os.path.expanduser(config["db"]["path"])


async def amain(config: dict):
    async with OonoAkira(config) as oono:
        await oono.run()


if __name__ == "__main__":
    config_path = sys.argv[1]
    with open(config_path) as f:
        config = json.load(f)

    process_config(config)

    try:
        asyncio.run(amain(config))
    except KeyboardInterrupt:
        pass
