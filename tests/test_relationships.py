"""모델 relationship 탐색 테스트 (Season ↔ Team ↔ User)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.season import Season
from app.models.team import Team
from app.models.user import User


async def _seed_chain():
    """creator admin → season → team → member 를 만들고 id 들을 돌려준다."""
    suffix = uuid.uuid4().hex[:8]
    async with AsyncSessionLocal() as db:
        creator = User(
            username=f"creator_{suffix}", password="x", nickname="c", role="admin"
        )
        db.add(creator)
        await db.flush()

        season = Season(name=f"시즌_{suffix}", created_by=creator.id)
        db.add(season)
        await db.flush()

        team = Team(season_id=season.id, name="레드팀")
        db.add(team)
        await db.flush()

        member = User(
            username=f"member_{suffix}",
            password="x",
            nickname="m",
            role="user",
            team_id=team.id,
        )
        db.add(member)
        await db.commit()
        return season.id, team.id, member.id


async def test_forward_navigation():
    """Season → teams → members (one-to-many)."""
    season_id, team_id, member_id = await _seed_chain()

    async with AsyncSessionLocal() as db:
        season = (
            await db.execute(
                select(Season)
                .where(Season.id == season_id)
                .options(selectinload(Season.teams).selectinload(Team.members))
            )
        ).scalar_one()

        assert [t.id for t in season.teams] == [team_id]
        assert member_id in [m.id for m in season.teams[0].members]


async def test_reverse_navigation():
    """User → team → season (many-to-one 체이닝)."""
    season_id, team_id, member_id = await _seed_chain()

    async with AsyncSessionLocal() as db:
        member = (
            await db.execute(
                select(User)
                .where(User.id == member_id)
                .options(selectinload(User.team).selectinload(Team.season))
            )
        ).scalar_one()

        assert member.team is not None
        assert member.team.id == team_id
        assert member.team.season.id == season_id
