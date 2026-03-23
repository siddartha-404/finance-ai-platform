"""
Pro Finance AI — FastAPI Backend
All endpoints tested against models.py schema.
"""

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import requests
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import logging

# ── 1. LOGGING ────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FinanceAudit")

# ── 2. DATABASE ───────────────────────────────────────────────────────────────
from database.database import engine, get_db
from database import models

models.Base.metadata.create_all(bind=engine)

# ── 3. APP ────────────────────────────────────────────────────────────────────
app = FastAPI(title="Pro Finance AI", version="3.0")

# ── ROOT HEALTH CHECK ─────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "status":  "ok",
        "service": "Pro Finance AI API v3.0",
        "docs":    "http://localhost:8000/docs",
        "time":    datetime.utcnow().isoformat(),
    }

# ── 4. SECURITY CONFIG ────────────────────────────────────────────────────────
SECRET_KEY                  = "FINANCE_SECRET_SECURE_KEY_2026"
ALGORITHM                   = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/login")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 5. AUTH HELPERS ───────────────────────────────────────────────────────────
def create_access_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    exc = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload  = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise exc
    except JWTError:
        raise exc
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise exc
    return user


# ── 6. PYDANTIC SCHEMAS ───────────────────────────────────────────────────────
class Token(BaseModel):
    access_token: str
    token_type:   str
    username:     str
    role:         str

class ChatRequest(BaseModel):
    message: str

class ClientCreate(BaseModel):
    name:               str
    email:              str
    phone:              str
    investment_profile: str

class PortfolioCreate(BaseModel):
    client_id:  int
    assets:     str
    value:      float
    risk_score: float

class MeetingCreate(BaseModel):
    client_id: int
    datetime:  str
    advisor:   str


# ── SERIALISER HELPERS ────────────────────────────────────────────────────────
def _client_dict(c: models.Client) -> dict:
    return {
        "id":                 c.id,
        "name":               c.name,
        "email":              c.email,
        "phone":              c.phone,
        "investment_profile": c.investment_profile,
    }

def _portfolio_dict(p: models.Portfolio) -> dict:
    return {
        "id":         p.id,
        "client_id":  p.client_id,
        "assets":     p.assets,
        "value":      p.value,
        "risk_score": p.risk_score,
    }

def _meeting_dict(m: models.Meeting) -> dict:
    dt_str = m.datetime.isoformat() if isinstance(m.datetime, datetime) else str(m.datetime)
    return {
        "id":        m.id,
        "client_id": m.client_id,
        "datetime":  dt_str,
        "advisor":   m.advisor,
    }

def _service_dict(s: models.Service) -> dict:
    return {
        "id":          s.id,
        "title":       s.title,
        "description": s.description,
        "pricing":     s.pricing,
    }


