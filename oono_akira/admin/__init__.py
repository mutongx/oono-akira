import os
import re
import importlib
import shlex
from argparse import ArgumentParser, Namespace, Action
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


class OonoHelpAction(Action):
    def __call__(self, parser: ArgumentParser, *_):
        raise OonoAdminException(parser.format_help())


class OonoAdminArgumentParser(ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise OonoAdminException(message)


def get_parser():
    global parser, commands
    if parser is None:
        parser = OonoAdminArgumentParser(prog="/oono", add_help=False)
        parser.register("action", "oono_help", OonoHelpAction)
        parser.add_argument("-h", "--help", nargs=0, action="oono_help", help="Display help message")
        subparsers = parser.add_subparsers(dest="command", metavar="<command>")
        for file in os.listdir(os.path.dirname(__file__)):
            if "__" in file:
                continue
            match = re.fullmatch(r"(_cmd_([0-9a-z_]+))\.py", file)
            if not match:
                continue
            mod_name = match.group(2)
            mod_import = f"oono_akira.admin.{match.group(1)}"
            mod = importlib.import_module(mod_import)
            subparser = subparsers.add_parser(mod_name, help=mod.help(), add_help=False)
            subparser.register("action", "oono_help", OonoHelpAction)
            subparser.add_argument("-h", "--help", nargs=0, action="oono_help", help="Display help message")
            mod.setup(subparser)
            commands[mod_name] = {"parser": subparser, "handler": mod.handler}
    return parser


async def run_command(context: SlackContext | None, workspace: str, channel: str, user: str, command_text: str):
    try:
        args = shlex.split(command_text)
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
                            {"type": "rich_text_preformatted", "elements": [
                                {"type": "text", "text": f"# /oono {command_text}\n{e.message}"}
                            ]}
                        ],
                    }
                ],
            }
        )


if __name__ == "__main__":
    import asyncio
    import sys

    asyncio.run(run_command(None, "", "", "", shlex.join(sys.argv[1:])))
