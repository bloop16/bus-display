import json
from pathlib import Path

import src.web.app as web_app


class _FakeAPI:
    def search_stops(self, query):
        if query == 'Rankweil Konkordiaplatz':
            return [
                {
                    'id': '490079200',
                    'name': 'Rankweil Konkordiaplatz',
                    'ids': ['490079200', '490079201'],
                }
            ]
        return []


class TestDestinationNormalization:
    def test_api_destinations_normalizes_via_stop_ids(self, tmp_path):
        fake_root = tmp_path / 'app-root'
        fake_src_web = fake_root / 'src' / 'web'
        fake_src_web.mkdir(parents=True, exist_ok=True)

        original_file = web_app.__file__
        try:
            web_app.__file__ = str(fake_src_web / 'app.py')
            app = web_app.create_app(testing=True, api=_FakeAPI())
            client = app.test_client()

            payload = [
                {
                    'icon': 'home',
                    'via_stops': [{'id': '490079200', 'name': 'Rankweil Konkordiaplatz'}],
                }
            ]

            response = client.post(
                '/api/destinations',
                data=json.dumps(payload),
                content_type='application/json',
            )
            assert response.status_code == 200

            config_path = fake_root / 'config' / 'stops.json'
            saved = json.loads(config_path.read_text())
            via = saved['destinations'][0]['via_stops'][0]
            assert via['id'] == '490079200'
            assert via['ids'] == ['490079200', '490079201']
        finally:
            web_app.__file__ = original_file
