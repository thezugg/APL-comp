"""Pool League v4: public brackets and committee administration."""
import csv
import io
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import Base, engine, get_db
from . import models, security
from .models import Admin, Division, Team, Player, Competition, Entry, EntryPlayer, Match, Audit
from .service import (KINDS, get_comp, comp_dict, add_players_entry, add_team_entry,
                      generate_draw, apply_progression, save_result, audit)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if len(security.JWT_SECRET) < 32:
        raise RuntimeError("Set JWT_SECRET to 32+ random characters in .env")
    Base.metadata.create_all(engine)  # Development bootstrap; introduce Alembic before production upgrades.
    from .db import SessionLocal
    with SessionLocal.begin() as session:
        for number in range(1, 5):
            name = f"Division {number}"
            if not session.scalar(select(Division.id).where(Division.name == name)):
                session.add(Division(name=name))
        email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
        password = os.environ.get("ADMIN_PASSWORD", "")
        if not session.scalar(select(func.count(Admin.id))) and (not email or len(password) < 12):
            raise RuntimeError("Set ADMIN_EMAIL and ADMIN_PASSWORD (12+ characters) for the first committee account")
        if email and password and not session.scalar(select(func.count(Admin.id))):
            session.add(Admin(email=email, password_hash=security.hash_password(password), role="owner"))
    yield


app = FastAPI(title="Pool League API", version="4.0.0-alpha", lifespan=lifespan)


class LoginIn(BaseModel):
    email: str
    password: str


class AdminIn(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=12, max_length=200)


class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    division_id: int


class PlayerIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    division_id: int
    team_id: int | None = None
    member_number: str | None = Field(default=None, max_length=80)


