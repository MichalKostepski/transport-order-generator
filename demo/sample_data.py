"""Fictional values used exclusively for the public portfolio demo."""

from __future__ import annotations


def example_orders():
    base = {
        "order_year": 2026,
        "order_month": 10,
        "carrier_details": "",
        "internal_notes": "Fictional portfolio example. No real customer data.",
        "driver_id_card": "DEMO-ID-01",
        "driver_pesel": "",
        "driver_phone": "000 000 000",
        "payment": "30 days / bank transfer",
        "pdf_path": "",
    }
    samples = [
        {
            "order_ordinal": 1,
            "order_number": "1/10/UT/2026",
            "order_date": "2026-10-12",
            "carrier_name": "Northline Demo Transport",
            "load_place_name": "Example Logistics Hub",
            "load_address": "12 Sample Street, Example City",
            "load_date": "12.10.2026",
            "unload_place_name": "Sample Distribution Center",
            "unload_address": "8 Fictional Road, Test Town",
            "unload_date": "13.10.2026",
            "service_value": "1 450 PLN net",
            "cargo_type": "Granular fertilizer (demo)",
            "cargo_tons": 24,
            "driver_full_name": "Jan Testowy",
            "truck_registration": "DEMO101",
            "trailer_registration": "DEMO202",
        },
        {
            "order_ordinal": 2,
            "order_number": "2/10/UT/2026",
            "order_date": "2026-10-15",
            "carrier_name": "Example Freight Services",
            "load_place_name": "Demo Fertilizer Terminal",
            "load_address": "15 Prototype Avenue, Demo City",
            "load_date": "15.10.2026",
            "unload_place_name": "Example Agricultural Warehouse",
            "unload_address": "20 Test Route, Sample Village",
            "unload_date": "16.10.2026",
            "service_value": "1 820 PLN net",
            "cargo_type": "Mineral fertilizer (demo)",
            "cargo_tons": 22,
            "driver_full_name": "Anna Przykładowa",
            "driver_id_card": "DEMO-ID-02",
            "truck_registration": "DEMO303",
            "trailer_registration": "DEMO404",
        },
    ]
    return [{**base, **sample} for sample in samples]


EXAMPLE_MESSAGE = """Kierowca: Jan Testowy
Dowód: DEMO-ID-01
Auto: DEMO101
Naczepa: DEMO202
Tel: 000 000 000"""
