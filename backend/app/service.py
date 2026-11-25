from collections import defaultdict
from sqlalchemy import select, delete, func
from fastapi import HTTPException
from .models import Competition, Entry, EntryPlayer, Match, Player, Team, Division, Audit
from .engine import draw_slots, round_count

KINDS = ("singles", "doubles", "threes", "teams")


def get_comp(session, comp_id, public=False):
    comp = session.get(Competition, comp_id)
    if not comp or (public and comp.status not in ("published", "completed")):
        raise HTTPException(404, "Competition not found")
    return comp


def audit(session, admin_id, event, detail):
    session.add(Audit(admin_id=admin_id, event=event, detail=detail[:600]))


def comp_dict(session, comp, include_entries=False):
    count = session.scalar(select(func.count(Entry.id)).where(Entry.competition_id == comp.id)) or 0
    div = session.get(Division, comp.division_id) if comp.division_id else None
    data = dict(id=comp.id, name=comp.name, kind=comp.kind, division_id=comp.division_id,
                division=div.name if div else "Open / All Divisions", enforce_same_division=comp.enforce_same_division,
                status=comp.status, entry_count=count, created_at=comp.created_at.isoformat())
    if include_entries:
        entries = session.scalars(select(Entry).where(Entry.competition_id == comp.id).order_by(Entry.label)).all()
        members = session.scalars(select(EntryPlayer).where(EntryPlayer.competition_id == comp.id)).all()
        grouped = defaultdict(list)
        for row in members:
            grouped[row.entry_id].append({"id": row.player_id, "name": row.name_snapshot,
                                          "division": row.division_snapshot, "team": row.team_snapshot})
        data["entries"] = [dict(id=e.id, label=e.label, team_id=e.team_id, players=grouped[e.id]) for e in entries]
        matches = session.scalars(select(Match).where(Match.competition_id == comp.id).order_by(Match.round_num, Match.position)).all()
        data["matches"] = [dict(id=m.id, round_num=m.round_num, position=m.position, a=m.a, b=m.b,
                                bye=m.bye, score_a=m.score_a, score_b=m.score_b, winner=m.winner) for m in matches]
    return data


def validate_players(session, comp, ids):
    expected = {"singles": 1, "doubles": 2, "threes": 3}.get(comp.kind)
    if expected is None:
        raise HTTPException(422, "Choose a registered team for team competitions")
    if len(ids) != expected or len(set(ids)) != len(ids):
        raise HTTPException(422, f"Choose exactly {expected} different players")
    players = [session.get(Player, ident) for ident in ids]
    if any(p is None or not p.active for p in players):
        raise HTTPException(422, "One or more players do not exist or are inactive")
    if comp.kind == "singles" and comp.division_id and players[0].division_id != comp.division_id:
        raise HTTPException(422, "Player is not registered in this competition's division")
    if comp.kind in ("doubles", "threes") and comp.enforce_same_division:
        if len({p.division_id for p in players}) != 1 or (comp.division_id and players[0].division_id != comp.division_id):
            raise HTTPException(422, "All partners must play in the same competition division")
    used = set(session.scalars(select(EntryPlayer.player_id).where(EntryPlayer.competition_id == comp.id)).all())
    if used.intersection(ids):
        raise HTTPException(409, "A selected player is already entered in this competition")
    return players


def add_players_entry(session, comp, ids):
    if comp.status != "draft":
        raise HTTPException(409, "Entries are locked once a draw is generated")
    players = validate_players(session, comp, ids)
    teams = {p.id: session.get(Team, p.team_id) if p.team_id else None for p in players}
    divs = {p.id: session.get(Division, p.division_id) for p in players}
    label = " / ".join(p.name for p in players)
    if session.scalar(select(Entry.id).where(Entry.competition_id == comp.id, Entry.label == label)):
        raise HTTPException(409, "This entry already exists")
    entry = Entry(competition_id=comp.id, label=label)
    session.add(entry)
    session.flush()
    for p in players:
        session.add(EntryPlayer(competition_id=comp.id, entry_id=entry.id,
                                player_id=p.id, name_snapshot=p.name,
                                division_snapshot=divs[p.id].name,
                                team_snapshot=teams[p.id].name if teams[p.id] else ""))
    session.flush()
    return entry


