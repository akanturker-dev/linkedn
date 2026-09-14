const DURUM_ETIKET = {
  yeni: "Yeni",
  sira_kontrol_edildi: "Sıra Kontrol Edildi",
  linkedin_bulundu: "LinkedIn Bulundu",
  linkedin_bulunamadi: "LinkedIn Bulunamadı",
  istek_gonderildi: "İstek Gönderildi",
  baglanti_kabul: "Bağlantı Kabul Edildi",
  mesaj_gonderildi: "Mesaj Gönderildi",
  ilgilenmiyor: "İlgilenmiyor",
  hata: "Hata",
};

const GOREV_ETIKET = { aktif: "Aranıyor", tamamlandi: "Tamamlandı" };

const SABLON_ALANLARI = {
  baglanti_notu: "set-sablon-not",
  ilk_mesaj: "set-sablon-mesaj",
  ilk_mesaj_bulunamadi: "set-sablon-bulunamadi",
  ilk_mesaj_ust_sira: "set-sablon-ust-sira",
};

const state = {
  leads: [],
  settings: null,
  durum: null,
  sortKey: "id",
  sortDir: "desc",
  filtreDurum: "",
  aramaMetni: "",
};

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

// Dis kaynaktan gelen linklerde javascript: gibi semalari engeller
function guvenliUrl(u) {
  return /^https?:\/\//i.test(u || "") ? u : "#";
}

async function api(path, options = {}) {
  const resp = await fetch(path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!resp.ok) {
    let mesaj = `Hata ${resp.status}`;
    try {
      const govde = await resp.json();
      if (govde.detail) mesaj = typeof govde.detail === "string" ? govde.detail : JSON.stringify(govde.detail);
    } catch (_) {}
    throw new Error(mesaj);
  }
  return resp.json();
}

async function kullaniciIslemi(fn) {
  try {
    await fn();
  } catch (e) {
    alert(e.message);
  }
}

/* ---------------- Adaylar tablosu ---------------- */

async function leadleriYukle() {
  const params = new URLSearchParams();
  if (state.filtreDurum) params.set("durum", state.filtreDurum);
  if (state.aramaMetni) params.set("arama", state.aramaMetni);
  try {
    state.leads = await api(`/api/leads?${params.toString()}`);
  } catch (_) {
    return;
  }
  tabloyuCiz();
}

function siraliLeadler() {
  const { sortKey, sortDir } = state;
  return [...state.leads].sort((a, b) => {
    let av = a[sortKey] ?? "";
    let bv = b[sortKey] ?? "";
    if (typeof av === "string") av = av.toLowerCase();
    if (typeof bv === "string") bv = bv.toLowerCase();
    if (av < bv) return sortDir === "asc" ? -1 : 1;
    if (av > bv) return sortDir === "asc" ? 1 : -1;
    return 0;
  });
}

function siraMetni(lead) {
  if (lead.google_sirasi) return `${lead.google_sayfasi}. sayfa, ${lead.google_sirasi}. sıra`;
  if (!lead.google_arama_terimi) return "Kontrol edilmedi";
  return "İlk 30'da yok";
}

