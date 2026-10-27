---
description: Review the current changes against the service's architecture rules before pushing
argument-hint: [base branch or files to review]
---

Use the `architect` subagent to review the changes in this repository
($ARGUMENTS, or `git diff` against `origin/main` if nothing is given) against
the architecture rules and technology policy of this service. Report the
findings with their rule ids and a verdict. Do not edit any file.
