from os import access
import sqlite3
import json
from datetime import datetime
from contextlib import closing
from oono_akira.log import log


class OonoDatabase:

    def __init__(self, file: str) -> None:
        self._file = file
        self._db = sqlite3.connect(self._file)

    def initialize(self):
        with closing(self._db.cursor()) as cur:
            workspace = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=:table", {"table": "workspace"})
            if workspace.fetchone() is None:
                cur.execute("""
                    CREATE TABLE workspace (
                        id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        bot TEXT NOT NULL,
                        admin TEXT NOT NULL,
                        token TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
            payload = cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=:table", {"table": "payload"})
            if payload.fetchone() is None:
                cur.execute("""
                    CREATE TABLE payload (
                        type TEXT NOT NULL,
                        time TEXT NOT NULL,
                        content TEXT NOT NULL
                    )
                """)

    def record_payload(self, payload_type, payload_content):
        if not isinstance(payload_content, str):
            payload_content = json.dumps(payload_content)
        with closing(self._db.cursor()) as cur:
            cur.execute("INSERT INTO payload VALUES (:type, :time, :content)", {
                "type": payload_type,
                "time": datetime.now(),
                "content": payload_content
            })
            self._db.commit()

    def add_workspace(self, workspace_id, workspace_name, bot_id, admin_id, access_token):
        with closing(self._db.cursor()) as cur:
            cur.execute("""
                INSERT INTO workspace(id, name, bot, admin, token, updated_at)
                VALUES (:id, :name, :bot, :admin, :token, :updated_at)
                ON CONFLICT(id)
                DO UPDATE SET
                    id=:id,
                    name=:name,
                    bot=:bot,
                    token=:token,
                    updated_at=:updated_at
            """, {
                "id": workspace_id,
                "name": workspace_name,
                "bot": bot_id,
                "admin": admin_id,
                "token": access_token,
                "updated_at": datetime.now()
            })
            self._db.commit()

    def get_workspace_info(self, workspace_id):
        with closing(self._db.cursor()) as cur:
            rows = cur.execute("SELECT name, bot, admin, token FROM workspace WHERE id=:id", {"id": workspace_id})
            row = rows.fetchone()
            if row is None:
                raise ValueError("Unauthorized workspace {}".format(workspace_id))
            name, bot, admin, token = row
        return {
            "workspace_name": name,
            "bot_id": bot,
            "admin_id": admin,
            "workspace_token": token
        }

