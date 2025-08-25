
import os, json, time, hmac, hashlib, base64
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException, Header, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from jinja2 import Environment, FileSystemLoader

from sqlmodel import SQLModel, Field, Session, create_engine, select

from app.services.openai_ai import generate_ad_copies, suggest_audiences, forecast_performance, ai_insights
from app.services.shopify import fetch_products, fetch_last_30d_sales
from app.services.analytics import roi_report
from app.services.creative_ranker import pick_best_image
from app.services.learner import train_models, score_campaign_blueprints, get_last_train_report
from app.services.auto_rules import optimization_suggestions
from app.services.capi import send_capi_event

APP_TITLE = "Ads AI Panel – Pro (Meta + Shopify, TR) + CAPI"
VERSION = "v2.12"

BRAND_NAME = os.getenv("BRAND_NAME", "Merve Sarıdemir Shoes")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
SECRET_KEY = os.getenv("SECRET_KEY", "devsecret")
DB_URL = os.getenv("DATABASE_URL", "sqlite:///data.db")

SHOPIFY_WEBHOOK_SECRET = os.getenv("SHOPIFY_WEBHOOK_SECRET")  # optional

engine = create_engine(DB_URL, echo=False)

class Campaign(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    platform: str  # meta
    objective: str  # sales | traffic | awareness
    daily_budget: float
    start_date: datetime
    end_date: datetime
    status: str = "draft"
    product_id: Optional[str] = None
    ad_text: Optional[str] = None
    audience_json: Optional[str] = None
    image_path: Optional[str] = None
    predicted_ctr: Optional[float] = None
    predicted_cvr: Optional[float] = None

class SpendLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime
    platform: str
    spend: float

class SaleLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime
    source: str  # shopify
    revenue: float

class CampaignStat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime
    campaign_id: int = Field(index=True)
    impressions: int = 0
    clicks: int = 0
    add_to_cart: int = 0
    purchases: int = 0
    spend: float = 0.0
    revenue: float = 0.0
    age_band: Optional[str] = None
    city: Optional[str] = None
    interest: Optional[str] = None
    creative_type: Optional[str] = None

def init_db():
    SQLModel.metadata.create_all(engine)

app = FastAPI(title=APP_TITLE)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Environment(loader=FileSystemLoader("app/templates"))

def require_login(request: Request):
    if request.session.get("authed"):
        return True
    raise HTTPException(status_code=401, detail="Unauthorized")

@app.on_event("startup")
def on_startup():
    init_db()
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("models", exist_ok=True)

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    tpl = templates.get_template("login.html")
    return HTMLResponse(tpl.render(request=request, brand=BRAND_NAME))

@app.post("/login")
def do_login(request: Request, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        request.session["authed"] = True
        return RedirectResponse(url="/", status_code=302)
    return RedirectResponse(url="/login?error=1", status_code=302)

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    require_login(request)
    with Session(engine) as s:
        last30_spend = s.exec(select(SpendLog)).all()
        last30_sales = s.exec(select(SaleLog)).all()
        camp_count = s.exec(select(Campaign)).all()
    report = roi_report(last30_spend, last30_sales)
    insights = ai_insights(report)
    lr = get_last_train_report()
    tpl = templates.get_template("dashboard.html")
    return HTMLResponse(tpl.render(request=request, brand=BRAND_NAME, report=report, insights=insights, version=VERSION, campaigns=len(camp_count), last_train=lr))

@app.get("/products", response_class=HTMLResponse)
def products_page(request: Request):
    require_login(request)
    products = fetch_products(limit=60)
    tpl = templates.get_template("products.html")
    return HTMLResponse(tpl.render(request=request, brand=BRAND_NAME, products=products))

@app.get("/campaigns/new", response_class=HTMLResponse)
def new_campaign(request: Request, product_id: Optional[str] = None):
    require_login(request)
    tpl = templates.get_template("campaigns_new.html")
    return HTMLResponse(tpl.render(request=request, brand=BRAND_NAME, product_id=product_id))

@app.post("/campaigns/create", response_class=HTMLResponse)
async def create_campaign(
    request: Request,
    name: str = Form(...),
    platform: str = Form(...),
    objective: str = Form(...),
    daily_budget: float = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    product_id: Optional[str] = Form(None),
    base_text: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    require_login(request)
    image_path = None
    if image:
        save_path = os.path.join("uploads", f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{image.filename}")
        with open(save_path, "wb") as f:
            f.write(await image.read())
        image_path = pick_best_image([save_path]) or save_path

    ad_texts = generate_ad_copies(base_text or "", objective=objective, brand=BRAND_NAME)
    audiences = suggest_audiences(objective=objective, platform=platform)
    pred = forecast_performance(platform=platform, objective=objective, budget=daily_budget)

    with Session(engine) as s:
        c = Campaign(
            name=name,
            platform=platform,
            objective=objective,
            daily_budget=daily_budget,
            start_date=datetime.fromisoformat(start_date),
            end_date=datetime.fromisoformat(end_date),
            status="draft",
            product_id=product_id,
            ad_text=ad_texts[0] if ad_texts else None,
            audience_json=json.dumps(audiences, ensure_ascii=False),
            image_path=image_path,
            predicted_ctr=pred.get("ctr"),
            predicted_cvr=pred.get("cvr"),
        )
        s.add(c); s.commit()
    return RedirectResponse(url="/campaigns/list", status_code=302)

@app.get("/campaigns/list", response_class=HTMLResponse)
def list_campaigns(request: Request):
    require_login(request)
    with Session(engine) as s:
        rows = s.exec(select(Campaign).order_by(Campaign.id.desc())).all()
    tpl = templates.get_template("campaigns_list.html")
    return HTMLResponse(tpl.render(request=request, brand=BRAND_NAME, rows=rows))

# ---- Logging endpoints ----
@app.get("/reports/sync_shopify")
def sync_shopify_sales(request: Request):
    require_login(request)
    sales = fetch_last_30d_sales()
    with Session(engine) as s:
        for it in sales:
            s.add(SaleLog(date=it["date"], source="shopify", revenue=it["amount"]))
        s.commit()
    return RedirectResponse(url="/", status_code=302)

@app.post("/logs/spend")
def add_spend(request: Request, platform: str = Form(...), amount: float = Form(...), date: str = Form(...)):
    require_login(request)
    with Session(engine) as s:
        s.add(SpendLog(date=datetime.fromisoformat(date), platform=platform, spend=amount))
        s.commit()
    return RedirectResponse(url="/", status_code=302)

# ---- CampaignStat for learning ----
class CampaignStat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    date: datetime
    campaign_id: int = Field(index=True)
    impressions: int = 0
    clicks: int = 0
    add_to_cart: int = 0
    purchases: int = 0
    spend: float = 0.0
    revenue: float = 0.0
    age_band: Optional[str] = None
    city: Optional[str] = None
    interest: Optional[str] = None
    creative_type: Optional[str] = None

@app.post("/logs/campaign_stat")
def add_campaign_stat(
    request: Request,
    campaign_id: int = Form(...),
    date: str = Form(...),
    impressions: int = Form(0),
    clicks: int = Form(0),
    add_to_cart: int = Form(0),
    purchases: int = Form(0),
    spend: float = Form(0.0),
    revenue: float = Form(0.0),
    age_band: str = Form(None),
    city: str = Form(None),
    interest: str = Form(None),
    creative_type: str = Form(None)
):
    require_login(request)
    with Session(engine) as s:
        s.add(CampaignStat(
            campaign_id=campaign_id,
            date=datetime.fromisoformat(date),
            impressions=impressions,
            clicks=clicks,
            add_to_cart=add_to_cart,
            purchases=purchases,
            spend=spend,
            revenue=revenue,
            age_band=age_band,
            city=city,
            interest=interest,
            creative_type=creative_type
        )); s.commit()
    return RedirectResponse(url="/learn", status_code=302)

# ---- Learning & Optimization ----
@app.get("/learn", response_class=HTMLResponse)
def learn_home(request: Request):
    require_login(request)
    lr = get_last_train_report()
    tpl = templates.get_template("learn.html")
    return HTMLResponse(tpl.render(request=request, brand=BRAND_NAME, last_train=lr))

@app.post("/learn/train")
def trigger_train(request: Request):
    require_login(request)
    with Session(engine) as s:
        stats = s.exec(select(CampaignStat)).all()
        camps = s.exec(select(Campaign)).all()
    report = train_models(stats, camps)
    return RedirectResponse(url="/learn", status_code=302)

@app.get("/optimize/suggest", response_class=HTMLResponse)
def suggest_opt(request: Request):
    require_login(request)
    with Session(engine) as s:
        stats = s.exec(select(CampaignStat)).all()
        camps = s.exec(select(Campaign)).all()
    learn_scores = score_campaign_blueprints(stats, camps)
    rules = optimization_suggestions(stats, camps)
    tpl = templates.get_template("optimize.html")
    return HTMLResponse(tpl.render(request=request, brand=BRAND_NAME, scores=learn_scores, rules=rules))

# ----------------- Shopify webhook -> CAPI -----------------
def _verify_shopify_hmac(hmac_header: str, body: bytes) -> bool:
    if not SHOPIFY_WEBHOOK_SECRET:
        return True  # skip if not provided
    digest = hmac.new(SHOPIFY_WEBHOOK_SECRET.encode(), body, hashlib.sha256).digest()
    calc_hmac = base64.b64encode(digest).decode()
    return hmac.compare_digest(calc_hmac, hmac_header or "")

@app.post("/webhooks/shopify/orders_paid")
async def orders_paid(request: Request, x_shopify_hmac_sha256: Optional[str] = Header(None)):
    raw = await request.body()
    if not _verify_shopify_hmac(x_shopify_hmac_sha256, raw):
        raise HTTPException(status_code=401, detail="Invalid HMAC")

    payload = json.loads(raw.decode("utf-8"))
    order_id = payload.get("id")
    email = (payload.get("email") or "") or ((payload.get("customer") or {}).get("email") or "")
    phone = ""
    if payload.get("customer", {}).get("phone"):
        phone = payload["customer"]["phone"]
    elif payload.get("billing_address", {}).get("phone"):
        phone = payload["billing_address"]["phone"]
    value = float(payload.get("total_price") or 0.0)
    currency = payload.get("currency") or "TRY"
    event_id = str(order_id) if order_id else None

    resp = send_capi_event(
        event_name="Purchase",
        value=value,
        currency=currency,
        email=email,
        phone=phone,
        event_id=event_id,
        event_source_url=None,
        client_user_agent=None,
        test_mode=False
    )
    return JSONResponse({"ok": True, "meta": resp})

# ------------- Browser → Server forwarding with fbp/fbc -------------
@app.post("/capi/forward")
async def capi_forward(data: dict = Body(...)):
    """
    Accepts JSON from storefront (thank-you page) containing fbp/fbc, event_id, email, phone, value, currency.
    Example body:
    {
      "event_name":"Purchase", "value":1600, "currency":"TRY",
      "email":"x@y.com", "phone":"+90...", "event_id":"12345",
      "fbp":"fb.1.169...", "fbc":"fb.1.169...",
      "event_source_url":"https://shop.myshopify.com/checkout/thank_you",
      "client_user_agent": "Mozilla/5.0",
      "test_mode": true
    }
    """
    resp = send_capi_event(
        event_name=data.get("event_name") or "Purchase",
        value=float(data.get("value") or 0.0),
        currency=data.get("currency") or "TRY",
        email=data.get("email") or "",
        phone=data.get("phone") or "",
        event_id=data.get("event_id"),
        fbp=data.get("fbp"),
        fbc=data.get("fbc"),
        event_source_url=data.get("event_source_url"),
        client_user_agent=data.get("client_user_agent"),
        test_mode=bool(data.get("test_mode", False))
    )
    return JSONResponse({"ok": True, "meta": resp})

@app.get("/capi/test")
def capi_test(email: str = "test@example.com"):
    resp = send_capi_event(
        event_name="Purchase",
        value=123.45,
        currency="TRY",
        email=email,
        phone="",
        event_id=f"test-{int(time.time())}",
        test_mode=True
    )
    return JSONResponse({"ok": True, "meta": resp})

@app.get("/health")
def health():
    return {"ok": True, "app": APP_TITLE, "version": VERSION}
