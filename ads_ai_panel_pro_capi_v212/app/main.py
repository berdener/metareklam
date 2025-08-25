from fastapi import FastAPI
from fastapi.responses import RedirectResponse

app = FastAPI()

@app.get("/")
def root():
    # Root URL'ye girince otomatik dashboard'a yönlendirsin
    return RedirectResponse(url="/login")

@app.get("/health")
def health():
    return {"ok": True, "version": "v2.13"}