function tabloyuCiz() {
  const tbody = document.getElementById("leads-tbody");
  const leads = siraliLeadler();
  document.getElementById("bos-durum").hidden = leads.length > 0;
  tbody.innerHTML = "";
  for (const lead of leads) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(lead.isletme_adi)}</td>
      <td>${escapeHtml(lead.sektor)}</td>
      <td>${escapeHtml(lead.sehir)}</td>
      <td class="website-hucre" title="${escapeHtml(lead.website)}">${escapeHtml(lead.website)}</td>
      <td>${escapeHtml(siraMetni(lead))}</td>
      <td>${lead.maps_puani ?? "-"}${lead.maps_yorum_sayisi ? ` (${lead.maps_yorum_sayisi})` : ""}</td>
      <td><span class="badge badge-${escapeHtml(lead.durum)}">${escapeHtml(DURUM_ETIKET[lead.durum] || lead.durum)}</span></td>
      <td>${lead.son_islem_tarihi ? new Date(lead.son_islem_tarihi).toLocaleString("tr-TR") : "-"}</td>
    `;
    tr.addEventListener("click", () => modalAc(lead.id));
    tbody.appendChild(tr);
  }
}

/* ---------------- Aday detayı penceresi ---------------- */

function modalAc(leadId) {
  const lead = state.leads.find((l) => l.id === leadId);
  if (!lead) return;
  const linkedinHucre = lead.linkedin_url
    ? `<a href="${escapeHtml(guvenliUrl(lead.linkedin_url))}" target="_blank" rel="noopener">${escapeHtml(lead.linkedin_ad || "Profili aç")}</a>`
    : "-";
  document.getElementById("modal-baslik").textContent = lead.isletme_adi;
  document.getElementById("modal-body").innerHTML = `
    <div class="modal-satir"><span class="etiket">Sektör / Şehir</span><span>${escapeHtml(lead.sektor)} / ${escapeHtml(lead.sehir)}</span></div>
    <div class="modal-satir"><span class="etiket">Website</span><a href="${escapeHtml(guvenliUrl(lead.website))}" target="_blank" rel="noopener">${escapeHtml(lead.website)}</a></div>
    <div class="modal-satir"><span class="etiket">Telefon</span><span>${escapeHtml(lead.telefon || "-")}</span></div>
    <div class="modal-satir"><span class="etiket">Google Sırası</span><span>${escapeHtml(siraMetni(lead))}</span></div>
    <div class="modal-satir"><span class="etiket">LinkedIn</span><span>${linkedinHucre}</span></div>
    <div class="modal-satir"><span class="etiket">Durum</span><span class="badge badge-${escapeHtml(lead.durum)}">${escapeHtml(DURUM_ETIKET[lead.durum] || lead.durum)}</span></div>
    <label class="field"><span>LinkedIn kişi profili (elle düzeltebilirsin)</span>
      <input type="text" id="modal-linkedin-url" value="${escapeHtml(lead.linkedin_url || "")}" placeholder="https://www.linkedin.com/in/..." />
    </label>
    <label class="field"><span>Notlar</span>
      <textarea id="modal-notlar" rows="3">${escapeHtml(lead.notlar || "")}</textarea>
    </label>
    <div class="modal-actions">
      <button class="btn btn-accent" id="modal-kaydet">Kaydet</button>
      <button class="btn btn-ghost" id="modal-tekrar-dene">Baştan Değerlendir</button>
      <button class="btn btn-ghost" id="modal-ilgilenmiyor">İlgilenmiyor İşaretle</button>
      <button class="btn btn-danger" id="modal-sil">Sil</button>
    </div>
  `;
  const guncelle = (govde) =>
    kullaniciIslemi(async () => {
      await api(`/api/leads/${leadId}`, { method: "PATCH", body: JSON.stringify(govde) });
      modalKapat();
      leadleriYukle();
      durumuYukle();
    });
  document.getElementById("modal-kaydet").addEventListener("click", () =>
    guncelle({
      linkedin_url: document.getElementById("modal-linkedin-url").value.trim(),
      notlar: document.getElementById("modal-notlar").value,
    })
  );
  document.getElementById("modal-tekrar-dene").addEventListener("click", () => guncelle({ durum: "yeni" }));
  document.getElementById("modal-ilgilenmiyor").addEventListener("click", () => guncelle({ durum: "ilgilenmiyor" }));
  document.getElementById("modal-sil").addEventListener("click", () => {
    if (!confirm("Bu aday silinsin mi?")) return;
    kullaniciIslemi(async () => {
      await api(`/api/leads/${leadId}`, { method: "DELETE" });
      modalKapat();
      leadleriYukle();
      durumuYukle();
    });
  });
  document.getElementById("modal-overlay").hidden = false;
}

function modalKapat() {
  document.getElementById("modal-overlay").hidden = true;
}

/* ---------------- Durum, özet ve istatistik kartları ---------------- */

async function durumuYukle() {
  const pill = document.getElementById("durum-pill");
  const ozet = document.getElementById("kullanim-ozet");
  try {
    state.durum = await api("/api/durum");
  } catch (_) {
    pill.textContent = "Sunucuya ulaşılamıyor";
    pill.className = "durum-pill guvenlik";
    ozet.textContent = "BAŞLAT.cmd ile programı tekrar aç.";
    return;
  }
  const d = state.durum;

  if (d.guvenlik_kontrolu) {
    pill.textContent = "Güvenlik kontrolü bekleniyor";
    pill.className = "durum-pill guvenlik";
  } else if (d.giris_bekleniyor) {
    pill.textContent = "LinkedIn girişi bekleniyor";
    pill.className = "durum-pill bekliyor";
  } else if (d.calisiyor) {
    pill.textContent = "Çalışıyor";
    pill.className = "durum-pill calisiyor";
  } else {
    pill.textContent = "Durduruldu";
    pill.className = "durum-pill durduruldu";
  }
  document.getElementById("guvenlik-banner").hidden = !d.guvenlik_kontrolu;

  const oturum =
    d.bot_giris_yapildi === true ? "LinkedIn: bağlı" :
    d.bot_giris_yapildi === false ? "LinkedIn: giriş yapılmamış" :
    "LinkedIn: henüz kontrol edilmedi";
  const limitler = state.settings?.limitler;
  ozet.textContent = limitler
    ? `${oturum} · Son 24 saat: ${d.baglanti_son_gun}/${limitler.baglanti_gunluk} istek, ${d.mesaj_son_gun}/${limitler.mesaj_gunluk} mesaj`
    : oturum;

  const btn = document.getElementById("btn-otomasyon");
  btn.textContent = d.calisiyor ? "Otomasyonu Durdur" : "Otomasyonu Başlat";
  btn.classList.toggle("aktif", d.calisiyor);

  istatistikKartlariniCiz(d);
}

function istatistikKartlariniCiz(d) {
  const dagilim = d.durum_dagilimi || {};
  const kartlar = [
    ["Toplam Aday", d.toplam_aday || 0],
    ["LinkedIn Bulundu", dagilim.linkedin_bulundu || 0],
    ["İstek Gönderildi", dagilim.istek_gonderildi || 0],
    ["Bağlantı Kabul", dagilim.baglanti_kabul || 0],
    ["Mesaj Gönderildi", dagilim.mesaj_gonderildi || 0],
    ["Hata", dagilim.hata || 0],
  ];
  document.getElementById("stat-cards").innerHTML = kartlar
    .map(([etiket, deger]) => `<div class="stat-card"><div class="deger">${deger}</div><div class="etiket">${etiket}</div></div>`)
    .join("");
}

/* ---------------- Aktivite günlüğü ---------------- */

async function logYukle() {
  let loglar;
  try {
    loglar = await api("/api/log?limit=150");
  } catch (_) {
    return;
  }
  document.getElementById("log-list").innerHTML = loglar
    .map(
      (l) => `<div class="log-satir ${escapeHtml(l.seviye)}">
        <span class="log-zaman">${new Date(l.zaman).toLocaleString("tr-TR")}</span>
        <span class="log-mesaj">${escapeHtml(l.mesaj)}</span>
      </div>`
    )
    .join("");
}

/* ---------------- Arama görevleri ---------------- */

async function gorevleriYukle() {
  const gorevler = await api("/api/gorevler");
  const el = document.getElementById("gorev-listesi");
  el.innerHTML = gorevler
    .map(
      (g) => `<li class="gorev-item">
        <span>${escapeHtml(g.sektor)} / ${escapeHtml(g.sehir)}</span>
        <span class="gorev-durum">${escapeHtml(GOREV_ETIKET[g.durum] || g.durum)}</span>
        <button data-id="${g.id}" class="gorev-sil" title="Görevi sil">×</button>
      </li>`
    )
    .join("");
  el.querySelectorAll(".gorev-sil").forEach((btn) => {
    btn.addEventListener("click", () =>
      kullaniciIslemi(async () => {
        await api(`/api/gorevler/${btn.dataset.id}`, { method: "DELETE" });
        gorevleriYukle();
      })
    );
  });
}

/* ---------------- Ayarlar ---------------- */

async function ayarlariYukle() {
  const s = (state.settings = await api("/api/settings"));
  document.getElementById("set-api-key").value = s.serper_api_key || "";
  document.getElementById("set-saat-baslangic").value = s.calisma_saatleri.baslangic;
  document.getElementById("set-saat-bitis").value = s.calisma_saatleri.bitis;
  document.getElementById("set-limit-baglanti-saat").value = s.limitler.baglanti_saatlik;
  document.getElementById("set-limit-baglanti-gun").value = s.limitler.baglanti_gunluk;
  document.getElementById("set-limit-mesaj-gun").value = s.limitler.mesaj_gunluk;
  for (const [anahtar, alanId] of Object.entries(SABLON_ALANLARI)) {
    document.getElementById(alanId).value = s.mesaj_sablonlari[anahtar] || "";
  }
}

let bildirimZamanlayici = null;

async function ayarlariKaydet() {
  const sablonlar = {};
  for (const [anahtar, alanId] of Object.entries(SABLON_ALANLARI)) {
    sablonlar[anahtar] = document.getElementById(alanId).value;
  }
  const yeni = {
    serper_api_key: document.getElementById("set-api-key").value.trim(),
    calisma_saatleri: {
      baslangic: Number(document.getElementById("set-saat-baslangic").value),
      bitis: Number(document.getElementById("set-saat-bitis").value),
    },
    limitler: {
      baglanti_saatlik: Number(document.getElementById("set-limit-baglanti-saat").value),
      baglanti_gunluk: Number(document.getElementById("set-limit-baglanti-gun").value),
      mesaj_gunluk: Number(document.getElementById("set-limit-mesaj-gun").value),
    },
    mesaj_sablonlari: sablonlar,
  };
  const bildirim = document.getElementById("kayit-bildirim");
  try {
    state.settings = await api("/api/settings", { method: "PUT", body: JSON.stringify(yeni) });
    bildirim.textContent = "Ayarlar kaydedildi ✓";
    bildirim.className = "kayit-bildirim";
  } catch (e) {
    bildirim.textContent = e.message;
    bildirim.className = "kayit-bildirim hata";
  }
  bildirim.hidden = false;
  clearTimeout(bildirimZamanlayici);
  bildirimZamanlayici = setTimeout(() => (bildirim.hidden = true), 8000);
  durumuYukle();
}

/* ---------------- Olaylar ---------------- */

function olaylariBagla() {
  document.getElementById("btn-ayar-kaydet").addEventListener("click", ayarlariKaydet);

  document.getElementById("btn-gorev-ekle").addEventListener("click", () =>
    kullaniciIslemi(async () => {
      const sektor = document.getElementById("yeni-sektor").value.trim();
      const sehir = document.getElementById("yeni-sehir").value.trim();
      if (!sektor || !sehir) throw new Error("Sektör ve şehir gir.");
      await api("/api/gorevler", { method: "POST", body: JSON.stringify({ sektor, sehir }) });
      document.getElementById("yeni-sektor").value = "";
      document.getElementById("yeni-sehir").value = "";
      gorevleriYukle();
    })
  );

  document.getElementById("btn-otomasyon").addEventListener("click", () =>
    kullaniciIslemi(async () => {
      const yol = state.durum?.calisiyor ? "/api/otomasyon/durdur" : "/api/otomasyon/baslat";
      await api(yol, { method: "POST" });
      durumuYukle();
    })
  );

  document.getElementById("btn-linkedin-giris").addEventListener("click", () =>
    kullaniciIslemi(async () => {
      await api("/api/linkedin/giris", { method: "POST" });
      durumuYukle();
      alert(
        "Birkaç saniye içinde ayrı bir tarayıcı penceresi açılacak. LinkedIn'e o pencereden giriş yap.\n\n" +
          "Giriş bitince o pencereyi kapatma, simge durumuna küçült: asistan o pencereyi kullanıyor."
      );
    })
  );

  document.getElementById("btn-guvenlik-devam").addEventListener("click", () =>
    kullaniciIslemi(async () => {
      await api("/api/guvenlik/devam", { method: "POST" });
      durumuYukle();
    })
  );

  document.getElementById("arama-kutusu").addEventListener("input", (e) => {
    state.aramaMetni = e.target.value;
    leadleriYukle();
  });

  document.getElementById("durum-filtre").addEventListener("change", (e) => {
    state.filtreDurum = e.target.value;
    leadleriYukle();
  });

  document.getElementById("btn-tablo-yenile").addEventListener("click", leadleriYukle);

  document.querySelectorAll("#leads-table thead th").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      state.sortDir = state.sortKey === key && state.sortDir === "asc" ? "desc" : "asc";
      state.sortKey = key;
      tabloyuCiz();
    });
  });

  document.getElementById("modal-kapat").addEventListener("click", modalKapat);
  document.getElementById("modal-overlay").addEventListener("click", (e) => {
    if (e.target.id === "modal-overlay") modalKapat();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") modalKapat();
  });

  document.getElementById("log-toggle").addEventListener("click", () => {
    const drawer = document.getElementById("log-drawer");
    drawer.classList.toggle("acik");
    document.getElementById("log-toggle-ok").textContent = drawer.classList.contains("acik") ? "▼" : "▲";
  });
}

/* ---------------- Başlangıç ---------------- */

async function baslat() {
  olaylariBagla();
  try {
    await ayarlariYukle();
    await gorevleriYukle();
  } catch (_) {}
  await Promise.all([leadleriYukle(), durumuYukle(), logYukle()]);
  setInterval(leadleriYukle, 8000);
  setInterval(durumuYukle, 5000);
  setInterval(logYukle, 5000);
}

baslat();
