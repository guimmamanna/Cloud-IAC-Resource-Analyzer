# Architecture

## Overview

```text
cloud_resources.json ──┐
                        ├──► ResourceAnalyzer ──► report.json
iac_resources.json  ───┘
```

The analyzer has no network calls, no database, and no mutable global state. It loads two JSON files, runs a pure in-memory comparison, and writes a JSON report.

---

## Modules

### `analyzer.py`

All the logic lives in `ResourceAnalyzer`. On construction it builds two lookup dicts from the IaC list (one keyed by `id`, one by `name`) so each cloud resource can be matched in O(1) instead of scanning the list. The actual dict contents are just references to the original objects — no copying.

The three standalone functions (`load_json_file`, `save_report`, `generate_analysis_report`) handle I/O and orchestration and are kept outside the class so they can be used independently.

### `cli.py`

Standard argparse wrapper. Both input files are validated before the analyzer is invoked, so errors surface with a clean message rather than a mid-run traceback. The output directory is created automatically if it doesn't exist.

---

## Matching

Resources are matched by `id` first. If the cloud resource has no `id`, matching falls back to `name`. The two fields use separate lookup dicts — if they shared one namespace, a resource with `id: "foo"` could silently be overwritten by a different resource with `name: "foo"`.

Resources with neither `id` nor `name` are indexed by position (`_index_0`, `_index_1`, …) as a last resort, but positional matching is fragile if either file reorders resources between exports.

---

## Comparison

`_compare_values` recurses into both structures simultaneously:

- **Dicts** — takes the union of both keysets. Keys missing from one side are reported as a change with `None` on the missing side.
- **Arrays** — compares element-by-element by index up to `max(len(cloud), len(iac))`. This means array order matters: reordering security group rules, subnet lists, etc. will show up as changes even if the logical content is identical.
- **Primitives** — direct equality check. Type mismatches (e.g. `"true"` vs `true`) are caught here.

Property paths use dot notation (`tags.Owner`) for dict keys and bracket notation (`subnets[1].cidr_block`) for array indices.

---

## Design decisions

**Separate `id`/`name` lookup dicts.** The original implementation used a single flat dict for both fields, which meant `id` values and `name` values competed in the same namespace. Splitting them eliminates that category of false match.

**Index-based array comparison.** Matching array elements by value or by a nested key would be more semantically correct for some resource types, but it adds significant complexity and makes the output harder to reason about. Index-based comparison is simple, predictable, and explicit about what it does.

**Report only, no remediation.** The tool produces a diff and stops there. Applying changes automatically would require resource-type-specific logic and carries real risk — better left to the operator.

**`ResourceAnalyzer` as a class.** Not strictly necessary for this size of problem, but it keeps the lookup dicts and the report together without passing them around as arguments, and it gives callers a clean way to re-run the analysis on different inputs.
