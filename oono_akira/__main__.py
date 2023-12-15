import asyncio
import json
import sys

from oono_akira.config import Configuration
from oono_akira.oono import OonoAkira


async def amain(config: Configuration):
    async with OonoAkira(config) as oono:
        await oono.run()


if __name__ == "__main__":
    config_path = sys.argv[1]
    with open(config_path) as f:
        config = json.load(f)

    try:
        asyncio.run(amain(config))
    except KeyboardInterrupt:
        pass
