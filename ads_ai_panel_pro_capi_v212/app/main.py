import os
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

APP_VERSION = "v2.13-dashboard"

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "258654")
SECRET_KEY = os.getenv("SECRET_KEY", "supersecret123")

app = FastAPI(title="Ads AI Panel")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)


# 🔐 Dashboard (root)
@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    if not request.session.get("authed"):
        return RedirectResponse(url="/login", status_code=303)

    return HTMLResponse(f"""
    <!doctype html><html><head><meta charset="utf-8"><title>Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body class="bg-light">
      <div class="container py-5">
        <div class="card shadow">
          <div class="card-body">
            <h2 class="mb-3">Hoş geldin 👋</h2>
            <p>Artık panele giriş yaptın. Burada Shopify ve Meta entegrasyonları olacak.</p>
            <p class="text-muted">Versiyon: {APP_VERSION}</p>
            <a href="/logout" class="btn btn-outline-danger">Çıkış Yap</a>
          </div>
        </div>
      </div>
    </body></html>
    """)


# 🔑 Login Sayfası
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    error = request.query_params.get("error")
    return HTMLResponse(f"""
    <!doctype html><html><head><meta charset="utf-8"><title>Giriş</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body class="bg-light">
      <div class="container py-5"><div class="row justify-content-center"><div class="col-md-4">
        <div class="card shadow"><div class="card-body">
          <h5 class="mb-3">Ads AI Panel – Giriş</h5>
          {"<div class='alert alert-danger'>Parola hatalı</div>" if error else ""}
          <form method="post" action="/login">
            <div class="mb-3"><label class="form-label">Parola</label>
              <input type="password" class="form-control" name="password" required></div>
            <button class="btn btn-primary w-100">Giriş Yap</button>
          </form>
        </div></div>
      </div></div></div>
    </body></html>
    """)


# 🔓 Login İşlemi
@app.post("/login")
def do_login(request: Request, password: str = Form(...)):
    if (password or "").strip() == (ADMIN_PASSWORD or "").strip():
        request.session["authed"] = True
        return RedirectResponse(url="/", status_code=303)
    return RedirectResponse(url="/login?error=1", status_code=303)


# 🚪 Logout
@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


# 🩺 Health check
@app.get("/health")
def health(request: Request):
    return {
        "ok": True,
        "version": APP_VERSION,
        "logged_in": bool(request.session.get("authed"))
    }
