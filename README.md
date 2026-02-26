# Cloud-to-IaC Resource Analyzer

Compares deployed cloud resources (exported as JSON) against IaC declarations (also JSON) and produces a structured drift report. Each cloud resource gets one entry in the report with a state of Match, Modified, or Missing, and a ChangeLog listing every differing property when the state is Modified.

Matching is done by id first, name as a fallback. Comparison is recursive — it handles arbitrarily nested objects and arrays, reporting changes as dotted paths (tags.Owner, subnets[1].cidr_block).

The bonus Docker setup spins up LocalStack, runs the analysis against the example files, and optionally uploads the report to a local S3 bucket.

See README.md for usage and ARCHITECTURE.md for implementation details.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

### CLI

```bash
python -m cloud_iac_analyzer.cli cloud.json iac.json report.json
```

### Programmatic

```python
from cloud_iac_analyzer import generate_analysis_report

report = generate_analysis_report(
    cloud_file='cloud_resources.json',
    iac_file='iac_resources.json',
    output_file='report.json'
)
```

if you want more control:

```python
from cloud_iac_analyzer import ResourceAnalyzer

analyzer = ResourceAnalyzer(cloud_resources, iac_resources)
report = analyzer.analyze()
```

## Input format

Both files are JSON arrays of resource objects. Resources need at least an `id` or `name` field for matching — `id` is preferred and checked first.

## Output format

One entry per cloud resource:

```json
{
  "CloudResourceItem": {},
  "IacResourceItem": {},
  "State": "Modified",
  "ChangeLog": [
    {
      "KeyName": "tags.Environment",
      "CloudValue": "prod",
      "IacValue": "production"
    }
  ]
}
```

**State values:**

- `Match` — resource found in IaC and all properties are identical
- `Modified` — resource found in IaC but has differences (see ChangeLog)
- `Missing` — resource exists in cloud but not in IaC

`ChangeLog` is empty when state is `Match` or `Missing`. Property paths use dot notation for nested fields (`tags.Owner`) and bracket notation for arrays (`subnets[1].cidr_block`).

## Running on the examples

```bash
python -m cloud_iac_analyzer.cli examples/cloud_resources.json examples/iac_resources.json output/report.json
```

## Docker (bonus)

Spins up LocalStack and runs the analyzer, leaving the report in `output/`:

```bash
cd docker
docker-compose up
```

To also upload the report to the LocalStack S3 bucket:

```bash
docker-compose --profile upload up
```

Accessing the uploaded report:

```bash
aws s3 ls s3://analyzer-reports/ --endpoint-url http://localhost:4566 --region us-east-1
```

## Tests

```bash
pytest test_analyzer.py -v
```

## Notes

- Array comparison is index-based, so reordering array elements (e.g. security group rules) shows up as changes.
- Resources with neither `id` nor `name` are indexed by position and won't match reliably.
- Both input files must be JSON arrays — a top-level object will raise a `ValueError`.
