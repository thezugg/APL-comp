import io


def create(admin, kind="doubles", division_id=2, enforce=True):
    r = admin.post("/api/admin/competitions", json={"name": "Test KO", "kind": kind,
                "division_id": division_id, "enforce_same_division": enforce})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def player(admin, name, division_id, team_id=None):
    r = admin.post("/api/admin/players", json={"name": name, "division_id": division_id, "team_id": team_id})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def post_entry(admin, comp, ids):
    return admin.post(f"/api/admin/competitions/{comp}/entries", json={"player_ids": ids})


def test_access_control(client, admin):
    assert client.get("/api/public/competitions").status_code == 200
    assert client.get("/api/admin/players").status_code == 200  # already logged in through admin fixture
    assert client.post("/api/admin/competitions", json={"name":"No token", "kind":"singles"}, headers={"X-CSRF-Token": "bad"}).status_code == 403
    comp = create(admin, "singles")
    assert client.get(f"/api/public/competitions/{comp}").status_code == 404


def test_division_toggle_and_duplicate(admin):
    a = player(admin, "Player A", 1)
    b = player(admin, "Player B", 2)
    c = create(admin, "doubles", 2)
    bad = post_entry(admin, c, [a, b])
    assert bad.status_code == 422
    assert admin.patch(f"/api/admin/competitions/{c}/division-rule", json={"enforce_same_division": False}).status_code == 200
    assert post_entry(admin, c, [a, b]).status_code == 201
    assert post_entry(admin, c, [a, b]).status_code == 409
    assert admin.patch(f"/api/admin/competitions/{c}/division-rule", json={"enforce_same_division": True}).status_code == 409


def test_csv_import_and_no_duplicates(admin):
    csv_data = b"Name,Division,Team,Member ID\nNia,Division 1,Vale A,9001\nGwyn,Division 2,Vale B,9002\n"
    r = admin.post("/api/admin/players/import", content=csv_data)
    assert r.status_code == 200, r.text
    assert r.json()["added"] == 2
    assert admin.post("/api/admin/players/import", content=csv_data).json()["skipped"] == 2
    r = admin.post("/api/admin/players/import", content=b"Name,Division,Team,Member ID\nNia,Division 2,Vale B,9001\n")
    assert r.status_code == 200 and r.json()["updated"] == 1
    assert len(admin.get("/api/admin/teams").json()) == 2
    assert len(admin.get("/api/admin/players").json()) == 2
    assert admin.post("/api/admin/players/import", content=b"Name,Division\nMia,Division 5\n").status_code == 422


def test_complete_knockout_and_correction_guard(admin):
    ids = [player(admin, f"Player {i}", 2) for i in range(5)]
    comp = create(admin, "singles")
    for ident in ids:
        assert post_entry(admin, comp, [ident]).status_code == 201
    detail = admin.post(f"/api/admin/competitions/{comp}/draw")
    assert detail.status_code == 200, detail.text
    matches = detail.json()["matches"]
    assert len(matches) == 7 and sum(m["bye"] for m in matches) == 3
    assert admin.get(f"/api/public/competitions/{comp}").status_code == 404
    assert admin.post(f"/api/admin/competitions/{comp}/publish").status_code == 200
    assert admin.get(f"/api/public/competitions/{comp}").status_code == 200
    completed = []
    for _ in range(10):
        matches = admin.get(f"/api/admin/competitions/{comp}").json()["matches"]
        ready = [m for m in matches if not m["bye"] and m["a"] is not None and m["b"] is not None and m["winner"] is None]
        if not ready:
            break
        for match in ready:
            r = admin.post(f"/api/admin/competitions/{comp}/matches/{match['id']}/result", json={"score_a": 5, "score_b": 3})
            assert r.status_code == 200, r.text
            completed.append(match["id"])
    final = admin.get(f"/api/admin/competitions/{comp}").json()
    assert final["status"] == "completed"
    assert len(completed) == 4
    first = next(m for m in final["matches"] if m["id"] == completed[0])
    assert admin.post(f"/api/admin/competitions/{comp}/matches/{first['id']}/result", json={"score_a": 0, "score_b": 5}).status_code == 409
    assert admin.post(f"/api/admin/competitions/{comp}/draw").status_code == 409
    assert admin.get("/api/admin/audit").status_code == 200


def test_threes_and_teams(admin):
    a = player(admin, "A", 1)
    b = player(admin, "B", 1)
    c = player(admin, "C", 1)
    comp = create(admin, "threes", 1)
    assert post_entry(admin, comp, [a, b]).status_code == 422
    assert post_entry(admin, comp, [a, b, c]).status_code == 201
    team = admin.post("/api/admin/teams", json={"name": "Vale A", "division_id": 1}).json()["id"]
    tc = create(admin, "teams", 1)
    assert admin.post(f"/api/admin/competitions/{tc}/entries", json={"team_id": team}).status_code == 201
    assert admin.post(f"/api/admin/competitions/{tc}/entries", json={"team_id": team}).status_code == 409
