# Connecting a trusted local tool

Run from a clone after `python -m pip install -e .`:

```sh
python examples/custom_tool.py
```

The example solves `a*x+b=0` with Python's `fractions.Fraction` and SymPy. It builds two Profile dictionaries, each with task ID, input/output schemas, global applicability and a local deployment. Its two tiny, different datasets and local approval identities are illustrative fixtures. Failure counts are computed by executing the adapters, but these toy datasets cannot establish relative accuracy. Source revisions `example-v1` are example labels, not pinned source digests. Real comparison requires the same representative dataset and split, controlled settings, recorded adapter/dependency revisions, independent review and meaningful uncertainty.

The script writes profiles and a separate unsigned approval ledger to a temporary directory. Each record binds the profile's artifact identity, task contract, dataset and metric. It computes an evaluation digest and records `approved_by` and `approved_at` separately. To revoke, add that digest to the ledger's `revoked` list and reload the service. To reapprove a modified version, evaluate and review it again and approve its new digest. A digest detects changes to its bound record; it does not establish correctness or reviewer identity.

Register code explicitly from a trusted application, not from downloaded metadata:

```python
from umr.execution import AdapterRegistry
from umr.service import RouterService

registry = AdapterRegistry(additional_adapters={"my-adapter": my_trusted_adapter})
service = RouterService("path/to/profiles", approval_ledger_path="path/to/ledger.json",
                        adapter_registry=registry)
result = service.handle({"task_id": "my.task", "inputs": {}, "execute": True})
```

An adapter exposes `execute(inputs)` and returns an object matching its Profile output schema. The application must review and install the adapter itself; this process executes its code with application privileges and is not sandboxed. Built-in adapter IDs cannot be replaced. `umr serve` does not load these adapters automatically. Default routing does not compare numerical quality unless `require_quality_comparison` and `comparison_metric_id` are supplied. In the example, the normal request selects by existing ranking rules; strict comparison abstains because the two fixture datasets differ. Changed revision and revoked approval also abstain. Invalid input and missing adapter are rejected before execution; `a=0` yields a structured execution failure.

For abstention inspect `decision.reason`, `decision.rejected` and, if present, `decision.comparison.reasons`; repair inputs or obtain applicable evidence, rather than retry blindly. For selected results inspect `provenance` and `execution.status` / `execution.error`. HTTP normally returns 200 even on abstention or adapter failure. See `examples/http_integration.py` and [evidence details](../outputs/evidence-routing-evaluation.md).
