from datetime import datetime, timedelta

from src.api.vmobil import Departure, VMobilAPI


class _FakeGTFS:
    def __init__(self):
        self.find_calls = 0

    def search_stops(self, query, limit=10):
        if query == 'Rankweil Konkordiaplatz':
            return [{'id': '490079200', 'name': 'Rankweil Konkordiaplatz', 'ids': ['490079200', '490079201']}]
        return []

    def trip_passes_stop_after(self, trip_id, boarding_stop_id, via_stop_id):
        return trip_id == 'TRIP-1' and boarding_stop_id == '490079100' and via_stop_id == '490079201'

    def find_trip_id_for_departure(self, stop_id, line, departure_time, destination=None, max_diff_minutes=8):
        self.find_calls += 1
        if stop_id == '490079100' and line == '455':
            return 'TRIP-1'
        return None


class TestDestinationIconMatching:
    def test_match_resolves_legacy_single_via_id_to_group_ids(self):
        api = VMobilAPI.__new__(VMobilAPI)
        api._via_ids_cache = {}

        dep = Departure(
            line='455',
            destination='Bregenz',
            departure_time=datetime.now() + timedelta(minutes=3),
            stop_name='Rankweil Bahnhof',
            trip_id='TRIP-1',
            boarding_stop_id='490079100',
        )
        destinations = [
            {
                'icon': 'home',
                'via_stops': [{'id': '490079200', 'name': 'Rankweil Konkordiaplatz'}],
            }
        ]

        icons = VMobilAPI._match_destination_icons(api, dep, destinations, _FakeGTFS())

        assert icons == ['home']

    def test_get_all_departures_infers_trip_id_and_matches_icon(self):
        api = VMobilAPI.__new__(VMobilAPI)
        api.use_gtfs = True
        api.gtfs = _FakeGTFS()
        api._via_ids_cache = {}

        def _fake_get_departures(stop_id=None, stop_name=None, limit=10):
            return [
                Departure(
                    line='455',
                    destination='Bregenz',
                    departure_time=datetime.now() + timedelta(minutes=5),
                    stop_name='Rankweil Bahnhof',
                )
            ]

        api.get_departures = _fake_get_departures

        deps = VMobilAPI.get_all_departures(
            api,
            stops=[{'id': '490079100', 'name': 'Rankweil Bahnhof'}],
            destinations=[
                {
                    'icon': 'home',
                    'via_stops': [{'id': '490079200', 'name': 'Rankweil Konkordiaplatz'}],
                }
            ],
            limit=6,
        )

        assert len(deps) == 1
        assert deps[0].trip_id == 'TRIP-1'
        assert deps[0].icons == ['home']
        assert api.gtfs.find_calls == 1
