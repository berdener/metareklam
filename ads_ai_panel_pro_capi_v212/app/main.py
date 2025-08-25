import os
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

APP_VERSION = "v2.13-fixed"

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "258654")

app = FastAPI(title="Ads AI Panel")

@app.get("/", response_class=HTMLResponse)
def root():
    # Root URL'ye girenleri login sayfasına al
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
def login_page():
    return HTMLResponse("""
    <!doctype html><html><head><meta charset="utf-8"><title>Giriş</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body class="bg-light">
      <div class="container py-5"><div class="row justify-content-center"><div class="col-md-4">
        <div class="card shadow"><div class="card-body">
          <h5 class="mb-3">Ads AI Panel – Giriş</h5>
          <form method="post" action="/login">
            <div class="mb-3"><label class="form-label">Parola</label>
              <input type="password" class="form-control" name="password" required></div>
            <button class="btn btn-primary w-100">Giriş Yap</button>
          </form>
        </div></div>
      </div></div></div>
    </body></html>
    """)

@app.post("/login")
def do_login(password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        # Şimdilik demo: girişten sonra health sayfasına yönlendiriyoruz
        return RedirectResponse(url="/health", status_code=302)
    return RedirectResponse(url="/login?error=1", status_code=302)

@app.get("/health")
def health():
    return {"ok": True, "version": APP_VERSION}
