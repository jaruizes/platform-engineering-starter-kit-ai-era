"""What the platform API reads from and writes to Kubernetes: the current
state of environments and services, and the audit trail (events)."""

from __future__ import annotations

import os
from datetime import datetime, timezone

GROUP = "platform.starterkit.dev"
VERSION = "v1alpha1"
PREFIX = "platform.starterkit.dev"
NAMESPACE = os.environ.get("PLATFORM_NAMESPACE", "platform-system")
COMPONENT = "platform-api"


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


def record(action: str, message: str, subject: str, actor: str, kind: str, warning: bool = False) -> None:
    """Adds an entry to the audit trail, the same Kubernetes events the
    console and the portal show. It never breaks the request itself."""
    from kubernetes import client
    from kubernetes.client.exceptions import ApiException

    timestamp = datetime.now(timezone.utc)
    requester_type = "agent" if actor.startswith("agent:") else "human"
    event = client.CoreV1Event(
        metadata=client.V1ObjectMeta(
            generate_name="platform-", namespace=NAMESPACE,
            annotations={
                f"{PREFIX}/actor": actor.removeprefix("agent:"),
                f"{PREFIX}/requester-type": requester_type,
            },
        ),
        involved_object=client.V1ObjectReference(
            api_version=f"{GROUP}/{VERSION}", kind=kind, name=subject, namespace=NAMESPACE),
        reason=action,
        message=message,
        type="Warning" if warning else "Normal",
        source=client.V1EventSource(component=COMPONENT),
        first_timestamp=timestamp,
        last_timestamp=timestamp,
        count=1,
    )
    try:
        client.CoreV1Api().create_namespaced_event(NAMESPACE, event)
    except ApiException:
        pass
