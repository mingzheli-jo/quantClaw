from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.strategy import StrategyTemplate
from app.models.system import User
from app.schemas.strategy import StrategyCreate, StrategyUpdate, StrategyOut

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategyOut])
def list_strategies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(StrategyTemplate).order_by(StrategyTemplate.is_active.desc(), StrategyTemplate.id).all()


@router.post("", response_model=StrategyOut, status_code=201)
def create_strategy(body: StrategyCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = StrategyTemplate(
        name=body.name, description=body.description,
        filter_config=body.filter_config.model_dump(),
        score_config=body.score_config.model_dump(),
        signal_config=body.signal_config.model_dump(),
        risk_config=body.risk_config.model_dump(),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.get("/{strategy_id}", response_model=StrategyOut)
def get_strategy(strategy_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(StrategyTemplate).filter(StrategyTemplate.id == strategy_id).first()
    if not t:
        raise HTTPException(404, "Strategy not found")
    return t


@router.put("/{strategy_id}", response_model=StrategyOut)
def update_strategy(strategy_id: int, body: StrategyUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(StrategyTemplate).filter(StrategyTemplate.id == strategy_id).first()
    if not t:
        raise HTTPException(404, "Strategy not found")
    if body.name is not None:
        t.name = body.name
    if body.description is not None:
        t.description = body.description
    if body.filter_config is not None:
        t.filter_config = body.filter_config.model_dump()
    if body.score_config is not None:
        t.score_config = body.score_config.model_dump()
    if body.signal_config is not None:
        t.signal_config = body.signal_config.model_dump()
    if body.risk_config is not None:
        t.risk_config = body.risk_config.model_dump()
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(StrategyTemplate).filter(StrategyTemplate.id == strategy_id).first()
    if not t:
        raise HTTPException(404, "Strategy not found")
    if t.is_builtin:
        raise HTTPException(400, "Cannot delete builtin strategy")
    db.delete(t)
    db.commit()
    return {"ok": True}


@router.put("/{strategy_id}/activate", response_model=StrategyOut)
def activate_strategy(strategy_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(StrategyTemplate).filter(StrategyTemplate.id == strategy_id).first()
    if not t:
        raise HTTPException(404, "Strategy not found")
    db.query(StrategyTemplate).update({"is_active": False})
    t.is_active = True
    db.commit()
    db.refresh(t)
    return t
