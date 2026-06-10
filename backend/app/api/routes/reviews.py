import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.decision import ManualDecision
from app.models.review import ReviewRecord


router = APIRouter()

REVIEW_PERIODS = {"7d", "14d"}
REVIEW_RESULTS = {"improved", "unchanged", "worse"}


class ReviewIn(BaseModel):
    review_period: str
    before_metrics_json: dict[str, Any] | None = None
    after_metrics_json: dict[str, Any] | None = None
    result: str | None = None
    note: str | None = None


def _dump_json(value: dict[str, Any] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _validate_decision_id(decision_id: int) -> None:
    if decision_id <= 0:
        raise HTTPException(status_code=400, detail="人工处理记录 ID decision_id 必须大于 0")


def review_payload(review: ReviewRecord) -> dict[str, object]:
    return {
        "id": review.id,
        "manual_decision_id": review.manual_decision_id,
        "review_period": review.review_period,
        "before_metrics_json": review.before_metrics_json,
        "after_metrics_json": review.after_metrics_json,
        "result": review.result,
        "note": review.note,
        "reviewed_at": review.reviewed_at.isoformat(),
    }


@router.post("/{decision_id}")
def create_review(
    decision_id: int,
    payload: ReviewIn,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _validate_decision_id(decision_id)
    if payload.review_period not in REVIEW_PERIODS:
        raise HTTPException(status_code=400, detail="复盘周期 review_period 只能是 7d 或 14d")
    if payload.result not in REVIEW_RESULTS:
        raise HTTPException(status_code=400, detail="复盘结果 review_result 不在第一版支持范围内")

    decision = db.get(ManualDecision, decision_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="人工处理记录不存在")

    review = db.execute(
        select(ReviewRecord).where(
            ReviewRecord.manual_decision_id == decision_id,
            ReviewRecord.review_period == payload.review_period,
        )
    ).scalar_one_or_none()
    now = datetime.now()
    if review is None:
        review = ReviewRecord(
            manual_decision_id=decision_id,
            review_period=payload.review_period,
            before_metrics_json=_dump_json(payload.before_metrics_json),
            after_metrics_json=_dump_json(payload.after_metrics_json),
            result=payload.result,
            note=payload.note,
            reviewed_at=now,
        )
        db.add(review)
    else:
        review.before_metrics_json = _dump_json(payload.before_metrics_json)
        review.after_metrics_json = _dump_json(payload.after_metrics_json)
        review.result = payload.result
        review.note = payload.note
        review.reviewed_at = now
    db.commit()
    db.refresh(review)
    return review_payload(review)


@router.get("")
def list_reviews(
    decision_id: int | None = None,
    decision_ids: str | None = None,
    review_period: str | None = None,
    result: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    filters = []
    if decision_id is not None:
        _validate_decision_id(decision_id)
        filters.append(ReviewRecord.manual_decision_id == decision_id)
    if decision_ids:
        try:
            parsed_decision_ids = [int(item) for item in decision_ids.split(",") if item.strip()]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="人工处理记录 ID 列表 decision_ids 格式不正确") from exc
        if any(item <= 0 for item in parsed_decision_ids):
            raise HTTPException(status_code=400, detail="人工处理记录 ID 列表 decision_ids 必须全部大于 0")
        if parsed_decision_ids:
            filters.append(ReviewRecord.manual_decision_id.in_(parsed_decision_ids))
    if review_period:
        if review_period not in REVIEW_PERIODS:
            raise HTTPException(status_code=400, detail="复盘周期 review_period 只能是 7d 或 14d")
        filters.append(ReviewRecord.review_period == review_period)
    if result:
        if result not in REVIEW_RESULTS:
            raise HTTPException(status_code=400, detail="复盘结果 review_result 不在第一版支持范围内")
        filters.append(ReviewRecord.result == result)

    stmt = select(ReviewRecord).where(*filters).order_by(ReviewRecord.reviewed_at.desc(), ReviewRecord.id.desc())
    return [review_payload(review) for review in db.execute(stmt).scalars().all()]
