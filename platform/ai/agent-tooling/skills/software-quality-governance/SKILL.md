---
name: software-quality-governance
description: Verify a service change against its architecture-specific quality profile, interpret deterministic gate findings, correct the implementation, and report commit-linked evidence.
---

# Software quality and governance

Use the platform quality policy as the source of truth for what must pass. It is versioned by architecture; the Spring service Golden Path starts with `backend-spring-v2`.

1. Read the service catalog architecture label and its `AGENTS.md`. For Spring v2, read the `backend-spring-v2` architecture rules and quality profile.
2. Make the smallest change that satisfies the behavior and architecture. Keep business/domain code free of framework and persistence dependencies, follow module-first package ownership, and do not suppress ArchUnit rules.
3. Run `./mvnw -B -ntp verify -DskipITs`, then `python3 .platform/quality/gate.py --architecture backend-spring-v2`.
4. If the gate fails, use the named failed check and ArchUnit/JUnit output to correct the source. Do not edit the result JSON, relax the profile, skip tests, or move the GitOps manifest to make a failure disappear.
5. If configured, SonarQube adds analysis through `SONAR_HOST_URL` and `SONAR_TOKEN`; it does not replace the deterministic gate.
6. Before reporting completion, confirm the JSON evidence identifies the tested source commit, architecture and profile version. Summarize passed checks and any remaining findings.