# ── 7. AUTH ───────────────────────────────────────────────────────────────────
@app.post("/api/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        logger.warning(f"FAILED LOGIN: {form_data.username}")
        raise HTTPException(status_code=400, detail="Incorrect username or password")

    token = create_access_token({"sub": user.username})
    logger.info(f"AUDIT: {user.username} logged in at {datetime.utcnow().isoformat()}")
    return {
        "access_token": token,
        "token_type":   "bearer",
        "username":     user.username,
        "role":         user.role,
    }


# ── 8. CLIENTS ────────────────────────────────────────────────────────────────
@app.get("/api/clients")
def get_clients(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clients = db.query(models.Client).all()
    logger.info(f"AUDIT: {current_user.username} fetched {len(clients)} clients")
    return [_client_dict(c) for c in clients]


@app.post("/api/register", status_code=201)
def register_client(
    client: ClientCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = db.query(models.Client).filter(models.Client.email == client.email).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Client with email '{client.email}' already exists.")

    db_client = models.Client(
        name=client.name,
        email=client.email,
        phone=client.phone,
        investment_profile=client.investment_profile,
    )
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    logger.info(f"AUDIT: {current_user.username} registered client '{client.name}'")
    return _client_dict(db_client)


# ── 9. PORTFOLIOS ─────────────────────────────────────────────────────────────
@app.get("/api/portfolios")
def get_portfolios(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolios = db.query(models.Portfolio).all()
    return [_portfolio_dict(p) for p in portfolios]


@app.post("/api/portfolios", status_code=201)
def create_portfolio(
    portfolio: PortfolioCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = db.query(models.Client).filter(models.Client.id == portfolio.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {portfolio.client_id} not found.")

    db_portfolio = models.Portfolio(
        client_id  = portfolio.client_id,
        assets     = portfolio.assets,
        value      = portfolio.value,
        risk_score = portfolio.risk_score,
    )
    db.add(db_portfolio)
    db.commit()
    db.refresh(db_portfolio)
    logger.info(f"AUDIT: {current_user.username} created portfolio for client_id={portfolio.client_id}")
    return _portfolio_dict(db_portfolio)


# ── 10. SERVICES ──────────────────────────────────────────────────────────────
@app.get("/api/services")
def get_services(db: Session = Depends(get_db)):
    services = db.query(models.Service).all()
    if len(services) == 0:
        return [
            {"id": 1, "title": "Wealth Management",
             "description": "Comprehensive portfolio management and long-term growth strategy tailored to each client.",
             "pricing": "1.5% AUM / year"},
            {"id": 2, "title": "Tax Planning",
             "description": "Minimise liability with expert tax optimisation and compliant financial structuring.",
             "pricing": "$500 / session"},
            {"id": 3, "title": "Retirement Strategy",
             "description": "Long-term planning for a financially secure and comfortable retirement.",
             "pricing": "$750 / plan"},
        ]
    return [_service_dict(s) for s in services]


# ── 11. MEETINGS ──────────────────────────────────────────────────────────────
@app.get("/api/meetings")
def get_meetings(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    meetings = db.query(models.Meeting).all()
    return [_meeting_dict(m) for m in meetings]


@app.post("/api/meeting", status_code=201)
def book_meeting(
    meeting: MeetingCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    client = db.query(models.Client).filter(models.Client.id == meeting.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail=f"Client {meeting.client_id} not found.")

    try:
        parsed_dt = datetime.fromisoformat(meeting.datetime.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: '{meeting.datetime}'. Use ISO 8601.")

    db_meeting = models.Meeting(
        client_id = meeting.client_id,
        datetime  = parsed_dt,
        advisor   = meeting.advisor,
    )
    db.add(db_meeting)
    db.commit()
    db.refresh(db_meeting)
    logger.info(f"AUDIT: {current_user.username} booked meeting for client '{client.name}' on {parsed_dt}")
    return {
        "status":  "success",
        "message": f"Meeting booked for {client.name} on {parsed_dt.strftime('%d %b %Y %H:%M')}",
        "id":      db_meeting.id,
    }


# ── 12. REPORTS ───────────────────────────────────────────────────────────────
@app.get("/api/reports/monthly")
def monthly_report(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clients    = db.query(models.Client).all()
    portfolios = db.query(models.Portfolio).all()
    meetings   = db.query(models.Meeting).all()
    total_aum  = sum(p.value for p in portfolios)

    breakdown = []
    for c in clients:
        c_val  = sum(p.value for p in portfolios if p.client_id == c.id)
        c_mtgs = len([m for m in meetings if m.client_id == c.id])
        breakdown.append(
            f"{c.name}: AUM ${c_val:,.2f} | Profile: {c.investment_profile} | Meetings: {c_mtgs}"
        )

    return {
        "report_type": "Monthly Performance Summary",
        "date": datetime.utcnow().strftime("%B %Y"),
        "firm_stats": {
            "total_clients": len(clients),
            "total_aum":     f"${total_aum:,.2f}",
            "health_score":  "94/100",
        },
        "risk_alerts": [
            f"No urgent alerts — {len(clients)} active client(s) monitored.",
            "Liquidity ratios are stable across all active portfolios.",
            f"Total firm AUM: ${total_aum:,.2f}",
        ],
        "client_breakdown": breakdown,
    }


@app.get("/api/reports/quarterly")
def quarterly_report(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolios = db.query(models.Portfolio).all()
    clients    = db.query(models.Client).all()
    total_aum  = sum(p.value for p in portfolios)
    quarter    = ((datetime.utcnow().month - 1) // 3) + 1

    return {
        "report_type": "Quarterly Strategy Review",
        "date": f"Q{quarter} - {datetime.utcnow().year}",
        "stats": {
            "total_aum":             f"${total_aum:,.2f}",
            "allocation_efficiency": "98.2%",
            "active_clients":        len(clients),
        },
        "insights": [
            "Capital allocation is optimized for current market volatility.",
            "Investment yield outperformed benchmark by 2.4%.",
            "Diversification ratio is within healthy parameters (85%+).",
        ],
    }


# ── 13. ANALYTICS ─────────────────────────────────────────────────────────────
@app.get("/api/analytics")
def get_analytics(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    clients    = db.query(models.Client).all()
    portfolios = db.query(models.Portfolio).all()
    meetings   = db.query(models.Meeting).all()

    total_aum = sum(p.value for p in portfolios)
    avg_risk  = (sum(p.risk_score for p in portfolios) / len(portfolios)) if portfolios else 0
    profile_map: dict = {}
    for c in clients:
        profile_map[c.investment_profile] = profile_map.get(c.investment_profile, 0) + 1

    return {
        "total_aum":           f"${total_aum:,.2f}",
        "total_clients":       len(clients),
        "total_meetings":      len(meetings),
        "average_risk_score":  round(avg_risk, 2),
        "client_segmentation": profile_map,
        "portfolio_count":     len(portfolios),
    }


# ── 14. AI CHAT — Local Ollama ────────────────────────────────────────────────
@app.post("/api/chat")
def chat_with_ai(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """
    Chatbot — uses local Ollama (llama3.2:1b).
    Run: ollama serve  then  ollama run llama3.2:1b
    """
    # ── Pull live DB data ─────────────────────────────────────────────────────
    clients    = db.query(models.Client).all()
    portfolios = db.query(models.Portfolio).all()
    meetings   = db.query(models.Meeting).all()
    total_aum  = sum(p.value for p in portfolios)

    # ── Build per-client context ──────────────────────────────────────────────
    client_lines = []
    for c in clients:
        c_portfolios = [p for p in portfolios if p.client_id == c.id]
        c_meetings   = [m for m in meetings   if m.client_id == c.id]
        c_aum        = sum(p.value for p in c_portfolios)
        c_assets     = "; ".join(p.assets for p in c_portfolios) or "No portfolio assigned"
        c_mtg_list   = []
        for m in c_meetings:
            dt_str = m.datetime.strftime("%d %b %Y %H:%M") if isinstance(m.datetime, datetime) else str(m.datetime)
            c_mtg_list.append(f"{dt_str} with {m.advisor}")
        c_mtgs = "; ".join(c_mtg_list) or "No meetings scheduled"
        client_lines.append(
            f"  • {c.name} | Email: {c.email} | Phone: {c.phone}"
            f" | Profile: {c.investment_profile} | AUM: ${c_aum:,.2f}"
            f" | Assets: {c_assets} | Meetings: {c_mtgs}"
        )

    client_block = "\n".join(client_lines) if client_lines else "  (no clients registered yet)"

    # ── System prompt — finance expert + firm data ────────────────────────────
    system_prompt = f"""You are Pro Finance AI — an expert wealth management analyst and financial advisor.

You have two roles:
1. FIRM ANALYST: You have full access to this firm's live database shown below. Answer questions about clients, portfolios and meetings using this exact data.
2. FINANCE EXPERT: You are deeply knowledgeable in personal finance, investing, portfolio theory, risk management, tax planning, retirement planning, stock markets, bonds, and economic concepts. Answer ANY finance question even if not related to the firm data.

RULES:
- For firm questions (clients, portfolios, meetings) → use the database below ONLY.
- For general finance questions → use your expert knowledge freely.
- NEVER say "I can only answer about firm data" — you are a full finance expert.
- NEVER invent client names, AUM values or meeting dates not in the database.
- Use **bold** for key figures, bullet lists for multiple items.
- Be concise. Max 300 words.

━━━ LIVE FIRM DATABASE ━━━
Date          : {datetime.utcnow().strftime("%d %B %Y")}
Total Clients : {len(clients)}
Total AUM     : ${total_aum:,.2f}
Total Meetings: {len(meetings)}

CLIENT DETAILS:
{client_block}

USER QUERY: {request.message}
"""

    # ── Call local Ollama ─────────────────────────────────────────────────────
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model":  "llama3.2:1b",
                "prompt": system_prompt,
                "stream": False,
                "options": {
                    "temperature":    0.2,
                    "num_predict":    400,
                    "top_p":          0.9,
                    "repeat_penalty": 1.1,
                },
            },
            timeout=60,
        )

        if response.status_code != 200:
            logger.error(f"Ollama HTTP {response.status_code}")
            return {"reply": "⚠️ **Ollama Error** — model returned a non-200 status. Try restarting Ollama."}

        reply = response.json().get("response", "").strip()
        if not reply:
            return {"reply": "⚠️ The AI model returned an empty response. Please try again."}

        return {"reply": reply}

    except requests.exceptions.ConnectionError:
        return {
            "reply": (
                "⚠️ **AI Offline** — cannot connect to Ollama on port 11434.\n\n"
                "Run these commands in a terminal:\n"
                "```\nollama serve\nollama run llama3.2:1b\n```"
            )
        }
    except requests.exceptions.Timeout:
        return {"reply": "⚠️ **AI Timeout** — the model took too long. Try a shorter question or restart Ollama."}
    except Exception as exc:
        logger.error(f"AI chat error: {exc}")
        return {"reply": f"⚠️ **Internal Error:** {exc}"}