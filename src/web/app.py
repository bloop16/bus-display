"""
Flask web interface for bus display configuration.
"""
from flask import Flask, render_template, jsonify, request
import json
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


def create_app(testing=False, api=None, on_config_saved=None):
    """Application factory. api: geteilte VMobilAPI-Instanz aus main.py (vermeidet Doppel-Init).
    on_config_saved: optionaler Callback – wird nach jedem Config-Save aufgerufen (Display-Update)."""
    app = Flask(__name__)
    app.config['TESTING'] = testing

    BASE_DIR = Path(__file__).parent.parent.parent
    CONFIG_DIR = BASE_DIR / 'config'
    CONFIG_FILE = CONFIG_DIR / 'stops.json'

    CONFIG_DIR.mkdir(exist_ok=True)

    if api is None:
        from src.api import VMobilAPI
        api = VMobilAPI()

    def _load_config() -> dict:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                return json.load(f)
        return {'stops': [], 'destinations': []}

    def _save_config(config: dict):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)

    def _normalize_destinations(destinations: list) -> list:
        """Normalisiert destinations/via_stops für robustes GTFS-Matching."""
        if not isinstance(destinations, list):
            return []

        normalized = []
        for entry in destinations:
            if not isinstance(entry, dict):
                continue

            icon = entry.get('icon')
            keywords = entry.get('keywords') if isinstance(entry.get('keywords'), list) else []

            via_stops_normalized = []
            for via in (entry.get('via_stops') or []):
                if not isinstance(via, dict):
                    continue

                via_name = via.get('name')
                if not via_name:
                    continue

                via_id = via.get('id')
                via_ids = via.get('ids') if isinstance(via.get('ids'), list) else None
                if not via_ids:
                    via_ids = [via_id] if via_id else []

                if len(via_ids) <= 1:
                    try:
                        matches = api.search_stops(via_name)
                        exact = next((m for m in matches if m.get('name') == via_name), None)
                        if exact:
                            via_id = exact.get('id') or via_id
                            via_ids = exact.get('ids') or via_ids
                    except Exception as e:
                        logger.debug(f'Via-Stop normalization lookup failed for {via_name}: {e}')

                via_ids = [sid for sid in via_ids if sid]
                if via_id and via_id not in via_ids:
                    via_ids.insert(0, via_id)
                if not via_id and via_ids:
                    via_id = via_ids[0]

                via_stops_normalized.append({
                    'id': via_id,
                    'name': via_name,
                    'ids': via_ids,
                })

            normalized.append({
                'icon': icon,
                'keywords': keywords,
                'via_stops': via_stops_normalized,
            })

        return normalized

    @app.route('/')
    def index():
        return render_template('index.html')

    # ── Stops ────────────────────────────────────────────────────

    @app.route('/api/stops')
    def api_search_stops():
        """Search bus stops"""
        query = request.args.get('q', '')
        if not query:
            return jsonify([])
        try:
            return jsonify(api.search_stops(query))
        except Exception as e:
            logger.error(f'Stop search failed: {e}')
            return jsonify({'error': str(e)}), 500

    # ── Departures ───────────────────────────────────────────────

    @app.route('/api/departures')
    def api_get_departures():
        """
        Get departures.
        - Without stop_id: aggregates all configured stops (max 6), with icon matching
        - With stop_id: single stop query (backwards compatible)
        """
        stop_id = request.args.get('stop_id')
        limit = int(request.args.get('limit', 6))

        try:
            if stop_id:
                departures = api.get_departures(stop_id=stop_id, limit=limit)
            else:
                config = _load_config()
                stops = config.get('stops', [])
                destinations = config.get('destinations', [])
                departures = api.get_all_departures(stops, destinations, limit=limit)

            return jsonify([dep.to_dict() for dep in departures])
        except Exception as e:
            logger.error(f'Departure fetch failed: {e}')
            return jsonify({'error': str(e)}), 500

    # ── Config ───────────────────────────────────────────────────

    @app.route('/api/config', methods=['GET', 'POST'])
    def api_config():
        """Get or save full configuration (stops + destinations)"""
        if request.method == 'GET':
            return jsonify(_load_config())

        config = request.get_json()
        if not config or 'stops' not in config:
            return jsonify({'error': 'Invalid config'}), 400
        try:
            config['destinations'] = _normalize_destinations(config.get('destinations', []))
            _save_config(config)
            logger.info(f'Config saved: {len(config["stops"])} stops, '
                        f'{len(config.get("destinations", []))} destinations')
            # Display sofort aktualisieren (falls BusDisplay-Instanz verfügbar)
            if on_config_saved:
                try:
                    on_config_saved()
                except Exception as cb_err:
                    logger.warning(f'Config-Callback fehlgeschlagen: {cb_err}')
            return jsonify({'status': 'ok'})
        except Exception as e:
            logger.error(f'Config save failed: {e}')
            return jsonify({'error': str(e)}), 500

    # ── Destinations ─────────────────────────────────────────────

    @app.route('/api/destinations', methods=['GET', 'POST'])
    def api_destinations():
        """Get or save destinations configuration"""
        if request.method == 'GET':
            return jsonify(_load_config().get('destinations', []))

        destinations = request.get_json()
        if not isinstance(destinations, list):
            return jsonify({'error': 'Expected a list of destinations'}), 400
        try:
            config = _load_config()
            config['destinations'] = _normalize_destinations(destinations)
            _save_config(config)
            logger.info(f'Destinations saved: {len(destinations)} entries')
            return jsonify({'status': 'ok'})
        except Exception as e:
            logger.error(f'Destinations save failed: {e}')
            return jsonify({'error': str(e)}), 500

    # ── WiFi ─────────────────────────────────────────────────────

    @app.route('/wifi')
    def wifi_setup():
        return render_template('wifi_setup.html')

    @app.route('/api/wifi/status')
    def wifi_status():
        try:
            from src.wifi.ap_manager import APManager
            ap = APManager()
            ssid = None
            if ap.is_wifi_connected():
                import subprocess
                result = subprocess.run(['iwgetid', '-r'], capture_output=True, text=True)
                if result.returncode == 0:
                    ssid = result.stdout.strip()
            return jsonify({
                'connected': ap.is_wifi_connected(),
                'ssid': ssid,
                'configured': ap.is_wifi_configured()
            })
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    @app.route('/api/wifi/connect', methods=['POST'])
    def wifi_connect():
        try:
            data = request.json
            ssid = data.get('ssid')
            password = data.get('password')
            if not ssid or not password:
                return jsonify({'error': 'SSID and password required'}), 400
            from src.wifi.ap_manager import APManager
            ap = APManager()
            if ap.connect_to_wifi(ssid, password):
                return jsonify({'success': True})
            return jsonify({'error': 'Connection failed'}), 500
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=False)
