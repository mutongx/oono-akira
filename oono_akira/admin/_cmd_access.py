import re
from argparse import ArgumentParser, Namespace

from oono_akira.slack.context import SlackContext
from oono_akira.admin import CommandResponse

MENTION = re.compile(r"<([@#])([A-Z0-9]+)\|.*?>")


def help():
    return "Manage module accesses"


def setup(parser: ArgumentParser):
    parser.description = "Manage accesses to restricted modules for channels and users."
    parser.add_argument(
        "access_action",
        metavar="action",
        choices=["grant", "revoke", "list", "check"],
        help="The action to perform: grant/revoke/list/check",
    )
    parser.add_argument("access_channel", metavar="channel", help="The channel to manage accesses for")
    parser.add_argument("access_user", metavar="user", help="The user to manage access for")
    parser.add_argument("access_module", metavar="module", help="The affected module name")


async def handler(context: SlackContext | None, args: Namespace) -> CommandResponse:
    # TODO: Support None-context mode
    if context is None:
        return

    command = context.must_command()
    if command.user_id != context.workspace.adminId:
        return "message", "No permission to manage accesses", []

    action = args.access_action
    channel = args.access_channel
    user = args.access_user
    module = args.access_module

    if (action == "grant" or action == "check") and (channel == "*" or user == "*"):
        return "message", "Wildcard is not supported in this action", []
    if channel != "" and channel != "*":
        match = MENTION.match(channel)
        if match is None:
            return "message", f"Invalid channel syntax: {channel}", []
        if match.group(1) != "#":
            return "message", f"Not a channel: {channel}", []
        channel = match.group(2)
    if user != "" and user != "*":
        match = MENTION.match(user)
        if match is None:
            return "message", f"Invalid user syntax: {user}", []
        if match.group(1) != "@":
            return "message", f"Not a user: {user}", []
        user = match.group(2)

    channel_desc = "`*`" if channel == "*" else "*all channels*" if channel == "" else f"<#{channel}>"
    user_desc = "`*`" if user == "*" else "*all users*" if user == "" else f"<@{user}>"

    if action == "grant":
        await context.db.grant_access(context.workspace.id, channel, user, module)
        return "message", f"Granted access to `{module}`, channel: {channel_desc}, user: {user_desc}", []

    if action == "revoke":
        await context.db.revoke_access(
            context.workspace.id,
            channel if channel != "*" else None,
            user if user != "*" else None,
            module,
        )
        return "message", f"Revoked access to `{module}`, channel: {channel_desc}, user: {user_desc}", []

    if action == "check":
        modules = await context.db.get_accesses(context.workspace.id, channel, user)
        found_desc = "Found" if module in modules else "Found no"
        return "message", f"{found_desc} access to `{module}`, channel: {channel_desc}, user: {user_desc}", []

    if action == "list":
        accesses = await context.db.list_accesses(
            context.workspace.id,
            channel if channel != "*" else None,
            user if user != "*" else None,
            module,
        )
        desc: list[str] = []
        for access in accesses:
            desc.append(
                f"Found access to `{access.module}`"
                f", channel: {f'<#{access.channel}>' if access.channel != '' else '*all channels*'}"
                f", user: {f'<@{access.user}>' if access.user != '' else '*all users*'}"
            )
        if len(desc) == 0:
            desc.append(f"Found no accesses to `{module}`, channel: {channel_desc}, user: {user_desc}")
        return "message", "\n".join(desc), []
