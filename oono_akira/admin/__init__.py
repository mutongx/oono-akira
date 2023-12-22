import os
import re
import importlib
from argparse import ArgumentParser, Namespace
from typing import Mapping, Callable, NoReturn, Awaitable, TypedDict

from oono_akira.slack.context import SlackContext

Command = TypedDict(
    "Command",
    {
        "parser": ArgumentParser,
        "handler": Callable[[SlackContext | None, Namespace], Awaitable[None]],
    },
)

parser = None
commands: Mapping[str, Command] = {}


class OonoAdminException(Exception):
    def __init__(self, message: str):
        self._message = message

    @property
    def message(self):
        return self._message


class OonoAdminArgumentParser(ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise OonoAdminException(message)


def get_parser():
    global parser, commands
    if parser is None:
        parser = OonoAdminArgumentParser(prog="/oono", add_help=False)
        subparsers = parser.add_subparsers(dest="command")
        for file in os.listdir(os.path.dirname(__file__)):
            if "__" in file:
                continue
            match = re.fullmatch(r"(_cmd_([0-9a-z_]+))\.py", file)
            if not match:
                continue
            module_name = match.group(2)
            module_import = f"oono_akira.admin.{match.group(1)}"
            module = importlib.import_module(module_import)
            subparser = subparsers.add_parser(module_name, description=module.desc(), add_help=False)
            subparser.add_argument("-h", "--help", action="store_true")
            module.setup(subparser)
            commands[module_name] = {"parser": subparser, "handler": module.handler}
    return parser


async def run_command(context: SlackContext | None, workspace: str, channel: str, user: str, args: list[str]):
    try:
        parsed_args = get_parser().parse_args(args)
        if parsed_args.command is None:
            raise OonoAdminException(get_parser().format_usage())
        command = commands[parsed_args.command]
        if parsed_args.help:
            raise OonoAdminException(command["parser"].format_help())
        parsed_args.workspace = workspace
        parsed_args.channel = channel
        parsed_args.user = user
        await commands[parsed_args.command]["handler"](context, parsed_args)
    except OonoAdminException as e:
        if context is None:
            print(e.message, end="")
            return
        await context.api.chat.postEphemeral(
            {
                "channel": channel,
                "user": user,
                "text": "Error running /oono command",
                "blocks": [
                    {
                        "type": "rich_text",
                        "elements": [
                            {"type": "rich_text_preformatted", "elements": [{"type": "text", "text": e.message}]}
                        ],
                    }
                ],
            }
        )


if __name__ == "__main__":
    import asyncio
    import sys

    asyncio.run(run_command(None, "!", "2", "3", sys.argv[1:]))
