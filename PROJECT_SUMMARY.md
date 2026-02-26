# Project summary

Compares deployed cloud resources (exported as JSON) against IaC declarations (also JSON) and produces a structured drift report. Each cloud resource gets one entry in the report with a state of `Match`, `Modified`, or `Missing`, and a `ChangeLog` listing every differing property when the state is `Modified`.

Matching is done by `id` first, `name` as a fallback. Comparison is recursive — it handles arbitrarily nested objects and arrays, reporting changes as dotted paths (`tags.Owner`, `subnets[1].cidr_block`).

The bonus Docker setup spins up LocalStack, runs the analysis against the example files, and optionally uploads the report to a local S3 bucket.

See README.md for usage and ARCHITECTURE.md for implementation details.
