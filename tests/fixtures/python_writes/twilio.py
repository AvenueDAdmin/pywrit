"""Twilio SMS regression fixture."""


def send_sms(client, to, body):
    client.messages.create(to=to, from_="+15555555555", body=body)
