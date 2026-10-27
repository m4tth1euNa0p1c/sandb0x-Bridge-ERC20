"""Arrêt contrôlé du seul relayer local, contrôle des données anciennes et reprise."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import bridge as b
import bridge_runtime as app


def wait(predicate, timeout=60):
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            if predicate():
                return
        except (OSError, urllib.error.URLError) as error:
            # La passerelle peut répondre 502 durant le démarrage effectif.
            # Attente bornée, sans transformer une absence persistante en succès.
            last_error = type(error).__name__
        time.sleep(2)
    raise TimeoutError('État attendu non atteint ; dernier accès : ' + str(last_error))


def wait_for_nominal(read_status, query, record, timeout=60):
    """Attendre la disponibilité métier dans l'API et dans sa collecte Prometheus."""
    record.update({'started_utc': b.utc(), 'passed': False, 'observations': [],
                   'timestamp_semantics': 'evaluation_timestamp_unix_seconds est la date de la requête instantanée Prometheus, pas celle du scrape sous-jacent.'})

    def nominal():
        status = read_status()
        observation = {'observed_utc': b.utc(), 'status_ready': status.get('ready'),
                       'status_stale': status.get('stale'), 'status_updated_utc': status.get('updatedUtc'),
                       'prometheus': {}}
        record['observations'].append(observation)
        for expr in ('up{job="bridge"}', 'bridge:telemetry_fresh', 'bridge_ready'):
            result = query(expr)
            assert len(result) <= 1, f'Série ambiguë : {expr}'
            observation['prometheus'][expr] = {
                'value': float(result[0]['value'][1]) if result else None,
                'evaluation_timestamp_unix_seconds': result[0]['value'][0] if result else None,
            }
        return (status.get('ready') is True and status.get('stale') is False
                and all(sample['value'] == 1 for sample in observation['prometheus'].values()))

    try:
        wait(nominal, timeout)
        record['passed'] = True
    finally:
        record['ended_utc'] = b.utc()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('local-fast', 'local-besu'), default='local-fast')
    parser.add_argument('--capture-name')
    args = parser.parse_args()
    port = 18090 if args.profile == 'local-fast' else 18091
    grafana = 13000 if args.profile == 'local-fast' else 13001
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    source = b.source_snapshot()
    report = {'utc': b.utc(), 'source_commit': b.run(['git', 'rev-parse', 'HEAD'])['stdout'],
              'source': source, 'profile': args.profile, 'checks': [], 'passed': False}
    stopped = False

    def get(url):
        with opener.open(url, timeout=10) as response:
            return json.load(response)

    def query(expr):
        response = get(f'http://127.0.0.1:{port}/api/v1/query?' + urllib.parse.urlencode({'query': expr}))
        assert response['status'] == 'success'
        return response['data']['result']

    def scalar(expr):
        result = query(expr)
        assert len(result) == 1, f'Série absente ou ambiguë : {expr}'
        return float(result[0]['value'][1])

    def check(id_, expected, observed, passed):
        report['checks'].append({'id': id_, 'expected': expected, 'observed': observed, 'passed': bool(passed)})
        assert passed, id_

    try:
        assert app.read_status(b, args.profile)['ready'] is True
        b.container_id(args.profile, 'relayer')  # Refuse plusieurs réplicas ambigus.
        expected = b.read_json(ROOT / 'observability/grafana/dashboards/bridge.json')
        actual = get(f'http://127.0.0.1:{grafana}/api/dashboards/uid/t3l4n-bridge')['dashboard']
        fields = lambda d: [{k: p.get(k) for k in ('id', 'targets', 'fieldConfig')} for p in d['panels']]
        check('served_dashboard', 'Requêtes et mappings réellement servis égaux aux fichiers', actual['uid'], fields(actual) == fields(expected))
        panels = {p['id']: p for p in expected['panels']}
        report['initial_readiness'] = {}
        wait_for_nominal(lambda: app.read_status(b, args.profile), query, report['initial_readiness'])
        b.compose(args.profile, ['--profile', 'bridge', 'stop', '--timeout', '20', 'relayer'], timeout=60)
        stopped = True
        report['stopped_utc'] = b.utc()
        age_expr = panels[6]['targets'][0]['expr']
        wait(lambda: scalar('max(up{job="bridge"}) or vector(0)') == 0 and scalar('max(bridge:telemetry_fresh) or vector(0)') == 0 and scalar(age_expr) >= 35)
        check('unavailable', 'Collecte absente et fraîcheur nulle après arrêt',
              {'up': scalar('max(up{job="bridge"}) or vector(0)'), 'fresh': scalar('max(bridge:telemetry_fresh) or vector(0)')},
              scalar('max(up{job="bridge"}) or vector(0)') == 0 and scalar('max(bridge:telemetry_fresh) or vector(0)') == 0)
        for id_, count in ((5, 1), (10, 2), (22, 1)):
            values = query(panels[id_]['targets'][0]['expr'])
            check(f'historical_timestamp_{id_}', 'Dernière observation horodatée conservée, sans la présenter comme courante',
                  values, len(values) == count and all(float(v['value'][1]) > 0 for v in values))
        age = scalar(age_expr)
        check('age', 'Ancienneté supérieure à 35 secondes', age, age >= 35)
        for id_ in (11, 12, 13, 15, 16, 17, 19, 20):
            values = query(panels[id_]['targets'][0]['expr'])
            check(f'current_business_{id_}', 'Aucune mesure métier courante lorsque le relayer est arrêté', values, values == [])
        values = query(panels[21]['targets'][0]['expr'])
        check('reconciliation_unknown', 'Contrôle d’offre courant indisponible, pas balanced historique', values,
              len(values) == 1 and values[0]['metric'].get('state') == 'Indisponible')
        if args.capture_name:
            assert os.name == 'nt', 'Capture PowerShell disponible uniquement sous Windows'
            b.run(['powershell', '-NoProfile', '-File', ROOT / 'observability/tests/capture.ps1',
                   '-Profile', args.profile, '-Name', args.capture_name], timeout=120)
            report['capture'] = args.capture_name
        report['passed'] = True
    except Exception as error:
        report['error'] = f'{type(error).__name__}: {error}'
    finally:
        try:
            if stopped:
                b.compose(args.profile, ['--profile', 'bridge', 'start', 'relayer'], timeout=60)
                report['restoration_readiness'] = {}
                wait_for_nominal(lambda: app.read_status(b, args.profile), query, report['restoration_readiness'])
                report['restored_utc'] = b.utc()
        except Exception as error:
            report['passed'] = False
            report['restoration_error'] = f'{type(error).__name__}: {error}'
        report['source_unchanged'] = b.source_snapshot()['sha256'] == source['sha256']
        report['passed'] = report['passed'] and report['source_unchanged']
        report['commands'] = b.RECORDS
        report['ended_utc'] = b.utc()
        path = b.LOCAL / (args.profile + '-monitoring-stale.json')
        b.write_json(path, report)
        print(json.dumps({'passed': report['passed'], 'report': str(path), 'error': report.get('error'), 'restoration_error': report.get('restoration_error')}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
