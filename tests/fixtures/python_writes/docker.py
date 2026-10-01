"""Docker SDK regression fixture."""


def start_worker(client):
    client.containers.run("worker:latest", detach=True)
