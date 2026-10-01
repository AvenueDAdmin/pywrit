"""Slack/webhook regression fixture."""


def post_message(client, channel, text):
    client.chat_postMessage(channel=channel, text=text)
