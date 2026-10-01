"""SendGrid regression fixture."""


def send_email(sg):
    sg.client.mail.send.post(request_body={"personalizations": []})
