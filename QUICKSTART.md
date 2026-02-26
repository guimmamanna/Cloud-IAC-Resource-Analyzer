# Quick start

```bash
pip install -r requirements.txt
python -m cloud_iac_analyzer.cli examples/cloud_resources.json examples/iac_resources.json output/report.json
```

That runs the analyzer against the bundled example files. The report lands in `output/report.json`.

## Reading the output

Each entry in the report corresponds to one cloud resource:

```json
{
  "CloudResourceItem": { "id": "vpc-12345", "..." : "..." },
  "IacResourceItem":   { "id": "vpc-12345", "..." : "..." },
  "State": "Modified",
  "ChangeLog": [
    { "KeyName": "tags.Owner", "CloudValue": "Team A", "IacValue": "Team B" }
  ]
}
```

- `Match` — identical in both files
- `Modified` — exists in both but properties differ; see `ChangeLog`
- `Missing` — exists in cloud but not in IaC

## With your own files

```bash
python -m cloud_iac_analyzer.cli cloud.json iac.json report.json
```

Both inputs must be JSON arrays. Resources are matched by `id`, falling back to `name`.

## Docker (bonus)

```bash
cd docker && docker-compose up
```

Starts LocalStack, runs the analysis, and saves the report to `output/`. Add `--profile upload` to also push the report to the LocalStack S3 bucket.

## Common errors

**`File not found`** — check the path; use an absolute path if needed.

**`Invalid JSON in ...`** — run `python -m json.tool cloud.json` to find the syntax error.

**`Expected a JSON array`** — the top-level structure must be `[...]`, not `{...}`.

**Port 4566 already in use** — run `lsof -i :4566` to find the process, or change the port in `docker-compose.yml`.
