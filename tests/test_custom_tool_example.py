import importlib.util
from pathlib import Path

import pytest

from umr.execution import AdapterRegistry, SympyEquationAdapter


def test_custom_tool_end_to_end():
    path = Path(__file__).resolve().parents[1] / 'examples' / 'custom_tool.py'
    spec = importlib.util.spec_from_file_location('custom_tool_example', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results = module.run()
    assert results['success']['execution']['result']['x'] == '2'
    for key in ('invalid', 'unregistered', 'incomparable', 'revision_changed', 'revoked'):
        assert results[key]['decision']['status'] == 'abstain'
    assert results['incomparable']['decision']['comparison']['status'] == 'incomparable'
    assert any('revoked' in item['reason'] for item in results['revoked']['decision']['comparison']['reasons'])
    assert results['execution_failure']['execution']['error']['code'] == 'adapter_execution_failed'


def test_explicit_registry_does_not_replace_builtin_or_accept_invalid_adapter():
    with pytest.raises(ValueError):
        AdapterRegistry({'sympy-equation': SympyEquationAdapter()})
    with pytest.raises(ValueError):
        AdapterRegistry({'custom': object()})
