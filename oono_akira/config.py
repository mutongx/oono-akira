from typing import List, Optional, TypedDict


class ServerSslConfiguration(TypedDict):
    cert: str
    key: str
    port: int


class ServerConfiguration(TypedDict):
    ssl: ServerSslConfiguration


class SqliteDatabaseConfiguration(TypedDict):
    path: str


class DatabaseConfiguration(TypedDict):
    sqlite: Optional[SqliteDatabaseConfiguration]


class SlackConfiguration(TypedDict):
    client_id: str
    client_secret: str
    redirect_uri: str
    token: str
    permissions: List[str]


class Configuration(TypedDict):
    server: ServerConfiguration
    database: DatabaseConfiguration
    slack: SlackConfiguration
