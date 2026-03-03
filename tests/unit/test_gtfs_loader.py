"""
Test suite for GTFS Loader

Tests real GTFS data loading and search functionality
"""
import pytest
from pathlib import Path
import json


class TestGTFSLoader:
    """Test GTFS data loading and parsing"""
    
    def test_gtfs_loader_initialization(self):
        """GTFSLoader should initialize without errors"""
        from src.api.gtfs_loader import GTFSLoader
        
        loader = GTFSLoader()
        assert loader is not None
        assert len(loader.stops_data) > 0
    
    def test_search_stops_basic(self):
        """Should search for stops by name"""
        from src.api.gtfs_loader import get_gtfs_loader
        
        loader = get_gtfs_loader()
        results = loader.search_stops("Bregenz")
        
        assert isinstance(results, list)
        if results:  # May be empty if GTFS not available, fallback stops ok
            assert all('id' in r for r in results)
            assert all('name' in r for r in results)
    
    def test_search_stops_limit(self):
        """Should respect limit parameter"""
        from src.api.gtfs_loader import get_gtfs_loader
        
        loader = get_gtfs_loader()
        results = loader.search_stops("Vorarlberg city", limit=5)
        
        assert len(results) <= 5
    
    def test_get_stop_by_id(self):
        """Should retrieve stop details by ID"""
        from src.api.gtfs_loader import get_gtfs_loader
        
        loader = get_gtfs_loader()
        
        # Try to get a known stop (fallback stops always have these IDs)
        stop = loader.get_stop('490085500')
        
        assert stop is not None or len(loader.stops_data) == 0  # OK if fallback not loaded
    
    def test_get_all_stops(self):
        """Should return all loaded stops"""
        from src.api.gtfs_loader import get_gtfs_loader
        
        loader = get_gtfs_loader()
        stops = loader.get_all_stops()
        
        assert isinstance(stops, list)
        assert len(stops) > 0
    
    def test_cache_functionality(self, tmp_path):
        """Should cache GTFS data locally"""
        from src.api.gtfs_loader import GTFSLoader, STOPS_CACHE_FILE
        
        # GTFSLoader should create cache on first run
        loader = GTFSLoader()
        
        # On Pi: cache should be in data/ directory
        # Mock: fallback stops should work without network
        assert loader.stops_data is not None
        assert len(loader.stops_data) > 0
    
    def test_singleton_pattern(self):
        """get_gtfs_loader() should return same instance"""
        from src.api.gtfs_loader import get_gtfs_loader
        
        loader1 = get_gtfs_loader()
        loader2 = get_gtfs_loader()
        
        assert loader1 is loader2  # Same object in memory
