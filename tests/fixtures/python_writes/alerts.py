"""PagerDuty/Opsgenie alert regression fixture."""


def send_pager_alert(pagerduty, summary):
    pagerduty.send_alert(summary=summary)


def create_opsgenie_incident(opsgenie, message):
    opsgenie.create_incident(message=message)
