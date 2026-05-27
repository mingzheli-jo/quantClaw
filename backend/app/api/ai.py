from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.config import settings
from app.models.ai import AIAnalysis
from app.models.signal import Signal
from app.models.system import User
from app.services.ai.analyzer import analyze_stock

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/daily")
def daily_analyses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = date.today()
    analyses = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.trade_date == today)
        .all()
    )
    result = []
    for a in analyses:
        signal = db.query(Signal).filter(
            Signal.code == a.code, Signal.trade_date == today
        ).first()
        result.append({
            "code": a.code,
            "stock_name": signal.stock_name if signal else a.code,
            "score": signal.score if signal else 0,
            "summary": a.summary,
            "risk": a.risk,
            "suggestion": a.suggestion,
            "market_comment": a.market_comment,
            "llm_provider": a.llm_provider,
            "created_at": str(a.created_at),
        })
    return result


@router.get("/{code}")
def get_analysis(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    analysis = (
        db.query(AIAnalysis)
        .filter(AIAnalysis.code == code)
        .order_by(AIAnalysis.trade_date.desc())
        .first()
    )
    if not analysis:
        return {"code": code, "summary": None}
    return {
        "code": analysis.code,
        "trade_date": str(analysis.trade_date),
        "summary": analysis.summary,
        "risk": analysis.risk,
        "suggestion": analysis.suggestion,
        "market_comment": analysis.market_comment,
        "llm_provider": analysis.llm_provider,
        "created_at": str(analysis.created_at),
    }


@router.post("/generate/{code}")
def generate_analysis(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not settings.deepseek_api_key and not settings.qwen_api_key:
        raise HTTPException(status_code=503, detail="未配置 AI 服务，请在环境变量中设置 DEEPSEEK_API_KEY")

    today = date.today()
    existing = db.query(AIAnalysis).filter(
        AIAnalysis.code == code, AIAnalysis.trade_date == today
    ).first()
    if existing:
        return {
            "code": existing.code,
            "trade_date": str(existing.trade_date),
            "summary": existing.summary,
            "risk": existing.risk,
            "suggestion": existing.suggestion,
            "market_comment": existing.market_comment,
        }

    today_count = db.query(AIAnalysis).filter(AIAnalysis.trade_date == today).count()
    if today_count >= 20:
        raise HTTPException(status_code=429, detail="今日 AI 分析次数已达上限 (20次)")

    result = analyze_stock(db, code)
    analysis = AIAnalysis(
        code=code,
        trade_date=today,
        summary=result["summary"],
        risk=result["risk"],
        suggestion=result["suggestion"],
        market_comment=result["market_comment"],
        llm_provider=settings.llm_provider,
    )
    db.add(analysis)
    db.commit()
    return {
        "code": code,
        "trade_date": str(today),
        "summary": result["summary"],
        "risk": result["risk"],
        "suggestion": result["suggestion"],
        "market_comment": result["market_comment"],
    }
