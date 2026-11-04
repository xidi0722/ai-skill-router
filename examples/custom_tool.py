"""Offline custom adapter example; evaluation datasets and approvals are illustrative fixtures."""
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from umr.evidence import capability_contract_digest, contract_evaluation_digest
from umr.execution import AdapterRegistry, ExecutionError
from umr.service import RouterService

ROOT = Path(__file__).resolve().parents[1]
TASK = 'math.linear_equation'
REQUEST = {'task_id': TASK, 'inputs': {'a': 2, 'b': -4}, 'execute': True}
METRIC = 'fixture.failures'


class FractionAdapter:
    def execute(self, inputs):
        a, b = inputs['a'], inputs['b']
        if a == 0:
            raise ExecutionError('a must be nonzero')
        return {'x': str(Fraction(-b, a))}


class SympyLinearAdapter:
    def execute(self, inputs):
        import sympy
        a, b = inputs['a'], inputs['b']
        if a == 0:
            raise ExecutionError('a must be nonzero')
        x = sympy.Symbol('x')
        return {'x': str(sympy.solve(a * x + b, x)[0])}


def profile(name, adapter, cases):
    # Start from a valid schema version; only these declared adapters can execute.
    result = json.loads((ROOT / 'profiles' / 'sympy-equation.json').read_text(encoding='utf-8'))
    result['id'] = 'urn:example:' + name
    result['display_name'] = name
    result['source'].update({'publisher': 'AI Skill Router contributors',
                             'artifact_url': 'https://github.com/xidi0722/ai-skill-router/blob/main/examples/custom_tool.py',
                             'artifact_id': name, 'revision': 'example-v1', 'artifact_digest': None,
                             'license': {'code': 'Apache-2.0', 'weights': None, 'data': None}})
    result['capabilities'] = [{
        'task_id': TASK,
        'input_schema': {'type': 'object', 'required': ['a', 'b'], 'properties': {'a': {'type': 'integer'}, 'b': {'type': 'integer'}}},
        'output_schema': {'type': 'object', 'required': ['x'], 'properties': {'x': {'type': 'string'}}},
        'applicability': {'geography': 'global'}, 'data_requirements': [],
    }]
    result['deployments'][0].update({'id': name + '-local', 'adapter': name})
    # The labels and tiny distinct datasets are fixtures; the count is computed by running the adapter.
    failures = sum(adapter.execute({'a': a, 'b': b})['x'] != expected for a, b, expected in cases)
    dataset_bytes = json.dumps(cases, separators=(',', ':')).encode()
    result['evaluations'] = [{
        'task_id': TASK, 'evidence_level': 'reproduced',
        'artifact': {'id': name, 'revision': 'example-v1', 'digest': None},
        'contract_digest': capability_contract_digest(result, TASK),
        'dataset': {'id': 'fixture-' + name, 'revision': 'v1', 'split': 'test', 'config_digest': 'sha256:' + sha256(dataset_bytes).hexdigest()},
        'applicability': {'region': 'global', 'horizon_days': None, 'resolution': None},
        'metrics': [{'id': METRIC, 'value': failures, 'unit': 'failures', 'direction': 'lower', 'sample_count': len(cases)}],
        'source': {'url': 'https://github.com/xidi0722/ai-skill-router', 'evaluator': 'local illustrative fixture'},
    }]
    return result


def run():
    adapters = {'fraction-linear': FractionAdapter(), 'sympy-linear': SympyLinearAdapter()}
    profiles = [
        profile('fraction-linear', adapters['fraction-linear'], [(1, -2, '2'), (2, -4, '2')]),
        profile('sympy-linear', adapters['sympy-linear'], [(3, -6, '2'), (4, -8, '2')]),
    ]
    digests = [contract_evaluation_digest(p, p['evaluations'][0]) for p in profiles]
    ledger = {'approvals': {d: {'approved_by': 'example-admin', 'approved_at': '2026-11-04T00:00:00Z'} for d in digests}, 'revoked': []}
    with TemporaryDirectory() as temp:
        base = Path(temp)
        catalog = base / 'profiles'
        catalog.mkdir()
        def save():
            for i, item in enumerate(profiles):
                (catalog / f'{i}.json').write_text(json.dumps(item), encoding='utf-8')
            (base / 'ledger.json').write_text(json.dumps(ledger), encoding='utf-8')
        def service(registry):
            save()
            return RouterService(catalog, approval_ledger_path=base / 'ledger.json', adapter_registry=registry)
        registry = AdapterRegistry(additional_adapters=adapters)
        normal = service(registry).handle(REQUEST)
        invalid = service(registry).handle({**REQUEST, 'inputs': {'a': 'bad', 'b': -4}})
        missing = service(AdapterRegistry()).handle(REQUEST)
        strict = {**REQUEST, 'constraints': {'require_quality_comparison': True, 'comparison_metric_id': METRIC}}
        incomparable = service(registry).handle(strict)
        profiles[0]['source']['revision'] = 'example-v2'
        changed = service(registry).handle(strict)
        profiles[0]['source']['revision'] = 'example-v1'
        ledger['revoked'] = [digests[0]]
        revoked = service(registry).handle(strict)
        failed = service(registry).handle({**REQUEST, 'inputs': {'a': 0, 'b': 2}})
        return {'success': normal, 'invalid': invalid, 'unregistered': missing, 'incomparable': incomparable,
                'revision_changed': changed, 'revoked': revoked, 'execution_failure': failed}


def main():
    print('Two local implementations; evaluations, versions and approvals are illustrative fixtures, not benchmark claims.')
    results = run()
    for name, response in results.items():
        decision = response['decision']
        print(f"{name}: {decision['status']}")
        if decision['status'] == 'selected':
            print('  selected:', decision['selected']['profile_id'])
            print('  execution:', response.get('execution', {}))
        else:
            print('  reason:', decision['reason'])
            print('  detail:', decision.get('comparison', {}).get('reasons', decision.get('rejected', [])))


if __name__ == '__main__':
    main()
