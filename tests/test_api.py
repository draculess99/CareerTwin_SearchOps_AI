from backend.app import analyze_job, build_search_url, parse_query_file


def test_queries_parse():
    items = parse_query_file()
    assert len(items) >= 20
    assert {x["track"] for x in items} == {"supply_chain", "applied_ai", "healthcare_ai"}


def test_url_builder():
    url = build_search_url("linkedin", '"Machine Learning Engineer" AND Python', "Boston, MA")
    assert "linkedin.com/jobs/search" in url
    assert "Machine+Learning+Engineer" in url


def test_classifier():
    result = analyze_job("Healthcare data scientist for patient flow, hospital staffing, Python, SQL and machine learning")
    assert result["recommended_track"] == "healthcare_ai"
    assert 0 <= result["fit_score"] <= 100
