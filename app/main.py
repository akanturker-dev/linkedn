from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db, engine, servis
from .config import load_settings

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="LinkedIn Müşteri Bulma Asistanı (web paneli)")


@app.on_event("startup")
def _baslangic():
    servis.baslat()


@app.on_event("shutdown")
def _kapanis():
    servis.kapat()


class AyarModel(BaseModel):
    serper_api_key: Optional[str] = None
    calisma_saatleri: Optional[dict] = None
    limitler: Optional[dict] = None
    mesaj_sablonlari: Optional[dict] = None
    headless_tarayici: Optional[bool] = None


class GorevModel(BaseModel):
    sektor: str
    sehir: str


class LeadGuncelleModel(BaseModel):
    linkedin_url: Optional[str] = None
    durum: Optional[str] = None
    notlar: Optional[str] = None


@app.get("/api/leads")
def leads_listele(durum: Optional[str] = None, arama: Optional[str] = None):
    return db.leads_getir(durum=durum, arama=arama)


@app.patch("/api/leads/{lead_id}")
def lead_guncelle(lead_id: int, model: LeadGuncelleModel):
    try:
        return servis.lead_guncelle(lead_id, model.dict())
    except LookupError as e:
        raise HTTPException(404, str(e))


@app.delete("/api/leads/{lead_id}")
def lead_sil(lead_id: int):
    db.lead_sil(lead_id)
    return {"ok": True}


@app.get("/api/gorevler")
def gorevler_listele():
    return db.gorevleri_getir()


@app.post("/api/gorevler")
def gorev_ekle(model: GorevModel):
    try:
        return {"id": servis.gorev_ekle(model.sektor, model.sehir)}
    except servis.AyarHatasi as e:
        raise HTTPException(400, str(e))


@app.delete("/api/gorevler/{gorev_id}")
def gorev_sil(gorev_id: int):
    db.gorev_sil(gorev_id)
    return {"ok": True}


@app.get("/api/settings")
def ayarlari_getir():
    return load_settings()


@app.put("/api/settings")
def ayarlari_kaydet(model: AyarModel):
    try:
        return servis.ayarlari_kaydet(model.dict())
    except servis.AyarHatasi as e:
        raise HTTPException(400, str(e))


@app.get("/api/durum")
def durum_getir():
    return servis.durum()


@app.get("/api/log")
def log_getir(limit: int = 200):
    return db.son_loglar(limit)


@app.post("/api/otomasyon/baslat")
def otomasyon_baslat():
    servis.otomasyonu_ayarla(True)
    return {"ok": True}


@app.post("/api/otomasyon/durdur")
def otomasyon_durdur():
    servis.otomasyonu_ayarla(False)
    return {"ok": True}


@app.post("/api/linkedin/giris")
def linkedin_giris():
    engine.komut_gonder("giris_yap")
    return {"ok": True}


@app.post("/api/guvenlik/devam")
def guvenlik_devam():
    engine.komut_gonder("guvenlik_devam")
    return {"ok": True}


app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def index():
    return FileResponse(str(WEB_DIR / "index.html"))
