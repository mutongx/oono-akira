import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from prisma import Prisma

from oono_akira.config import DatabaseConfiguration


class OonoDatabase:
    def __init__(self, conf: DatabaseConfiguration) -> None:
        if conf["provider"] == "sqlite":
            self._client = Prisma(datasource={"url": conf["url"]})
        else:
            raise RuntimeError("unknown database provider")

    async def __aenter__(self):
        await self._client.connect()
        return self

    async def __aexit__(self, *_):
        await self._client.disconnect()

    async def record_payload(self, source: str, content: str | Any):
        if not isinstance(content, str):
            content = json.dumps(content)
        return await self._client.payload.create(
            data={
                "source": source,
                "content": content,
                "createdAt": datetime.now(),
            }
        )

    async def setup_workspace(self, id: str, name: str, bot_id: str, admin_id: str, token: str, hook_url: str):
        return await self._client.workspace.upsert(
            where={
                "id": id,
            },
            data={
                "create": {
                    "id": id,
                    "name": name,
                    "botId": bot_id,
                    "adminId": admin_id,
                    "token": token,
                    "hookUrl": hook_url,
                    "createdAt": datetime.now(),
                    "updatedAt": datetime.now(),
                },
                "update": {
                    "name": name,
                    "botId": bot_id,
                    "adminId": admin_id,
                    "token": token,
                    "hookUrl": hook_url,
                    "updatedAt": datetime.now(),
                },
            },
        )

    async def get_workspace(self, id: str):
        return await self._client.workspace.find_unique(
            where={
                "id": id,
            },
        )

    async def add_grant(self, workspace: str, channel: str, user: str, module: str):
        return await self._client.grant.upsert(
            where={
                "grant": {
                    "workspace": workspace,
                    "channel": channel,
                    "user": user,
                    "module": module,
                }
            },
            data={
                "create": {
                    "workspace": workspace,
                    "channel": channel,
                    "user": user,
                    "module": module,
                    "createdAt": datetime.now(),
                },
                "update": {},
            },
        )

    async def revoke_grant(self, workspace: str, channel: str | None, user: str | None, module: str):
        if channel is not None and user is not None:
            await self._client.grant.delete(
                where={
                    "grant": {
                        "workspace": workspace,
                        "channel": channel,
                        "user": user,
                        "module": module,
                    }
                }
            )
        if channel is None and user is None:
            await self._client.grant.delete_many(
                where={
                    "workspace": workspace,
                    "module": module,
                }
            )
        if channel is not None and user is None:
            await self._client.grant.delete_many(
                where={
                    "workspace": workspace,
                    "channel": channel,
                    "module": module,
                }
            )
        if channel is None and user is not None:
            await self._client.grant.delete_many(
                where={
                    "workspace": workspace,
                    "user": user,
                    "module": module,
                }
            )

    async def get_grants(self, workspace: str, channel: str, user: str):
        grants = await self._client.grant.find_many(
            where={
                "workspace": workspace,
                "channel": {"in": [channel, ""]},
                "user": {"in": [user, ""]},
            }
        )
        return set([grant.module for grant in grants])

    async def acquire_lock(self, workspace: str, channel: str, module: str):
        return await self._client.lock.upsert(
            where={
                "lock": {
                    "workspace": workspace,
                    "channel": channel,
                    "module": module,
                },
            },
            data={
                "create": {
                    "workspace": workspace,
                    "channel": channel,
                    "module": module,
                    "createdAt": datetime.now(),
                },
                "update": {},
            },
        )

    async def release_lock(self, workspace: str, channel: str, module: str):
        return await self._client.lock.delete(
            where={
                "lock": {
                    "workspace": workspace,
                    "channel": channel,
                    "module": module,
                },
            }
        )

    async def get_locks(self, workspace: str, channel: str):
        locks = await self._client.lock.find_many(
            where={
                "workspace": workspace,
                "channel": channel,
            }
        )
        return set([lock.module for lock in locks])

    @asynccontextmanager
    async def get_session(self, **kwargs: str):
        key = ",".join(f"{key}={value}" for key, value in sorted(kwargs.items()))
        session = await self._client.session.upsert(
            where={"key": key},
            data={
                "create": {
                    "key": key,
                    "content": "{}",
                    "createdAt": datetime.now(),
                    "updatedAt": datetime.now(),
                },
                "update": {},
            },
        )
        data = json.loads(session.content)
        yield data
        await self._client.session.update(
            where={
                "key": key,
            },
            data={
                "content": json.dumps(data),
                "updatedAt": datetime.now(),
            },
        )
