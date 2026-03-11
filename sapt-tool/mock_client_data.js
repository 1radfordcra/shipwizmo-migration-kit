// Mock data for demonstration - inject into window
window._MOCK_CLIENT_DATA = {
  "id": 1,
  "email": "sarah@acmecommerce.com",
  "company_name": "Acme Commerce",
  "status": "invited",
  "shipping_data": {"data": [{"weight": 5}]},
  "data_confirmed": 1,
  "analysis": {
    "id": 7,
    "status": "published",
    "created_at": "2026-03-05",
    "published_at": "2026-03-05",
    "results": {
      "summary": {
        "shipment_count": 50,
        "total_original": 1150.0,
        "total_br": 960.0,
        "total_savings": 190.0,
        "savings_pct": "17%",
        "avg_original": 23.0,
        "avg_br": 19.2,
        "shipments_with_savings": 45
      },
      "currency": "USD",
      "by_service": {
        "USPS Priority Mail": {"count": 20, "original": 450.0, "br": 380.0, "savings": 70.0},
        "UPS Ground": {"count": 15, "original": 320.0, "br": 270.0, "savings": 50.0},
        "FedEx Ground": {"count": 15, "original": 380.0, "br": 310.0, "savings": 70.0}
      },
      "by_carrier": {
        "USPS": {"shipments": 20, "original": 450.0, "br": 380.0, "savings": 70.0},
        "UPS": {"shipments": 15, "original": 320.0, "br": 270.0, "savings": 50.0},
        "FedEx": {"shipments": 15, "original": 380.0, "br": 310.0, "savings": 70.0}
      },
      "by_zone": {
        "2": {"count": 10, "distribution": 20, "avg_original": 18.0, "avg_br": 15.0, "savings": 30.0, "savings_pct": "17%"},
        "4": {"count": 20, "distribution": 40, "avg_original": 23.0, "avg_br": 19.0, "savings": 80.0, "savings_pct": "17%"},
        "6": {"count": 15, "distribution": 30, "avg_original": 28.0, "avg_br": 23.0, "savings": 75.0, "savings_pct": "18%"},
        "8": {"count": 5, "distribution": 10, "avg_original": 35.0, "avg_br": 30.0, "savings": 25.0, "savings_pct": "14%"}
      },
      "shipments": [
        {"ship_date": "2026-02-01", "carrier": "USPS", "service": "Priority Mail", "weight": 5, "billable_weight": 5, "zone": 4, "origin_state": "CA", "dest_state": "NY", "price": 22.50, "br_service": "USPS Priority", "br_price": 19.00, "savings": 3.50},
        {"ship_date": "2026-02-02", "carrier": "UPS", "service": "Ground", "weight": 3, "billable_weight": 3, "zone": 2, "origin_state": "CA", "dest_state": "NV", "price": 15.00, "br_service": "UPS Ground", "br_price": 12.50, "savings": 2.50},
        {"ship_date": "2026-02-03", "carrier": "FedEx", "service": "Ground", "weight": 7, "billable_weight": 7, "zone": 6, "origin_state": "CA", "dest_state": "FL", "price": 30.00, "br_service": "FedEx Ground", "br_price": 25.00, "savings": 5.00}
      ]
    }
  }
};
