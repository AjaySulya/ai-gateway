import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.db.models import Model, Provider


async def get_candidates(
    db: AsyncSession, project_id: uuid.UUID, requested_model_name: str
) -> list[tuple[Model, Provider]]:
    """Static priority-fallback strategy: every active Model matching the
    requested name, under an active Provider on this project, ordered by
    priority (lower = more preferred). Two Provider rows can register the
    same model_name (e.g. the same model via two accounts, or two regions)
    to form a fallback chain - that's what Model.priority is for.

    This is the seam TypeSafe Jev plugs into later as a smarter orderer of
    this same candidate list, per the project's routing architecture
    (Request -> Candidate Filtering -> Jev Decision -> Policy/Health/Budget
    Validation -> Final Model Selection -> LiteLLM): this function is
    "Candidate Filtering", router.py's circuit-breaker check is today's
    stand-in for "Validation", and Jev would sit between the two.
    """
    result = await db.execute(
        select(Model, Provider)
        .join(Provider, Model.provider_id == Provider.id)
        .where(
            Provider.project_id == project_id,
            Provider.is_active.is_(True),
            Model.model_name == requested_model_name,
            Model.is_active.is_(True),
        )
        .order_by(Model.priority.asc())
    )
    return [(row[0], row[1]) for row in result.all()]
