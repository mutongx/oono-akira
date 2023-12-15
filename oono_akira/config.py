from typing import List, TypedDict


class ServerSslConfiguration(TypedDict):
    cert: str
    key: str
    port: int


class ServerConfiguration(TypedDict):
    ssl: ServerSslConfiguration


class DatabaseConfiguration(TypedDict):
    provider: str
    url: str


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
