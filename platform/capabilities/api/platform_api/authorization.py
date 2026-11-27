"""The platform's authorization model: the first line, for every operation,
read or write, inside or outside Kubernetes. Kyverno is the second line for
what reaches the Kubernetes API.

| Rule | Decision |
|---|---|
| Team scope | Create and delete only for your teams. Read your teams' resources; platform-team reads everything. Autonomous agents: only their owner team |
| Agent guardrails | Applied by Kyverno (small environments, env-* only); anything bigger becomes an approval request |
| Delete | Agents only delete what an agent requested for the same person (or the same autonomous agent) |
| Proposals | Only people in platform-team propose capability definitions |
| Approvals | Only people with the approver role, for their teams (platform-team approvers: every team), and never for a request made on their own behalf (four eyes) |
"""

from __future__ import annotations

from typing import Any, Mapping

from .identity import PREFIX, Identity


class Forbidden(PermissionError):
    """The requester may not do this."""


def _scope(identity: Identity) -> str:
    if identity.kind == "autonomous":
        return f"agent {identity.agent} works for team {', '.join(identity.teams) or 'none'}"
    who = identity.display
    return f"{who} is in {', '.join(identity.teams) or 'no team'}"


def require_team(identity: Identity, team: str | None, action: str) -> None:
    """Writes: only for one of your teams (an agent inherits its person's teams, no more)."""
    if not team:
        if identity.in_platform_team and not identity.is_agent:
            return
        raise Forbidden(f"Only people in platform-team can {action} without a team.")
    if team not in identity.teams:
        raise Forbidden(f"Team scope: {_scope(identity)}, not {team}, so it cannot {action} for {team}.")


def can_read(identity: Identity, team: str | None) -> bool:
    if identity.in_platform_team and identity.kind != "autonomous":
        return True
    return bool(team) and team in identity.teams


def require_read(identity: Identity, team: str | None, what: str) -> None:
    if not can_read(identity, team):
        raise Forbidden(f"Team scope: {_scope(identity)}; {what} belongs to {team or 'no team'}.")


def require_delete(identity: Identity, team: str | None, annotations: Mapping[str, str], what: str) -> None:
    require_team(identity, team, f"delete {what}")
    if not identity.is_agent:
        return
    requested_by = annotations.get(f"{PREFIX}/requested-by", "a person")
    if annotations.get(f"{PREFIX}/requester-type") != "agent":
        raise Forbidden(f"Agents can only delete what an agent requested: {what} was requested by {requested_by}. "
                        "Ask a person of the team to delete it.")
    if identity.kind == "autonomous":
        same = requested_by == identity.agent and not annotations.get(f"{PREFIX}/on-behalf-of")
    else:
        same = annotations.get(f"{PREFIX}/on-behalf-of") == identity.person
    if not same:
        owner = annotations.get(f"{PREFIX}/on-behalf-of") or requested_by
        raise Forbidden(f"Agents can only delete what an agent requested for the same person: {what} "
                        f"was requested for {owner}.")


def require_propose(identity: Identity) -> None:
    if identity.is_agent:
        # People decide what the platform needs; agents build it.
        raise Forbidden("Capability definitions are proposed by people on the platform team, not by agents.")
    if not identity.in_platform_team:
        raise Forbidden(f"Only people in platform-team propose platform capabilities; {_scope(identity)}.")


APPROVER = "approver"


def approval_team(approval: Mapping[str, Any]) -> str | None:
    return approval.get("team") or ((approval.get("manifest") or {}).get("spec") or {}).get("team") or \
        (approval.get("request") or {}).get("team")


def why_cannot_decide(identity: Identity, approval: Mapping[str, Any], four_eyes: bool = True) -> str | None:
    """None when the identity may approve or reject this request; otherwise why not."""
    if identity.is_agent:
        return "Agents never approve or reject: only people decide on what agents ask for."
    if APPROVER not in identity.roles:
        return f"{identity.person} does not have the approver role."
    team = approval_team(approval)
    if not identity.in_platform_team and team not in identity.teams:
        return (f"{identity.person} approves for {', '.join(identity.teams) or 'no team'}, "
                f"not for {team or 'requests without a team'}.")
    if four_eyes and approval.get("on_behalf_of") and approval.get("on_behalf_of") == identity.person:
        return (f"Four eyes: {identity.person} cannot decide on a request an agent made on their behalf. "
                "Another approver of the team, or of platform-team, has to.")
    return None


def require_decide(identity: Identity, approval: Mapping[str, Any], four_eyes: bool = True) -> None:
    reason = why_cannot_decide(identity, approval, four_eyes)
    if reason:
        raise Forbidden(reason)


def team_of_environment(environment: Mapping[str, Any] | None) -> str | None:
    return ((environment or {}).get("spec") or {}).get("team")
