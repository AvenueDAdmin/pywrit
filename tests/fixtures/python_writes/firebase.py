"""Firebase/FCM regression fixture."""


def push_message(messaging, token, title):
    messaging.send({"token": token, "notification": {"title": title}})