class CompetitionIn(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    kind: str
    division_id: int | None = None
    enforce_same_division: bool = True


class EntryIn(BaseModel):
    player_ids: list[int] | None = None
    team_id: int | None = None


class RuleIn(BaseModel):
    enforce_same_division: bool


class ResultIn(BaseModel):
    score_a: int = Field(ge=0, le=99)
    score_b: int = Field(ge=0, le=99)


def player_dict(db, player):
    team = db.get(Team, player.team_id) if player.team_id else None
    division = db.get(Division, player.division_id)
    return dict(id=player.id, name=player.name, member_number=player.member_number,
                division_id=player.division_id, division=division.name,
                team_id=player.team_id, team=team.name if team else "", active=player.active)


def team_dict(db, team):
    division = db.get(Division, team.division_id)
    return dict(id=team.id, name=team.name, division_id=team.division_id, division=division.name)


def persist(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A record with these details already exists")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(data: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = request.client.host if request.client else "unknown"
    # Stop password hashing work for IPs already in the penalty window.
    recent = [t for t in security.FAILED_LOGINS.get(ip, []) if security.time.monotonic() - t < 900]
    if len(recent) >= 8:
        raise HTTPException(429, "Too many login attempts. Try again later")
    admin = db.scalar(select(Admin).where(Admin.email == data.email.strip().lower(), Admin.active.is_(True)))
    valid = admin is not None and security.verify_password(data.password, admin.password_hash)
    security.check_login_attempt(ip, valid)
    if not valid:
        raise HTTPException(401, "Incorrect email or password")
    token, csrf = security.issue_token(admin.id)
    response.set_cookie("pool_session", token, httponly=True, samesite="strict",
                        secure=security.COOKIE_SECURE, max_age=28800, path="/")
    return {"id": admin.id, "email": admin.email, "role": admin.role, "csrf": csrf}


@app.get("/api/auth/me")
def me(request: Request, db: Session = Depends(get_db)):
    admin, claims = security.current_admin(request, db)
    return {"id": admin.id, "email": admin.email, "role": admin.role, "csrf": claims["csrf"]}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    security.require_admin(request, db, True)
    response.delete_cookie("pool_session", path="/")
    return {"ok": True}


@app.post("/api/admin/users", status_code=201)
def new_admin(data: AdminIn, request: Request, db: Session = Depends(get_db)):
    admin = security.require_admin(request, db, True)
    if admin.role != "owner":
        raise HTTPException(403, "Only the account owner can create committee accounts")
    email = data.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(422, "Enter a valid email address")
    user = Admin(email=email, password_hash=security.hash_password(data.password), role="admin")
    db.add(user)
    audit(db, admin.id, "admin.add", email)
    persist(db)
    return {"id": user.id, "email": user.email}


@app.get("/api/public/competitions")
def public_competitions(db: Session = Depends(get_db)):
    comps = db.scalars(select(Competition).where(Competition.status.in_(["published", "completed"])).order_by(Competition.id.desc())).all()
    return [comp_dict(db, comp) for comp in comps]


@app.get("/api/public/competitions/{comp_id}")
def public_competition(comp_id: int, db: Session = Depends(get_db)):
    return comp_dict(db, get_comp(db, comp_id, True), True)


@app.get("/api/admin/overview")
def overview(request: Request, db: Session = Depends(get_db)):
    security.require_admin(request, db)
    return {"players": db.scalar(select(func.count(Player.id))) or 0,
            "teams": db.scalar(select(func.count(Team.id))) or 0,
            "competitions": db.scalar(select(func.count(Competition.id))) or 0,
            "pending_matches": db.scalar(select(func.count(Match.id)).join(Competition, Match.competition_id == Competition.id)
                .where(Competition.status == "published", Match.winner.is_(None), Match.a.is_not(None), Match.b.is_not(None))) or 0}


@app.get("/api/admin/divisions")
def divisions(request: Request, db: Session = Depends(get_db)):
    security.require_admin(request, db)
    return [{"id": x.id, "name": x.name} for x in db.scalars(select(Division).order_by(Division.id))]


@app.get("/api/admin/teams")
def teams(request: Request, db: Session = Depends(get_db)):
    security.require_admin(request, db)
    return [team_dict(db, t) for t in db.scalars(select(Team).order_by(Team.name))]


@app.post("/api/admin/teams", status_code=201)
def add_team(data: TeamIn, request: Request, db: Session = Depends(get_db)):
    admin = security.require_admin(request, db, True)
    if not db.get(Division, data.division_id):
        raise HTTPException(422, "Unknown division")
    team = Team(name=data.name.strip(), division_id=data.division_id)
    if not team.name:
        raise HTTPException(422, "Team name is required")
    db.add(team)
    audit(db, admin.id, "team.add", team.name)
    persist(db)
    return team_dict(db, team)


@app.get("/api/admin/players")
def players(request: Request, division_id: int | None = None, search: str = "", db: Session = Depends(get_db)):
    security.require_admin(request, db)
    query = select(Player)
    if division_id:
        query = query.where(Player.division_id == division_id)
    if search.strip():
        query = query.where(Player.name.ilike(f"%{search.strip()[:80]}%"))
    people = db.scalars(query.order_by(Player.name).limit(2500)).all()
    return [player_dict(db, p) for p in people]


@app.post("/api/admin/players", status_code=201)
def add_player(data: PlayerIn, request: Request, db: Session = Depends(get_db)):
    admin = security.require_admin(request, db, True)
    if not db.get(Division, data.division_id):
        raise HTTPException(422, "Unknown division")
    if data.team_id:
        team = db.get(Team, data.team_id)
        if not team or team.division_id != data.division_id:
            raise HTTPException(422, "Team must belong to the player's division")
    member_number = data.member_number.strip() if data.member_number else None
    player = Player(name=data.name.strip(), division_id=data.division_id,
                    team_id=data.team_id, member_number=member_number or None)
    if not player.name:
        raise HTTPException(422, "Player name is required")
    db.add(player)
    audit(db, admin.id, "player.add", player.name)
    persist(db)
    return player_dict(db, player)


def parse_division(db, value):
    v = value.strip().lower().replace(" ", "")
    v = v.removeprefix("division").removeprefix("div")
    if v not in ("1", "2", "3", "4"):
        raise HTTPException(422, f"Invalid division '{value}'. Use Division 1 to Division 4")
    div = db.scalar(select(Division).where(Division.name == f"Division {v}"))
    return div


def find_team(db, name, division_id):
    for team in db.scalars(select(Team).where(Team.division_id == division_id)):
        if team.name.casefold() == name.casefold():
            return team
    t = Team(name=name, division_id=division_id)
    db.add(t)
    db.flush()
    return t


@app.post("/api/admin/players/import")
async def import_players(request: Request, db: Session = Depends(get_db)):
    admin = security.require_admin(request, db, True)
    raw = await request.body()
    if len(raw) > 2_000_000:
        raise HTTPException(413, "Maximum CSV file size is 2 MB")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
        headers = {h.strip().casefold(): h for h in reader.fieldnames or [] if h}
        if not {"name", "division"}.issubset(headers):
            raise HTTPException(422, "CSV needs Name and Division columns (Team and Member ID optional)")
        rows = []
        for line, row in enumerate(reader, 2):
            if line > 2002:
                raise HTTPException(422, "Maximum 2,000 players per import")
            if None in row:
                raise HTTPException(422, f"Line {line}: extra columns")
            name = (row.get(headers["name"]) or "").strip()
            div = (row.get(headers["division"]) or "").strip()
            team = (row.get(headers["team"]) or "").strip() if "team" in headers else ""
            member = (row.get(headers["member id"]) or "").strip() if "member id" in headers else ""
            if not (name or div or team or member):
                continue
            if not name or not div or len(name) > 120 or len(team) > 120 or len(member) > 80:
                raise HTTPException(422, f"Line {line}: invalid name/division/team/member ID")
            rows.append((name, parse_division(db, div).id, team, member))
    except UnicodeDecodeError:
        raise HTTPException(422, "Save the file as CSV UTF-8")
    except csv.Error as exc:
        raise HTTPException(422, f"Invalid CSV: {exc}")
    if not rows:
        raise HTTPException(422, "No players found")
    # Entire import succeeds or fails as one transaction, avoiding half-imported rosters.
    existing = db.scalars(select(Player)).all()
    existing_ids = {p.member_number: p for p in existing if p.member_number}
    added = updated = skipped = 0
    seen_member_ids = set()
    for name, div_id, team_name, member_number in rows:
        if member_number:
            if member_number in seen_member_ids:
                raise HTTPException(422, f"Duplicate Member ID in CSV: {member_number}")
            seen_member_ids.add(member_number)
        team_id = find_team(db, team_name, div_id).id if team_name else None
        old = existing_ids.get(member_number) if member_number else None
        if old is not None:
            if (old.name, old.division_id, old.team_id) == (name, div_id, team_id):
                skipped += 1
            else:
                old.name, old.division_id, old.team_id = name, div_id, team_id
                updated += 1
            continue
        if any(p.name.casefold() == name.casefold() and p.division_id == div_id and p.team_id == team_id for p in existing):
            skipped += 1
            continue
        player = Player(name=name, division_id=div_id, team_id=team_id, member_number=member_number or None)
        db.add(player)
        existing.append(player)
        if member_number:
            existing_ids[member_number] = player
        added += 1
    audit(db, admin.id, "players.import", f"Added {added}, updated {updated}, skipped {skipped}")
    persist(db)
    return {"added": added, "updated": updated, "skipped": skipped, "total": len(rows)}


@app.get("/api/admin/competitions")
def admin_competitions(request: Request, db: Session = Depends(get_db)):
    security.require_admin(request, db)
    return [comp_dict(db, c) for c in db.scalars(select(Competition).order_by(Competition.id.desc()))]


@app.post("/api/admin/competitions", status_code=201)
def create_competition(data: CompetitionIn, request: Request, db: Session = Depends(get_db)):
    admin = security.require_admin(request, db, True)
    if data.kind not in KINDS or not data.name.strip():
        raise HTTPException(422, "Choose Singles, Doubles, Threes or Teams and enter a name")
    if data.division_id and not db.get(Division, data.division_id):
        raise HTTPException(422, "Unknown division")
    comp = Competition(name=data.name.strip(), kind=data.kind, division_id=data.division_id,
                       enforce_same_division=data.enforce_same_division)
    db.add(comp)
    db.flush()
    audit(db, admin.id, "competition.add", f"{comp.id}: {comp.name}")
    persist(db)
    return comp_dict(db, comp)


@app.get("/api/admin/competitions/{comp_id}")
def admin_competition(comp_id: int, request: Request, db: Session = Depends(get_db)):
    security.require_admin(request, db)
    return comp_dict(db, get_comp(db, comp_id), True)


@app.patch("/api/admin/competitions/{comp_id}/division-rule")
def change_division_rule(comp_id: int, data: RuleIn, request: Request, db: Session = Depends(get_db)):
    admin = security.require_admin(request, db, True)
    comp = get_comp(db, comp_id)
    if comp.status != "draft":
        raise HTTPException(409, "Division rules are locked after generating the draw")
    if data.enforce_same_division and comp.kind in ("doubles", "threes"):
        rows = db.scalars(select(EntryPlayer).where(EntryPlayer.competition_id == comp.id)).all()
        by_entry = {}
        for p in rows:
            by_entry.setdefault(p.entry_id, []).append(p)
        divisions = {x.id: x.name for x in db.scalars(select(Division))}
        target = divisions.get(comp.division_id)
        for group in by_entry.values():
            if len({x.division_snapshot for x in group}) != 1 or (target and group[0].division_snapshot != target):
                raise HTTPException(409, "Remove cross-division partnerships before enabling this rule")
    comp.enforce_same_division = data.enforce_same_division
    audit(db, admin.id, "competition.rule", f"{comp.id}: {comp.enforce_same_division}")
    persist(db)
    return {"enforce_same_division": comp.enforce_same_division}


@app.post("/api/admin/competitions/{comp_id}/entries", status_code=201)
def add_entry(comp_id: int, data: EntryIn, request: Request, db: Session = Depends(get_db)):
    admin = security.require_admin(request, db, True)
    comp = get_comp(db, comp_id)
    if comp.kind == "teams":
        if data.team_id is None or data.player_ids:
            raise HTTPException(422, "Select exactly one registered team")
        entry = add_team_entry(db, comp, data.team_id)
    else:
        if data.player_ids is None or data.team_id is not None:
            raise HTTPException(422, "Select registered players")
        entry = add_players_entry(db, comp, data.player_ids)
    audit(db, admin.id, "entry.add", f"{comp.id}: {entry.label}")
    persist(db)
    return {"id": entry.id, "label": entry.label}


@app.post("/api/admin/competitions/{comp_id}/add-division")
def add_division(comp_id: int, request: Request, db: Session = Depends(get_db)):
    admin = security.require_admin(request, db, True)
    comp = get_comp(db, comp_id)
    if comp.status != "draft" or comp.kind != "singles" or comp.division_id is None:
        raise HTTPException(409, "Bulk entry is available for draft divisional Singles only")
    ids = db.scalars(select(Player.id).where(Player.division_id == comp.division_id, Player.active.is_(True))).all()
    used = set(db.scalars(select(EntryPlayer.player_id).where(EntryPlayer.competition_id == comp.id)))
    added = 0
    for player_id in ids:
        if player_id not in used:
            add_players_entry(db, comp, [player_id])
            added += 1
    audit(db, admin.id, "entry.bulk", f"{comp.id}: {added} singles players")
    persist(db)
    return {"added": added}


@app.delete("/api/admin/competitions/{comp_id}/entries/{entry_id}")
def delete_entry(comp_id: int, entry_id: int, request: Request, db: Session = Depends(get_db)):
    admin = security.require_admin(request, db, True)
    comp = get_comp(db, comp_id)
    if comp.status != "draft":
        raise HTTPException(409, "Entries are locked after drawing")
    entry = db.get(Entry, entry_id)
    if not entry or entry.competition_id != comp.id:
        raise HTTPException(404, "Entry not found")
    for member in db.scalars(select(EntryPlayer).where(EntryPlayer.entry_id == entry_id)).all():
        db.delete(member)
    db.delete(entry)
    audit(db, admin.id, "entry.remove", f"{comp.id}: {entry.label}")
    persist(db)
    return {"ok": True}


@app.post("/api/admin/competitions/{comp_id}/draw")
def draw(comp_id: int, request: Request, db: Session = Depends(get_db)):
    admin = security.require_admin(request, db, True)
    comp = get_comp(db, comp_id)
    generate_draw(db, comp)
    audit(db, admin.id, "draw.generate", f"{comp.id}: {comp.name}")
    persist(db)
    return comp_dict(db, comp, True)


@app.post("/api/admin/competitions/{comp_id}/publish")
def publish(comp_id: int, request: Request, db: Session = Depends(get_db)):
    admin = security.require_admin(request, db, True)
    comp = get_comp(db, comp_id)
    if comp.status != "drawn":
        raise HTTPException(409, "Generate a draft draw before publishing")
    comp.status = "published"
    audit(db, admin.id, "draw.publish", f"{comp.id}: {comp.name}")
    persist(db)
    return {"ok": True}


@app.post("/api/admin/competitions/{comp_id}/matches/{match_id}/result")
def result(comp_id: int, match_id: int, data: ResultIn, request: Request, db: Session = Depends(get_db)):
    admin = security.require_admin(request, db, True)
    comp = get_comp(db, comp_id)
    winner = save_result(db, comp, match_id, data.score_a, data.score_b)
    audit(db, admin.id, "match.result", f"{comp.id}/{match_id}: {data.score_a}-{data.score_b}, winner entry {winner}")
    persist(db)
    return {"ok": True, "winner": winner, "status": comp.status}


@app.get("/api/admin/audit")
def audit_history(request: Request, db: Session = Depends(get_db)):
    security.require_admin(request, db)
    rows = db.scalars(select(Audit).order_by(Audit.id.desc()).limit(100)).all()
    return [{"id": r.id, "event": r.event, "detail": r.detail,
             "admin_id": r.admin_id, "created_at": r.created_at.isoformat()} for r in rows]


# A release build from frontend/dist can be served on the same origin as the API.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(404, "API route not found")
        return FileResponse(DIST / "index.html")
