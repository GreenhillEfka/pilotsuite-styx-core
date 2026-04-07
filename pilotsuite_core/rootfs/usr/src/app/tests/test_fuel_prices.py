"""Tests for Fuel Price Tracker with Tankerkoenig integration (v5.17.0)."""

import time
from datetime import datetime

import pytest

from copilot_core.regional.fuel_prices import (
    FuelPriceTracker,
    FuelStation,
    FuelPrices,
    CostPer100km,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


def _make_tankerkoenig_response(
    stations: list[dict] | None = None,
) -> dict:
    """Create a Tankerkoenig-style API response."""
    if stations is None:
        stations = [
            {
                "id": "s1",
                "name": "Shell Berlin",
                "brand": "Shell",
                "street": "Hauptstr. 1",
                "place": "Berlin",
                "lat": 52.52,
                "lng": 13.405,
                "dist": 1.5,
                "diesel": 1.459,
                "e5": 1.659,
                "e10": 1.589,
                "isOpen": True,
            },
            {
                "id": "s2",
                "name": "Aral Berlin",
                "brand": "Aral",
                "street": "Berliner Str. 5",
                "place": "Berlin",
                "lat": 52.51,
                "lng": 13.41,
                "dist": 2.3,
                "diesel": 1.479,
                "e5": 1.679,
                "e10": 1.599,
                "isOpen": True,
            },
            {
                "id": "s3",
                "name": "Total Berlin",
                "brand": "Total",
                "street": "Friedrichstr. 10",
                "place": "Berlin",
                "lat": 52.53,
                "lng": 13.39,
                "dist": 3.0,
                "diesel": 1.439,
                "e5": 1.649,
                "e10": 1.579,
                "isOpen": True,
            },
        ]
    return {"ok": True, "stations": stations}


@pytest.fixture
def tracker():
    return FuelPriceTracker(
        latitude=52.52,
        longitude=13.405,
        radius_km=10.0,
        grid_price_eur_kwh=0.30,
    )


@pytest.fixture
def tracker_with_data(tracker):
    tracker.process_tankerkoenig_response(_make_tankerkoenig_response())
    return tracker


# ── Test initialization ──────────────────────────────────────────────────


class TestInit:
    def test_default_location(self, tracker):
        assert tracker._lat == 52.52
        assert tracker._lon == 13.405

    def test_default_radius(self, tracker):
        assert tracker._radius == 10.0

    def test_default_grid_price(self, tracker):
        assert tracker._grid_price == 0.30

    def test_no_api_key(self, tracker):
        assert not tracker.has_api_key

    def test_no_stations(self, tracker):
        assert tracker.station_count == 0

    def test_cache_not_valid(self, tracker):
        assert not tracker.cache_valid


# ── Test Tankerkoenig parsing ────────────────────────────────────────────


class TestTankerkoenigParsing:
    def test_parse_stations(self, tracker):
        data = _make_tankerkoenig_response()
        stations = tracker.process_tankerkoenig_response(data)
        assert len(stations) == 3

    def test_station_fields(self, tracker):
        data = _make_tankerkoenig_response()
        stations = tracker.process_tankerkoenig_response(data)
        s = stations[0]
        assert s.name == "Shell Berlin"
        assert s.brand == "Shell"
        assert s.diesel == 1.459
        assert s.e5 == 1.659
        assert s.e10 == 1.589

    def test_station_distance(self, tracker):
        data = _make_tankerkoenig_response()
        stations = tracker.process_tankerkoenig_response(data)
        assert stations[0].dist == 1.5

    def test_station_open(self, tracker):
        data = _make_tankerkoenig_response()
        stations = tracker.process_tankerkoenig_response(data)
        assert stations[0].is_open is True

    def test_closed_station(self, tracker):
        data = _make_tankerkoenig_response([
            {"id": "s1", "name": "Closed", "brand": "", "street": "",
             "place": "", "lat": 0, "lng": 0, "dist": 1,
             "diesel": 1.5, "e5": 1.7, "e10": 1.6, "isOpen": False}
        ])
        stations = tracker.process_tankerkoenig_response(data)
        assert stations[0].is_open is False

    def test_error_response(self, tracker):
        data = {"ok": False, "message": "API key invalid"}
        stations = tracker.process_tankerkoenig_response(data)
        assert len(stations) == 0

    def test_empty_stations(self, tracker):
        data = {"ok": True, "stations": []}
        stations = tracker.process_tankerkoenig_response(data)
        assert len(stations) == 0

    def test_cache_updated(self, tracker):
        tracker.process_tankerkoenig_response(_make_tankerkoenig_response())
        assert tracker.cache_valid is True

    def test_price_history_recorded(self, tracker):
        tracker.process_tankerkoenig_response(_make_tankerkoenig_response())
        assert len(tracker._price_history) == 1
        assert "diesel_avg" in tracker._price_history[0]


# ── Test manual prices ───────────────────────────────────────────────────


class TestManualPrices:
    def test_set_manual(self, tracker):
        stations = tracker.process_manual_prices(diesel=1.45, e5=1.65, e10=1.59)
        assert len(stations) == 1
        assert stations[0].diesel == 1.45

    def test_manual_station_name(self, tracker):
        stations = tracker.process_manual_prices(diesel=1.45)
        assert "Manuell" in stations[0].name

    def test_manual_open(self, tracker):
        stations = tracker.process_manual_prices(diesel=1.45)
        assert stations[0].is_open is True

    def test_manual_history(self, tracker):
        tracker.process_manual_prices(diesel=1.45, e5=1.65)
        assert len(tracker._price_history) == 1


# ── Test price aggregation ───────────────────────────────────────────────


class TestPrices:
    def test_no_prices_without_data(self, tracker):
        assert tracker.get_prices() is None

    def test_diesel_avg(self, tracker_with_data):
        prices = tracker_with_data.get_prices()
        assert prices is not None
        assert prices.diesel_avg is not None
        # (1.459 + 1.479 + 1.439) / 3 = 1.459
        assert abs(prices.diesel_avg - 1.459) < 0.01

    def test_diesel_min(self, tracker_with_data):
        prices = tracker_with_data.get_prices()
        assert prices.diesel_min == 1.439

    def test_diesel_max(self, tracker_with_data):
        prices = tracker_with_data.get_prices()
        assert prices.diesel_max == 1.479

    def test_e5_avg(self, tracker_with_data):
        prices = tracker_with_data.get_prices()
        assert prices.e5_avg is not None

    def test_e10_avg(self, tracker_with_data):
        prices = tracker_with_data.get_prices()
        assert prices.e10_avg is not None

    def test_station_count(self, tracker_with_data):
        prices = tracker_with_data.get_prices()
        assert prices.station_count == 3

    def test_cheapest_diesel(self, tracker_with_data):
        prices = tracker_with_data.get_prices()
        assert prices.cheapest_diesel is not None
        assert "Total" in prices.cheapest_diesel

    def test_cheapest_e5(self, tracker_with_data):
        prices = tracker_with_data.get_prices()
        assert prices.cheapest_e5 is not None

    def test_radius(self, tracker_with_data):
        prices = tracker_with_data.get_prices()
        assert prices.radius_km == 10.0


# ── Test cost per 100km ──────────────────────────────────────────────────


class TestCostPer100km:
    def test_no_cost_without_data(self, tracker):
        assert tracker.get_cost_per_100km() is None

    def test_electric_cost(self, tracker_with_data):
        cost = tracker_with_data.get_cost_per_100km()
        assert cost is not None
        # 18 kWh * 0.30 EUR = 5.40 EUR
        assert cost.electric_eur == 5.40

    def test_diesel_cost(self, tracker_with_data):
        cost = tracker_with_data.get_cost_per_100km()
        # ~6.0 L * ~1.459 EUR = ~8.75 EUR
        assert cost.diesel_eur > 8.0

    def test_benzin_cost(self, tracker_with_data):
        cost = tracker_with_data.get_cost_per_100km()
        # ~7.5 L * ~1.66 EUR = ~12.45 EUR
        assert cost.benzin_eur > 12.0

    def test_cheapest_is_electric(self, tracker_with_data):
        cost = tracker_with_data.get_cost_per_100km()
        assert cost.cheapest == "electric"

    def test_savings_vs_diesel(self, tracker_with_data):
        cost = tracker_with_data.get_cost_per_100km()
        assert cost.savings_vs_diesel_eur > 0

    def test_savings_vs_benzin(self, tracker_with_data):
        cost = tracker_with_data.get_cost_per_100km()
        assert cost.savings_vs_benzin_eur > 0

    def test_co2_values(self, tracker_with_data):
        cost = tracker_with_data.get_cost_per_100km()
        assert cost.co2_electric_kg < cost.co2_diesel_kg
        assert cost.co2_electric_kg < cost.co2_benzin_kg

    def test_custom_consumption(self, tracker_with_data):
        tracker_with_data.update_consumption(ev_kwh=25.0)  # bigger EV
        cost = tracker_with_data.get_cost_per_100km()
        # 25 * 0.30 = 7.50
        assert cost.electric_eur == 7.50

    def test_diesel_cheapest_with_high_grid(self, tracker):
        """With very high grid price, diesel can be cheaper."""
        tracker._grid_price = 0.80  # 80 ct/kWh
        tracker.process_manual_prices(diesel=1.30, e5=1.50, e10=1.45)
        cost = tracker.get_cost_per_100km()
        # Electric: 18 * 0.80 = 14.40, Diesel: 6 * 1.30 = 7.80
        assert cost.cheapest == "diesel"


# ── Test dashboard data ──────────────────────────────────────────────────


class TestDashboard:
    def test_dashboard_structure(self, tracker_with_data):
        data = tracker_with_data.get_dashboard_data()
        assert "prices" in data.__dict__
        assert "cost_per_100km" in data.__dict__
        assert "stations" in data.__dict__
        assert "price_history" in data.__dict__

    def test_recommendation_de(self, tracker_with_data):
        data = tracker_with_data.get_dashboard_data()
        assert len(data.recommendation_de) > 0
        # Electric should be cheapest with default prices
        assert "Elektro" in data.recommendation_de or "EUR" in data.recommendation_de

    def test_recommendation_en(self, tracker_with_data):
        data = tracker_with_data.get_dashboard_data()
        assert len(data.recommendation_en) > 0

    def test_stations_sorted_by_distance(self, tracker_with_data):
        data = tracker_with_data.get_dashboard_data()
        if len(data.stations) >= 2:
            assert data.stations[0]["dist"] <= data.stations[1]["dist"]

    def test_max_5_stations(self, tracker):
        # Create 10 stations
        stations = []
        for i in range(10):
            stations.append({
                "id": f"s{i}", "name": f"Station {i}", "brand": "X",
                "street": "", "place": "Berlin", "lat": 52.52, "lng": 13.4,
                "dist": float(i), "diesel": 1.5, "e5": 1.7, "e10": 1.6,
                "isOpen": True,
            })
        tracker.process_tankerkoenig_response({"ok": True, "stations": stations})
        data = tracker.get_dashboard_data()
        assert len(data.stations) <= 5


# ── Test configuration ───────────────────────────────────────────────────


class TestConfiguration:
    def test_set_api_key(self, tracker):
        tracker.set_api_key("test-key-123")
        assert tracker.has_api_key is True

    def test_api_url(self, tracker):
        tracker.set_api_key("mykey")
        url = tracker.get_api_url()
        assert "mykey" in url
        assert "52.52" in url
        assert "13.405" in url

    def test_update_location(self, tracker):
        tracker.update_location(48.0, 11.0, 5.0)
        assert tracker._lat == 48.0
        assert tracker._lon == 11.0
        assert tracker._radius == 5.0

    def test_update_grid_price(self, tracker):
        tracker.update_grid_price(0.35)
        assert tracker._grid_price == 0.35

    def test_update_consumption(self, tracker):
        tracker.update_consumption(ev_kwh=20.0, diesel_l=5.0)
        assert tracker._ev_kwh == 20.0
        assert tracker._diesel_l == 5.0

    def test_partial_consumption_update(self, tracker):
        original_benzin = tracker._benzin_l
        tracker.update_consumption(diesel_l=4.5)
        assert tracker._diesel_l == 4.5
        assert tracker._benzin_l == original_benzin


# ── Test recommendations ─────────────────────────────────────────────────


class TestRecommendations:
    def test_electric_cheapest_de(self, tracker_with_data):
        data = tracker_with_data.get_dashboard_data()
        assert "Elektro" in data.recommendation_de

    def test_electric_cheapest_en(self, tracker_with_data):
        data = tracker_with_data.get_dashboard_data()
        assert "Electric" in data.recommendation_en or "cheapest" in data.recommendation_en

    def test_diesel_cheapest_de(self, tracker):
        tracker._grid_price = 0.80
        tracker.process_manual_prices(diesel=1.30, e5=1.50, e10=1.45)
        data = tracker.get_dashboard_data()
        assert "Diesel" in data.recommendation_de

    def test_no_data_recommendation(self, tracker):
        data = tracker.get_dashboard_data()
        assert "Keine" in data.recommendation_de or "verfügbar" in data.recommendation_de


# ── Test price history ───────────────────────────────────────────────────


class TestPriceHistory:
    def test_history_grows(self, tracker):
        for i in range(5):
            tracker.process_manual_prices(diesel=1.40 + i * 0.01)
        assert len(tracker._price_history) == 5

    def test_history_max(self, tracker):
        tracker._max_history = 3
        for i in range(10):
            tracker.process_manual_prices(diesel=1.40 + i * 0.01)
        assert len(tracker._price_history) == 3
