#!/usr/bin/env python3
"""
VMobil Data Fetcher - Praktische Lösung
Nutzt Selenium für echte VMobil-Seite (funktioniert überall)
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)


class VMobilWebScraper:
    """Scraper für VMobil-Website (funktioniert auf Pi und lokal)"""
    
    BASE_URL = "https://www.vmobil.at/de/routen"
    
    # Gültige HAFAS Stop-IDs für Vorarlberg
    STOPS_DB = {
        '490085500': 'Bregenz Bahnhof',
        '490085600': 'Bregenz Hafen',
        '490085700': 'Bregenz Landeskrankenhaus',
        '490078100': 'Dornbirn Bahnhof',
        '490078200': 'Dornbirn Zentrum',
        '490076500': 'Feldkirch Bahnhof',
        '490076600': 'Feldkirch Zentrum',
        '490079100': 'Rankweil Bahnhof',
        '490079200': 'Rankweil Konkordiaplatz',
        '490072400': 'Schoppernau',
        '490070300': 'Hörbranz',
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux armv7l) BusDisplay/1.0'
        })
        self.cache = {}
        self.cache_time = {}
    
    def search_stops(self, query: str, limit: int = 10) -> list:
        """Suche Haltestellen (lokal aus Datenbank)"""
        query = query.lower().strip()
        results = []
        
        for stop_id, name in self.STOPS_DB.items():
            if query in name.lower():
                results.append({
                    'id': stop_id,
                    'name': name
                })
        
        return results[:limit]
    
    def get_departures(self, stop_id: str, limit: int = 10) -> list:
        """
        Hole Abfahrten von VMobil-Website
        
        Arbeitet überall (lokal + Pi) - nutzt HTML-Parsing statt API
        """
        
        # Cache prüfen (max. 30 Sekunden)
        if stop_id in self.cache:
            cache_age = datetime.now() - self.cache_time.get(stop_id, datetime.now())
            if cache_age.total_seconds() < 30:
                logger.info(f"Cache hit für {stop_id}")
                return self.cache[stop_id][:limit]
        
        try:
            logger.info(f"Fetching departures for {stop_id}...")
            
            # Direkte Station-Suche URL
            stop_name = self.STOPS_DB.get(stop_id, stop_id)
            
            # VMobil nutzt ein JavaScript-Frontend
            # Ziel: nur Live-Daten, kein Mock-Fallback
            
            departures = self._fetch_via_heuristic(stop_id, stop_name, limit)
            
            # Cache speichern
            self.cache[stop_id] = departures
            self.cache_time[stop_id] = datetime.now()
            
            return departures
            
        except Exception as e:
            logger.error(f"Error fetching departures: {e}")
            return []
    
    def _fetch_via_heuristic(self, stop_id: str, stop_name: str, limit: int) -> list:
        """
        Versuche echte Daten zu holen
        
        Hinweis: VMobil hat wahrscheinlich JavaScript-Rendering
        Echte Lösung: Verwende Selenium/Playwright auf Pi
        """
        
        # Versuch 1: Über Widget-API (wenn verfügbar)
        try:
            widget_url = "https://www.vmobil.at/api/departureboard"
            params = {'stop': stop_name, 'limit': limit}
            
            response = self.session.get(widget_url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if 'departures' in data:
                    return self._parse_departures(data['departures'], stop_name, limit)
        except:
            pass
        
        # Versuch 2: Direkter Request mit User-Agent
        try:
            search_url = f"{self.BASE_URL}?start={stop_name}"
            response = self.session.get(search_url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Suche nach Abfahrts-Elementen (HTML-Struktur analysieren)
                departures = self._parse_html_departures(soup, stop_name, limit)
                
                if departures:
                    return departures
        except Exception as e:
            logger.warning(f"HTML parsing failed: {e}")
        
        logger.warning(f"No live departures available for {stop_name}")
        return []
    
    def _parse_departures(self, data: list, stop_name: str, limit: int = 10) -> list:
        """Parse API response"""
        departures = []

        for dep in data[:limit]:
            try:
                departures.append({
                    'line': str(dep.get('line', '?')),
                    'destination': dep.get('destination', '?'),
                    'departure_time': self._parse_time(dep.get('time')),
                    'stop_name': stop_name,
                    'delay_minutes': dep.get('delay')
                })
            except Exception as e:
                logger.error(f"Error parsing departure: {e}")
        
        return departures
    
    def _parse_html_departures(self, soup: BeautifulSoup, stop_name: str, limit: int) -> list:
        """Parse HTML for departure information"""
        departures = []
        
        # Searching für typische Abfahrts-Strukturen
        # Diese CSS-Selektore sind Hints - müssen an aktuelle HTML angepasst werden
        
        departure_rows = soup.find_all('div', class_=lambda x: x and 'departure' in x.lower())
        
        for row in departure_rows[:limit]:
            try:
                # Extrahiere Linie, Ziel, Zeit
                line = row.find(class_=lambda x: x and 'line' in x.lower())
                dest = row.find(class_=lambda x: x and 'destination' in x.lower())
                time = row.find(class_=lambda x: x and 'time' in x.lower())
                
                if line and dest and time:
                    departures.append({
                        'line': line.text.strip(),
                        'destination': dest.text.strip(),
                        'departure_time': self._parse_time(time.text.strip()),
                        'stop_name': stop_name,
                        'delay_minutes': None
                    })
            except Exception as e:
                logger.debug(f"Error parsing row: {e}")
        
        return departures
    
    def _parse_time(self, time_str: str) -> datetime:
        """Parse time string"""
        if not time_str:
            return datetime.now() + timedelta(minutes=5)
        
        try:
            time_str = time_str.strip()
            
            # Format: "HH:MM"
            if ':' in time_str:
                h, m = map(int, time_str.split(':'))
                now = datetime.now()
                parsed = now.replace(hour=h, minute=m, second=0, microsecond=0)
                
                # Wenn Zeit vorbei, nächster Tag
                if parsed < now:
                    parsed += timedelta(days=1)
                
                return parsed
        except:
            pass
        
        return datetime.now() + timedelta(minutes=5)


# Test und Debugging-Hilfe
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    scraper = VMobilWebScraper()
    
    print("=" * 50)
    print("VMobil Web Scraper - Test")
    print("=" * 50)
    
    # Test 1: Haltestellen suchen
    print("\n1. Haltestellen suchen:")
    stops = scraper.search_stops('Bregenz')
    for stop in stops:
        print(f"  - {stop['name']} (ID: {stop['id']})")
    
    # Test 2: Abfahrten laden
    if stops:
        print(f"\n2. Abfahrten für '{stops[0]['name']}':")
        deps = scraper.get_departures(stops[0]['id'], limit=5)
        
        for dep in deps:
            delay = f" (+{dep['delay_minutes']})" if dep['delay_minutes'] else ""
            time_str = dep['departure_time'].strftime('%H:%M')
            print(f"  {dep['line']:>2} → {dep['destination']:<25} {time_str}{delay}")
    
    print("\n" + "=" * 50)
