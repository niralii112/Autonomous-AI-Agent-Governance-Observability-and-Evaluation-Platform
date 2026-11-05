import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_version import ModelVersion
from app.models.risk_assessment import RiskAssessment
from app.schemas import RiskAssessmentResponse


async def get_by_id(session: AsyncSession, risk_assessment_id: uuid.UUID) -> RiskAssessment | None:
    return await session.get(RiskAssessment, risk_assessment_id)


async def all_for_action(session: AsyncSession, action_id: uuid.UUID) -> list[RiskAssessment]:
    query = select(RiskAssessment).where(RiskAssessment.action_id == action_id).order_by(RiskAssessment.created_at)
    return list((await session.execute(query)).scalars())


async def ensure_model_version(session: AsyncSession, response: RiskAssessmentResponse) -> bool:
    """risk_assessments.model_version is a foreign key. If the model is not registered yet, register a
    minimal INACTIVE row so the assessment can be stored. Returns True when a row was created."""
    stmt = (pg_insert(ModelVersion).values(
        model_version=response.model_version, model_kind=response.risk_source.value, algorithm="unregistered",
        feature_schema_version="unknown", is_active=False).on_conflict_do_nothing(index_elements=["model_version"])
        .returning(ModelVersion.model_version_id))
    return (await session.execute(stmt)).first() is not None


async def add(session: AsyncSession, response: RiskAssessmentResponse) -> RiskAssessment:
    """Store the assessment exactly as Student 2's assess_risk returned it (id and timestamp included)."""
    row = RiskAssessment(
        risk_assessment_id=response.risk_assessment_id, action_id=response.action_id,
        risk_score=response.risk_score, risk_level=response.risk_level.value,
        confidence_score=response.confidence_score, risk_source=response.risk_source.value,
        model_version=response.model_version, features=response.features, reason_codes=response.reason_codes,
        latency_ms=response.latency_ms, created_at=response.created_at)
    session.add(row)
    await session.flush()
    return row
