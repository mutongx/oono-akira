from oono_akira.log import log
from typing import Tuple, Optional
from aiohttp import ClientSession

class SlackAPI:

    _REQ = {
        "oauth.v2.access": {
            "method": "post",
            "mime": "application/x-www-form-urlencoded"
        },
        "users.info": {
            "method": "get",
        },
    }

    def __init__(self, session: ClientSession, auth: Optional[dict] = None, path: Tuple[str, ...] = tuple()):
        self._session = session
        self._auth = auth
        self._path = path

    def __getattr__(self, key: str):
        return SlackAPI(self._session, self._auth, self._path + (key,))

    async def __call__(self, data=None, **kwargs):
        # Prepare request payload
        payload = {}
        headers = {}
        if data is not None:
            payload.update(data)
        payload.update(kwargs)
        # Prepare request argument
        api = ".".join(self._path)
        req = self._REQ.get(api, {})
        method = req.get("method", "post")
        body = {}
        if method == "post":
            mime = req.get("mime", "application/json")
            headers = { "Content-Type": f"{mime}; charset=UTF-8" }
            if mime == "application/x-www-form-urlencoded":
                body["data"] = payload
            elif mime == "application/json":
                body["json"] = payload
        elif method == "get":
            body["params"] = payload
        if self._auth and self._auth.get("token") is not None:
            headers["Authorization"] = f"Bearer {self._auth['token']}"
        # Send request
        resp = await self._session.request(
            method,
            f"https://slack.com/api/{api}",
            headers=headers,
            **body
        )
        result = await resp.json()
        if not result.get('ok'):
            log(f"Error: {result}")
        return result


class SlackContext(dict):
    pass