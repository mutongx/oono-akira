from typing import Any, Optional, Tuple

from aiohttp import ClientSession

from oono_akira.log import log
from oono_akira.slack.common import AnyObject


class SlackAPI:
    _REQ = {
        "oauth.v2.access": {
            "method": "post",
            "mime": "application/x-www-form-urlencoded",
        },
        "users.info": {
            "method": "get",
        },
    }

    def __init__(
        self,
        session: ClientSession,
        token: Optional[str] = None,
        path: Tuple[str, ...] = tuple(),
    ):
        self._session = session
        self._token = token
        self._path = path

    def __getattr__(self, key: str):
        return SlackAPI(self._session, self._token, self._path + (key,))

    async def __call__(self, __data: Optional[AnyObject] = None, **kwargs: Any) -> Any:
        # Prepare request payload
        payload: AnyObject = dict(**__data if __data else {}, **kwargs)
        headers: AnyObject = {}
        # Prepare request argument
        api = ".".join(self._path)
        req = self._REQ.get(api, {})
        method = req.get("method", "post")
        body = {}
        if method == "post":
            mime = req.get("mime", "application/json")
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