def add_team_entry(session, comp, team_id):
    if comp.kind != "teams":
        raise HTTPException(422, "Team selection only applies to team competitions")
    if comp.status != "draft":
        raise HTTPException(409, "Entries are locked once a draw is generated")
    team = session.get(Team, team_id)
    if not team or (comp.division_id and team.division_id != comp.division_id):
        raise HTTPException(422, "Select a registered team from the chosen division")
    if session.scalar(select(Entry.id).where(Entry.competition_id == comp.id, Entry.team_id == team_id)):
        raise HTTPException(409, "That team is already entered")
    entry = Entry(competition_id=comp.id, label=team.name, team_id=team_id)
    session.add(entry)
    session.flush()
    return entry


def apply_progression(session, comp):
    matches = session.scalars(select(Match).where(Match.competition_id == comp.id).order_by(Match.round_num, Match.position)).all()
    if not matches:
        return
    levels = defaultdict(list)
    for m in matches:
        levels[m.round_num].append(m)
    for r in sorted(levels):
        if r == 1:
            for match in levels[r]:
                if match.bye:
                    match.winner = match.a if match.a is not None else match.b
        else:
            previous = levels[r - 1]
            for match in levels[r]:
                left, right = previous[match.position * 2], previous[match.position * 2 + 1]
                match.a, match.b = left.winner, right.winner
    final = levels[max(levels)][0]
    if comp.status in ("published", "completed"):
        comp.status = "completed" if final.winner is not None else "published"


def generate_draw(session, comp):
    if comp.status not in ("draft", "drawn"):
        raise HTTPException(409, "Published draws cannot be regenerated")
    ids = list(session.scalars(select(Entry.id).where(Entry.competition_id == comp.id)))
    if len(ids) < 2:
        raise HTTPException(422, "At least two entries are required")
    if len(ids) > 512:
        raise HTTPException(422, "Maximum 512 entries per competition")
    slots = draw_slots(ids)
    session.execute(delete(Match).where(Match.competition_id == comp.id))
    session.flush()
    for r in range(1, round_count(len(ids)) + 1):
        for pos in range(len(slots) // (2 ** (r - 1))):
            a, b = slots[pos] if r == 1 else (None, None)
            session.add(Match(competition_id=comp.id, round_num=r, position=pos,
                              a=a, b=b, bye=r == 1 and (a is None or b is None)))
    session.flush()
    apply_progression(session, comp)
    comp.status = "drawn"


def save_result(session, comp, match_id, score_a, score_b):
    if comp.status not in ("published", "completed"):
        raise HTTPException(409, "Publish the draw before recording results")
    if score_a < 0 or score_b < 0 or score_a > 99 or score_b > 99 or score_a == score_b:
        raise HTTPException(422, "Enter valid non-tied frame scores between 0 and 99")
    match = session.get(Match, match_id)
    if not match or match.competition_id != comp.id:
        raise HTTPException(404, "Match not found")
    if match.bye or match.a is None or match.b is None:
        raise HTTPException(409, "Both opponents must be known before scoring")
    winning_entry = match.a if score_a > score_b else match.b
    if match.winner is not None and match.winner != winning_entry:
        downstream = session.scalar(select(Match).where(
            Match.competition_id == comp.id, Match.round_num == match.round_num + 1,
            Match.position == match.position // 2))
        if downstream and downstream.winner is not None:
            raise HTTPException(409, "Cannot change the winner after a later result has been recorded")
    match.score_a, match.score_b, match.winner = score_a, score_b, winning_entry
    session.flush()
    apply_progression(session, comp)
    return winning_entry
