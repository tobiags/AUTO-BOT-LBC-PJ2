from app.main import app


def test_phone_operations_router_exposes_dashboard_and_actions() -> None:
    routes = {
        (route.path, method)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }

    assert ("/api/v1/phone-operations/summary", "GET") in routes
    assert ("/api/v1/phone-operations/activations", "GET") in routes
    assert ("/api/v1/phone-operations/activations", "POST") in routes
    assert ("/api/v1/phone-operations/activations/{activation_id}/refresh", "POST") in routes
    assert ("/api/v1/phone-operations/activations/{activation_id}/cancel", "POST") in routes
    assert ("/api/v1/phone-operations/messages", "GET") in routes
    assert ("/api/v1/phone-operations/messages.csv", "GET") in routes
