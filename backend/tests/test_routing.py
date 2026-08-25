from app.services.routing import detect_mode


def test_routes_plain_question_to_qa():
    assert detect_mode("How do strong teams improve activation?") == "qa"


def test_routes_ship30_request():
    assert detect_mode("Turn this into a Ship 30 for 30 essay") == "ship30"


def test_routes_html_request_to_artifact():
    assert detect_mode("Create an HTML dashboard from this") == "artifact"
