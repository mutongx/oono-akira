from dataclasses import fields
from typing import Any, Mapping

from aiohttp import ClientSession

from oono_akira.log import log
from oono_akira.slack.any import AnyObject, AnyValue


class SlackAPI:
    OPTIONS: Mapping[str, tuple[str, str | None]] = {
        "oauth.v2.access": ("post", "application/x-www-form-urlencoded"),
        "users.info": ("get", None),
    }

    def __init__(
        self,
        session: ClientSession,
        token: str | None = None,
        path: tuple[str, ...] = tuple(),
    ):
        self._session = session
        self._token = token
        self._path = path

    def __getattr__(self, key: str):
        return SlackAPI(self._session, self._token, self._path + (key,))

    async def __call__(self, __data: AnyObject | None = None, **kwargs: Any) -> Any:
        # Prepare request payload
        payload: AnyObject = dict(**__data if __data else {}, **kwargs)
        headers: AnyObject = {}
        # Prepare request argument
        api = ".".join(self._path)
        method, mime = self.OPTIONS.get(api, ("post", "application/json"))
        body = {}
        if method == "post":
            headers = {"Content-Type": f"{mime}; charset=UTF-8"}
            if mime == "application/x-www-form-urlencoded":
                body["data"] = payload
            elif mime == "application/json":
                body["json"] = payload
        elif method == "get":
            body["params"] = payload
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        # Send request
        resp = await self._session.request(method, f"https://slack.com/api/{api}", headers=headers, **body)
        result = await resp.json()
        if not result.get("ok"):
            log(f"Error: {result}")
        return result


class SlackPayloadDumper:
    @staticmethod
    def dump(d: Any) -> AnyObject:
        if not hasattr(d, "__dataclass_fields__"):
            return d
        result: AnyObject = {}
        for field in fields(d):  # type: ignore
            value: AnyValue | None = getattr(d, field.name)
            if value is None:
                continue
            pending: AnyValue | None = None
            if isinstance(value, list):
                pending = []
                for item in value:  # type: ignore
                    pending.append(SlackPayloadDumper.dump(item))
            else:
                pending = SlackPayloadDumper.dump(value)
            result[field.name] = pending
        return result
