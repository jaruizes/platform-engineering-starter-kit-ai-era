# Spec: <what the service does, in the domain language>

## What we need

<The business need in two or three sentences: who, what and why.>

## Service

- **Name**: <service-name> (lowercase and dashes)
- **Team**: <owner team in the catalog>
- **Architecture**: <one from the engineering standards, for example Backend v2>
- **Module**: <first functional module, a business capability>
- **Package**: <base Java package, optional>

## API

### <Operation>

<What it does.>

- `GET /<resource>/{id}`
- Input: <parameters and body, with types>
- Output: <body, with an example>
- Errors: <status and body when the input is invalid or something is not found>

## Business rules

1. <One rule per line. Ranges say which side each boundary belongs to:
   "from 100 € (included) to 500 € (included)".>

## Acceptance criteria

- Given <context>, when <action>, then <observable result>.
- <One per rule at least, and one per boundary.>

## Dependencies

- <Other services it calls, with their contract, or "simulated in this version".>

## Test data

| <Key> | <Values> | <Expected result> |
|---|---|---|

## Out of scope

- <What this version does not do.>
