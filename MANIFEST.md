# Deliverables

## Core requirements

- [x] Accepts cloud and IaC JSON files as input
- [x] Matches resources by `id`, falling back to `name`
- [x] Recursive property comparison (nested objects and arrays)
- [x] Three states: `Missing`, `Match`, `Modified`
- [x] `ChangeLog` with `KeyName` / `CloudValue` / `IacValue` for each diff
- [x] Dotted path notation for nested keys (`tags.Owner`, `subnets[1].cidr_block`)
- [x] JSON output, one entry per cloud resource
- [x] CLI interface

## Bonus

- [x] Dockerfile + docker-compose with LocalStack
- [x] S3 bucket (`analyzer-reports`) seeded on startup
- [x] `upload-to-s3.py` uploads the report with a timestamped key

## Files

```text
cloud_iac_analyzer/
├── analyzer.py          core logic
├── cli.py               CLI wrapper
└── __init__.py

docker/
├── Dockerfile
├── docker-compose.yml
├── init-localstack.sh   creates the S3 bucket
└── upload-to-s3.py

examples/
├── cloud_resources.json
└── iac_resources.json

test_analyzer.py         runs the analyzer against the example files
setup.py
requirements.txt
```
