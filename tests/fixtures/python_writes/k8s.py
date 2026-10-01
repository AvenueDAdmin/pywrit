"""Kubernetes client regression fixture."""


def create_pod(core_v1_api, namespace, pod):
    core_v1_api.create_namespaced_pod(namespace=namespace, body=pod)


def delete_pod(core_v1_api, name, namespace):
    core_v1_api.delete_namespaced_pod(name=name, namespace=namespace)
