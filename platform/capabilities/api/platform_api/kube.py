"""What the code Golden Paths check in Kubernetes before creating a
repository: that the environment and the backend service exist."""

from __future__ import annotations


GROUP = "platform.starterkit.dev"
VERSION = "v1alpha1"


def load_kube_config() -> None:
    from kubernetes import config

    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()


def environment_exists(name: str) -> bool:
    from kubernetes import client
    from kubernetes.client.exceptions import ApiException

    try:
        client.CustomObjectsApi().get_cluster_custom_object(GROUP, VERSION, "environments", name)
        return True
    except ApiException as err:
        if err.status == 404:
            return False
        raise


def spring_service_exists(name: str, environment: str) -> bool:
    from kubernetes import client
    from kubernetes.client.exceptions import ApiException

    try:
        client.CustomObjectsApi().get_namespaced_custom_object(
            GROUP, VERSION, f"env-{environment}", "springservices", name)
        return True
    except ApiException as err:
        if err.status == 404:
            return False
        raise
