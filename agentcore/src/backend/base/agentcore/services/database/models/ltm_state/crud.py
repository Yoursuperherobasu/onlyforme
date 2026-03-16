from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from agentcore.services.database.models.ltm_state.model import LTMStateTable


async def get_ltm_state_by_agent(session: AsyncSession, agent_id: UUID) -> LTMStateTable | None:
    stmt = select(LTMStateTable).where(LTMStateTable.agent_id == agent_id)
    result = await session.exec(stmt)
    return result.first()


async def upsert_ltm_state(
    session: AsyncSession,
    agent_id: UUID,
    **kwargs,
) -> LTMStateTable:
    state = await get_ltm_state_by_agent(session, agent_id)
    if state:
        for key, value in kwargs.items():
            if value is not None:
                setattr(state, key, value)
        session.add(state)
        await session.commit()
        await session.refresh(state)
        return state

    state = LTMStateTable(agent_id=agent_id, **kwargs)
    session.add(state)
    await session.commit()
    await session.refresh(state)
    return state


async def increment_message_count(session: AsyncSession, agent_id: UUID) -> int:
    state = await get_ltm_state_by_agent(session, agent_id)
    if not state:
        state = LTMStateTable(agent_id=agent_id, message_count_since_last=1)
        session.add(state)
        await session.commit()
        await session.refresh(state)
        return 1

    state.message_count_since_last = (state.message_count_since_last or 0) + 1
    session.add(state)
    await session.commit()
    await session.refresh(state)
    return state.message_count_since_last
