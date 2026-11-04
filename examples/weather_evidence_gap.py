"""Offline example: a real deployment has no approved comparable precipitation evidence."""
from pathlib import Path
from umr.service import RouterService


def main():
    service = RouterService(Path(__file__).resolve().parents[1] / 'profiles')
    response = service.handle({
        'task_id': 'weather.precipitation_forecast',
        'inputs': {'latitude': 24.15, 'longitude': 120.67, 'target_date': '2026-11-05'},
        'constraints': {'require_quality_comparison': True, 'comparison_metric_id': 'precipitation-error'},
        'execute': False,
    })
    print('Real deployment: Open-Meteo WeatherNext 2; no network call')
    print('WeatherBench Z500 scores do not establish single-point precipitation performance.')
    print('decision:', response['decision']['status'])
    print('reason:', response['decision'].get('reason'))
    print('details:', response['decision'].get('comparison', {}).get('reasons', []))
    if response['decision']['status'] != 'abstain':
        raise RuntimeError('Expected abstention without comparable approved evidence')


if __name__ == '__main__':
    main()
