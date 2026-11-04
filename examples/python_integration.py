"""Run from the repository root: python examples/python_integration.py."""
from pathlib import Path

from umr.service import RouterService


def show(service, body):
    response = service.handle(body)
    decision = response['decision']
    print('decision:', decision['status'])
    if decision['status'] == 'abstain':
        print('reason:', decision['reason'])
        return
    print('resource:', response['provenance']['profile_id'])
    print('source:', response['provenance']['source'])
    execution = response.get('execution', {})
    print('execution:', execution.get('status'))
    if execution.get('status') == 'failed':
        print('error:', execution['error']['code'], execution['error']['message'])
    elif execution.get('status') == 'completed':
        print('result:', execution['result'])


def main():
    service = RouterService(Path(__file__).resolve().parents[1] / 'profiles')
    request = {'task_id': 'math.solve_equation', 'inputs': {'equation': 'x**2 - 4 = 0'}, 'execute': True}
    print('SUCCESS')
    show(service, request)
    print('ABSTAIN: independent evidence required')
    show(service, {**request, 'constraints': {'require_independent_evidence': True}})
    print('FAILURE: expression exceeds solver limits')
    show(service, {**request, 'inputs': {'equation': 'x**13=1'}})


if __name__ == '__main__':
    main()
