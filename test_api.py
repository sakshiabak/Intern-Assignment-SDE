import copy

from tests.conftest import BENGALURU_SQUARE, register_and_login


def make_project(client, auth, name="Open Pit A"):
    r = client.post(
        "/projects", json={"name": name, "industry": "mining"}, headers=auth
    )
    assert r.status_code == 201
    return r.json()["id"]


def make_survey(client, auth, pid, **overrides):
    body = {"name": "Flight 1", "area": BENGALURU_SQUARE, "image_count": 120}
    body.update(overrides)
    return client.post(f"/projects/{pid}/surveys", json=body, headers=auth)


# ---------- auth ----------
def test_register_login_me(client):
    h = register_and_login(client)
    r = client.get("/auth/me", headers=h)
    assert r.status_code == 200
    assert r.json()["email"] == "a@example.com"
    assert "password" not in r.text


def test_duplicate_email_rejected(client):
    register_and_login(client)
    r = client.post(
        "/auth/register", json={"email": "A@example.com", "password": "password123"}
    )
    assert r.status_code == 409


def test_wrong_password_and_bad_token(client):
    register_and_login(client)
    r = client.post("/auth/login", data={"username": "a@example.com", "password": "nope"})
    assert r.status_code == 401
    r = client.get("/projects", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
    assert client.get("/projects").status_code == 401


def test_weak_password_and_bad_email_rejected(client):
    assert (
        client.post("/auth/register", json={"email": "x@y.com", "password": "short"}).status_code
        == 422
    )
    assert (
        client.post("/auth/register", json={"email": "nope", "password": "password123"}).status_code
        == 422
    )


# ---------- projects ----------
def test_project_crud(client, auth):
    pid = make_project(client, auth)
    assert client.get(f"/projects/{pid}", headers=auth).json()["name"] == "Open Pit A"
    r = client.patch(f"/projects/{pid}", json={"name": "Renamed"}, headers=auth)
    assert r.json()["name"] == "Renamed"
    assert len(client.get("/projects", headers=auth).json()) == 1
    assert client.delete(f"/projects/{pid}", headers=auth).status_code == 204
    assert client.get(f"/projects/{pid}", headers=auth).status_code == 404


def test_users_cannot_see_each_others_projects(client, auth):
    pid = make_project(client, auth)
    other = register_and_login(client, "b@example.com")
    assert client.get(f"/projects/{pid}", headers=other).status_code == 404
    assert client.get("/projects", headers=other).json() == []
    assert make_survey(client, other, pid).status_code == 404


def test_invalid_industry_rejected(client, auth):
    r = client.post("/projects", json={"name": "x", "industry": "farming"}, headers=auth)
    assert r.status_code == 422


# ---------- surveys / GIS ----------
def test_create_survey_computes_area(client, auth):
    pid = make_project(client, auth)
    r = make_survey(client, auth, pid)
    assert r.status_code == 201
    # ~0.0090 deg x 0.0090 deg near 13N is roughly 1 km x 0.98 km
    assert 0.9 < r.json()["area_sq_km"] < 1.1


def test_invalid_polygons_rejected(client, auth):
    pid = make_project(client, auth)
    unclosed = copy.deepcopy(BENGALURU_SQUARE)
    unclosed["coordinates"][0].pop()
    assert make_survey(client, auth, pid, area=unclosed).status_code == 422
    out_of_range = copy.deepcopy(BENGALURU_SQUARE)
    out_of_range["coordinates"][0][0] = [200, 12.97]
    assert make_survey(client, auth, pid, area=out_of_range).status_code == 422
    assert make_survey(client, auth, pid, area={"type": "Point", "coordinates": [1, 2]}).status_code == 422


def test_filter_by_status_and_bbox_with_pagination(client, auth):
    pid = make_project(client, auth)
    make_survey(client, auth, pid, name="inside", status="completed")
    far = {
        "type": "Polygon",
        "coordinates": [[[72.8, 19.0], [72.9, 19.0], [72.9, 19.1], [72.8, 19.1], [72.8, 19.0]]],
    }
    make_survey(client, auth, pid, name="mumbai", area=far)

    base = f"/projects/{pid}/surveys"
    assert client.get(base, headers=auth).json()["total"] == 2
    r = client.get(base, params={"bbox": "77.5,12.9,77.7,13.0"}, headers=auth).json()
    assert [s["name"] for s in r["items"]] == ["inside"]
    r = client.get(base, params={"status": "completed"}, headers=auth).json()
    assert r["total"] == 1
    r = client.get(base, params={"limit": 1, "offset": 1}, headers=auth).json()
    assert r["total"] == 2 and len(r["items"]) == 1
    assert client.get(base, params={"bbox": "bad"}, headers=auth).status_code == 422


def test_survey_update_delete_and_geojson(client, auth):
    pid = make_project(client, auth)
    sid = make_survey(client, auth, pid).json()["id"]
    r = client.patch(
        f"/projects/{pid}/surveys/{sid}", json={"status": "processing"}, headers=auth
    )
    assert r.json()["status"] == "processing"
    fc = client.get(f"/projects/{pid}/surveys/geojson", headers=auth).json()
    assert fc["type"] == "FeatureCollection" and len(fc["features"]) == 1
    assert client.delete(f"/projects/{pid}/surveys/{sid}", headers=auth).status_code == 204
    assert client.get(f"/projects/{pid}/surveys/{sid}", headers=auth).status_code == 404


def test_project_stats(client, auth):
    pid = make_project(client, auth)
    make_survey(client, auth, pid, image_count=100)
    make_survey(client, auth, pid, image_count=50, status="completed")
    s = client.get(f"/projects/{pid}/stats", headers=auth).json()
    assert s["survey_count"] == 2
    assert s["total_images"] == 150
    assert s["by_status"] == {"planned": 1, "completed": 1}


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
