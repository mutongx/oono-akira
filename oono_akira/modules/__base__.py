from oono_akira.slack import SlackAPI, SlackContext

class ModuleBase:
    def __init__(self, slack_api: SlackAPI, slack_context: SlackContext):
        self._slack_api = slack_api
        self._slack_context = slack_context
