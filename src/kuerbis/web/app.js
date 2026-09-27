"use strict";

// ---------- Hilfsfunktionen ----------

const $ = (sel) => document.querySelector(sel);
const zahlFormat = new Intl.NumberFormat("de-CH", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
const rappenFormat = new Intl.NumberFormat("de-CH", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const chf = (x) =>
  x === null || x === undefined ? "" : Number.isInteger(x) ? zahlFormat.format(x) : rappenFormat.format(x);
const datumCH = (iso) => (iso ? `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}` : "");
const kurzDatum = (iso) => `${iso.slice(8, 10)}.${iso.slice(5, 7)}.`;
const eingabeText = (x) => (x === null || x === undefined ? "" : String(x));
const heuteIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

// Kategorische Palette (validiert, feste Reihenfolge; siehe dataviz-Referenz)
const PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
const MAX_VERGLEICH = PALETTE.length;
const TAGESFARBE = "#eb6834";
const TINTE_2 = "#52514e";
const GEDAEMPFT = "#898781";
const GITTER = "#e1e0d9";

async function rufe(name, ...args) {
  const antwort = await window.pywebview.api[name](...args);
  if (antwort && antwort.fehler) throw new Error(antwort.fehler);
  return antwort;
}

let hinweisTimer;
function hinweis(text, fehler = false) {
  const el = $("#hinweis");
  el.textContent = text;
  el.classList.toggle("fehler", fehler);
  el.hidden = false;
  clearTimeout(hinweisTimer);
  if (!fehler) hinweisTimer = setTimeout(() => (el.hidden = true), 6000);
}
$("#hinweis").addEventListener("click", () => ($("#hinweis").hidden = true));

function gespeichert() {
  const d = new Date();
  $("#speicher-status").textContent = `Gespeichert ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function frage(text, knoepfe) {
  const dlg = $("#dlg-frage");
  $("#frage-text").textContent = text;
  const box = $("#frage-knoepfe");
  box.innerHTML = "";
  for (const k of knoepfe) {
    const b = document.createElement("button");
    b.value = k.wert;
    b.textContent = k.label;
    b.className = "knopf" + (k.primaer ? " primaer" : "");
    box.appendChild(b);
  }
  dlg.returnValue = "";
  dlg.showModal();
  return new Promise((ok) => dlg.addEventListener("close", () => ok(dlg.returnValue), { once: true }));
}

// ---------- Zustand ----------

const zustand = {
  jahre: [],
  jahr: null,
  saison: null,
  ansicht: "erfassung",
  vergleichSlots: new Map(), // Jahr -> Palettenplatz (bleibt beim An-/Abwählen anderer Jahre stabil)
  vergleichInit: false,
};
const charts = {};

// ---------- Start ----------

async function start() {
  Chart.defaults.font.family = 'system-ui, -apple-system, "Segoe UI", sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = TINTE_2;
  await statusLaden();
}

async function statusLaden(bevorzugtesJahr) {
  const st = await window.pywebview.api.status();
  $("#datenpfad").textContent = st.datenpfad;
  zustand.jahre = st.jahre;
  if (st.fehler) {
    hinweis(st.fehler, true);
    speicherortDialog();
  }
  const wahl = $("#jahr-wahl");
  wahl.innerHTML = zustand.jahre.map((j) => `<option value="${j}">${j}</option>`).join("");
  let jahr = bevorzugtesJahr ?? zustand.jahr;
  if (!zustand.jahre.includes(jahr)) jahr = zustand.jahre[0] ?? null;
  zustand.jahr = jahr;
  zustand.vergleichInit = false;
  for (const j of [...zustand.vergleichSlots.keys()]) if (!zustand.jahre.includes(j)) zustand.vergleichSlots.delete(j);
  await ansichtZeigen(zustand.ansicht);
}

// ---------- Reiter ----------

document.querySelectorAll(".reiter button").forEach((b) =>
  b.addEventListener("click", () => ansichtZeigen(b.dataset.ansicht))
);

async function ansichtZeigen(name) {
  zustand.ansicht = name;
  document.querySelectorAll(".reiter button").forEach((b) => b.setAttribute("aria-selected", b.dataset.ansicht === name));
  document.querySelectorAll(".ansicht").forEach((s) => (s.hidden = s.id !== `ansicht-${name}`));
  try {
    if (name === "erfassung") await erfassungZeigen();
    if (name === "vergleich") await vergleichZeigen();
    if (name === "uebersicht") await uebersichtZeigen();
  } catch (e) {
    hinweis(e.message, true);
  }
}

// ---------- Erfassung ----------

$("#jahr-wahl").addEventListener("change", (e) => {
  zustand.jahr = Number(e.target.value);
  erfassungZeigen();
});

async function erfassungZeigen() {
  const leer = zustand.jahr === null;
  $("#leer-hinweis").hidden = !leer;
  $("#erfassung-inhalt").hidden = leer;
  $("#btn-start-aendern").hidden = leer;
  $("#jahr-wahl").parentElement.hidden = leer;
  $("#start-anzeige").textContent = "";
  if (leer) return;
  $("#jahr-wahl").value = zustand.jahr;
  zustand.saison = await rufe("saison", zustand.jahr);
  tabelleAufbauen();
  saisonAktualisieren();
  zurRelevantenZeile();
}

function tabelleAufbauen() {
  const s = zustand.saison;
  const heute = heuteIso();
  const body = $("#tage-body");
  body.innerHTML = "";
  s.zeilen.forEach((z, i) => {
    const tr = document.createElement("tr");
    tr.dataset.index = i;
    if (i % 7 === 0) tr.classList.add("wochenstart");
    if (z.wochentag === "Samstag" || z.wochentag === "Sonntag") tr.classList.add("wochenende");
    if (z.datum === heute) tr.classList.add("heute");
    tr.innerHTML = `
      <td class="wo">${i % 7 === 0 ? z.woche : ""}</td>
      <td>${z.wochentag}</td>
      <td>${datumCH(z.datum)}</td>
      <td class="zahl"><input inputmode="decimal" autocomplete="off" aria-label="Betrag ${datumCH(z.datum)}"></td>
      <td class="zahl laufend"></td>
      <td class="zahl wochentotal"></td>`;
    const input = tr.querySelector("input");
    input.value = eingabeText(z.betrag);
    input.dataset.datum = z.datum;
    input.dataset.alt = input.value;
    input.addEventListener("change", () => betragSpeichern(input));
    input.addEventListener("keydown", tastenNavigation);
    input.addEventListener("focus", () => input.select());
    body.appendChild(tr);
  });
}

function saisonAktualisieren() {
  const s = zustand.saison;
  $("#start-anzeige").textContent = `Start: ${datumCH(s.start)}`;
  const zeilen = $("#tage-body").children;
  s.zeilen.forEach((z, i) => {
    const tr = zeilen[i];
    if (!tr) return;
    tr.querySelector(".laufend").textContent = chf(z.laufend);
    tr.querySelector(".wochentotal").textContent = chf(z.wochentotal);
  });
  kachelnZeigen(s.statistik);
  jahresDiagramme();
}

function kachelnZeigen(st) {
  const k = (titel, wert, neben = "") =>
    `<div class="kachel"><div class="titel">${titel}</div><div class="wert">${wert}</div><div class="neben">${neben}</div></div>`;
  $("#kacheln").innerHTML =
    k("Total", `CHF ${chf(st.total)}`) +
    k("Verkaufstage", st.tage) +
    k("Mittel pro Tag", st.mittel === null ? "–" : `CHF ${chf(st.mittel)}`) +
    k("Bester Tag", st.max === null ? "–" : `CHF ${chf(st.max)}`, st.min === null ? "" : `schwächster: CHF ${chf(st.min)}`);
}

async function betragSpeichern(input) {
  try {
    zustand.saison = await rufe("betrag_setzen", zustand.jahr, input.dataset.datum, input.value);
    const z = zustand.saison.zeilen.find((r) => r.datum === input.dataset.datum);
    input.value = eingabeText(z ? z.betrag : null);
    input.dataset.alt = input.value;
    input.classList.remove("ungueltig");
    input.classList.remove("gespeichert");
    void input.offsetWidth; // Animation neu starten
    input.classList.add("gespeichert");
    $("#hinweis").hidden = true;
    saisonAktualisieren();
    gespeichert();
  } catch (e) {
    input.classList.add("ungueltig");
    hinweis(`${datumCH(input.dataset.datum)}: ${e.message}`, true);
  }
}

function tastenNavigation(e) {
  const richtung = e.key === "Enter" || e.key === "ArrowDown" ? 1 : e.key === "ArrowUp" ? -1 : 0;
  if (e.key === "Escape") {
    e.target.value = e.target.dataset.alt;
    e.target.classList.remove("ungueltig");
    return;
  }
  if (!richtung) return;
  e.preventDefault();
  const alle = [...document.querySelectorAll("#tage-body input")];
  const ziel = alle[alle.indexOf(e.target) + richtung];
  if (ziel) {
    ziel.focus();
    ziel.closest("tr").scrollIntoView({ block: "nearest" });
  } else {
    e.target.blur();
  }
}

function zurRelevantenZeile() {
  const zeilen = zustand.saison.zeilen;
  let index = zeilen.findIndex((z) => z.datum === heuteIso());
  if (index < 0) {
    for (let i = zeilen.length - 1; i >= 0; i--) if (zeilen[i].betrag !== null) { index = i; break; }
  }
  const tr = $("#tage-body").children[Math.max(index, 0)];
  if (tr) tr.scrollIntoView({ block: "center" });
  if (index >= 0 && zeilen[index].datum === heuteIso()) tr.querySelector("input").focus({ preventScroll: true });
}

function achsen(yTitel) {
  return {
    x: { grid: { display: false }, border: { color: "#c3c2b7" }, ticks: { color: GEDAEMPFT, maxRotation: 0, autoSkipPadding: 12 } },
    y: {
      beginAtZero: true,
      grid: { color: GITTER },
      border: { display: false },
      ticks: { color: GEDAEMPFT, callback: (v) => zahlFormat.format(v) },
      title: yTitel ? { display: true, text: yTitel, color: GEDAEMPFT } : undefined,
    },
  };
}

const tooltipBasis = {
  backgroundColor: "#0b0b0b",
  titleColor: "#fff",
  bodyColor: "#fff",
  padding: 10,
  cornerRadius: 6,
  displayColors: true,
  boxWidth: 8,
  boxHeight: 8,
  usePointStyle: true,
};

function diagrammSetzen(name, canvas, konfig) {
  if (charts[name]) charts[name].destroy();
  charts[name] = new Chart(canvas, konfig);
}

function jahresDiagramme() {
  const s = zustand.saison;
  // Nur bis zum letzten Tag mit Eintrag (mind. 16 Wochen Rahmen wäre leer)
  let ende = s.zeilen.length;
  const letzter = s.zeilen.map((z) => z.betrag !== null).lastIndexOf(true);
  if (letzter >= 0) ende = Math.min(s.zeilen.length, Math.max(letzter + 8, 28));
  const zeilen = s.zeilen.slice(0, ende);
  const labels = zeilen.map((z) => kurzDatum(z.datum));

  diagrammSetzen("tage", $("#chart-tage"), {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Tagesbetrag",
        data: zeilen.map((z) => z.betrag),
        backgroundColor: TAGESFARBE,
        hoverBackgroundColor: "#c9531f",
        borderRadius: { topLeft: 4, topRight: 4 },
        borderSkipped: "bottom",
        maxBarThickness: 14,
        categoryPercentage: 0.9,
      }],
    },
    options: {
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltipBasis,
          callbacks: {
            title: (it) => `${zeilen[it[0].dataIndex].wochentag}, ${datumCH(zeilen[it[0].dataIndex].datum)}`,
            label: (it) => ` CHF ${chf(it.raw)}`,
          },
        },
      },
      scales: achsen(),
    },
  });

  diagrammSetzen("laufend", $("#chart-laufend"), {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Laufendes Total",
        data: zeilen.map((z) => z.laufend),
        borderColor: PALETTE[0],
        backgroundColor: PALETTE[0],
        borderWidth: 2,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBorderColor: "#fcfcfb",
        pointHoverBorderWidth: 2,
        spanGaps: true,
        tension: 0,
      }],
    },
    options: {
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltipBasis,
          filter: (it) => it.raw !== null,
          callbacks: {
            title: (it) => datumCH(zeilen[it[0].dataIndex].datum),
            label: (it) => ` Total CHF ${chf(it.raw)}`,
          },
        },
      },
      scales: achsen(),
    },
  });
}

// ---------- Saison anlegen / ändern ----------

$("#btn-neue-saison").addEventListener("click", async () => {
  const jetzt = new Date().getFullYear();
  const jahr = zustand.jahre.includes(jetzt) ? Math.max(...zustand.jahre) + 1 : jetzt;
  const { start } = await window.pywebview.api.vorschlag_start(jahr);
  saisonDialog({ titel: "Neue Saison", jahr, start, neu: true });
});

$("#btn-start-aendern").addEventListener("click", () => {
  saisonDialog({ titel: `Startdatum ${zustand.jahr} ändern`, jahr: zustand.jahr, start: zustand.saison.start, neu: false });
});

$("#dlg-jahr").addEventListener("change", async (e) => {
  const jahr = Number(e.target.value);
  if (jahr > 1990 && jahr < 2100) $("#dlg-start").value = (await window.pywebview.api.vorschlag_start(jahr)).start;
});

function saisonDialog({ titel, jahr, start, neu }) {
  const dlg = $("#dlg-saison");
  $("#dlg-saison-titel").textContent = titel;
  $("#dlg-jahr").value = jahr;
  $("#dlg-jahr").disabled = !neu;
  $("#dlg-start").value = start;
  $("#dlg-saison-fehler").textContent = "";
  dlg.returnValue = "";
  dlg.showModal();
  dlg.onclose = null;
  const form = dlg.querySelector("form");
  form.onsubmit = async (e) => {
    if (e.submitter && e.submitter.value !== "ok") return;
    e.preventDefault();
    const j = Number($("#dlg-jahr").value);
    const s = $("#dlg-start").value;
    if (!s) return ($("#dlg-saison-fehler").textContent = "Bitte ein Startdatum wählen.");
    if (Number(s.slice(0, 4)) !== j) return ($("#dlg-saison-fehler").textContent = `Das Startdatum muss im Jahr ${j} liegen.`);
    try {
      if (neu) await rufe("neue_saison", j, s);
      else await rufe("start_aendern", j, s);
      dlg.close("ok");
      gespeichert();
      await statusLaden(j);
      if (zustand.ansicht !== "erfassung") ansichtZeigen("erfassung");
    } catch (err) {
      $("#dlg-saison-fehler").textContent = err.message;
    }
  };
}

// ---------- Vergleich ----------

function freierSlot() {
  const belegt = new Set(zustand.vergleichSlots.values());
  for (let i = 0; i < MAX_VERGLEICH; i++) if (!belegt.has(i)) return i;
  return -1;
}

async function vergleichZeigen() {
  if (!zustand.vergleichInit) {
    if (zustand.vergleichSlots.size === 0) {
      // Standard: neuestes Jahr + die 4 davor (neuestes bekommt Farbe 1)
      zustand.jahre.slice(0, 5).forEach((j) => zustand.vergleichSlots.set(j, freierSlot()));
    }
    zustand.vergleichInit = true;
  }
  const daten = await rufe("vergleich");
  chipsZeigen();
  vergleichsDiagramm(daten);
  jahresTotalDiagramm(daten);
}

function chipsZeigen() {
  const box = $("#jahr-chips");
  const voll = zustand.vergleichSlots.size >= MAX_VERGLEICH;
  box.innerHTML = "";
  for (const j of zustand.jahre) {
    const aktiv = zustand.vergleichSlots.has(j);
    const b = document.createElement("button");
    b.className = "chip";
    b.setAttribute("aria-pressed", aktiv);
    b.disabled = !aktiv && voll;
    b.innerHTML = `<span class="punkt"></span>${j}`;
    if (aktiv) b.querySelector(".punkt").style.background = PALETTE[zustand.vergleichSlots.get(j)];
    b.addEventListener("click", () => {
      if (aktiv) zustand.vergleichSlots.delete(j);
      else zustand.vergleichSlots.set(j, freierSlot());
      vergleichZeigen();
    });
    box.appendChild(b);
  }
}

function vergleichsDiagramm(daten) {
  const gewaehlt = daten.jahre.filter((j) => zustand.vergleichSlots.has(j.jahr)).sort((a, b) => b.jahr - a.jahr);
  const laenge = Math.max(0, ...gewaehlt.map((j) => j.kumuliert.length));
  const labels = Array.from({ length: laenge }, (_, i) => i + 1);
  const datasets = gewaehlt.map((j) => {
    const farbe = PALETTE[zustand.vergleichSlots.get(j.jahr)];
    return {
      label: String(j.jahr),
      data: j.kumuliert,
      borderColor: farbe,
      backgroundColor: farbe,
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointHoverBorderColor: "#fcfcfb",
      pointHoverBorderWidth: 2,
      tension: 0,
      _start: j.start,
    };
  });
  const tagDatum = (start, i) => {
    const d = new Date(start + "T00:00:00");
    d.setDate(d.getDate() + i);
    return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.`;
  };
  diagrammSetzen("vergleich", $("#chart-vergleich"), {
    type: "line",
    data: { labels, datasets },
    options: {
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          ...tooltipBasis,
          itemSort: (a, b) => b.raw - a.raw,
          callbacks: {
            title: (it) => `Saisontag ${it[0].label}`,
            label: (it) => ` ${it.dataset.label} (${tagDatum(it.dataset._start, it.dataIndex)}): CHF ${chf(it.raw)}`,
          },
        },
      },
      scales: {
        ...achsen(),
        x: { ...achsen().x, title: { display: true, text: "Saisontag", color: GEDAEMPFT } },
      },
    },
  });
  $("#legende-vergleich").innerHTML = gewaehlt
    .map((j) => `<span><i style="background:${PALETTE[zustand.vergleichSlots.get(j.jahr)]}"></i>${j.jahr}: CHF ${chf(j.total)}</span>`)
    .join("");
}

function jahresTotalDiagramm(daten) {
  const jahre = daten.jahre;
  diagrammSetzen("jahre", $("#chart-jahre"), {
    type: "bar",
    data: {
      labels: jahre.map((j) => j.jahr),
      datasets: [{
        label: "Jahrestotal",
        data: jahre.map((j) => j.total),
        backgroundColor: TAGESFARBE,
        hoverBackgroundColor: "#c9531f",
        borderRadius: { topLeft: 4, topRight: 4 },
        borderSkipped: "bottom",
        maxBarThickness: 28,
      }],
    },
    options: {
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: { display: false },
        tooltip: { ...tooltipBasis, displayColors: false, callbacks: { label: (it) => `CHF ${chf(it.raw)}` } },
      },
      scales: achsen(),
    },
  });
}

// ---------- Übersicht ----------

async function uebersichtZeigen() {
  const u = await rufe("uebersicht");
  const kopfStat = "<thead><tr><th>Jahr</th><th>Start</th><th class='zahl'>Tage</th><th class='zahl'>Total</th><th class='zahl'>Mittel</th><th class='zahl'>Min</th><th class='zahl'>Max</th></tr></thead>";
  $("#tabelle-statistik").innerHTML =
    kopfStat +
    "<tbody>" +
    u.zeilen
      .map((z) => {
        const s = z.statistik;
        return `<tr><td>${z.jahr}</td><td>${datumCH(z.start)}</td><td class="zahl">${s.tage}</td><td class="zahl">${chf(s.total)}</td><td class="zahl">${chf(s.mittel)}</td><td class="zahl">${chf(s.min)}</td><td class="zahl">${chf(s.max)}</td></tr>`;
      })
      .join("") +
    "</tbody>";

  const wochenKopf = Array.from({ length: u.max_wochen }, (_, i) => `<th class="zahl">Wo ${i + 1}</th>`).join("");
  $("#tabelle-wochen").innerHTML =
    `<thead><tr><th>Jahr</th>${wochenKopf}</tr></thead><tbody>` +
    u.zeilen
      .map((z) => {
        const zellen = Array.from({ length: u.max_wochen }, (_, i) => `<td class="zahl">${z.wochen[i] ? chf(z.wochen[i]) : ""}</td>`).join("");
        return `<tr><td>${z.jahr}</td>${zellen}</tr>`;
      })
      .join("") +
    "</tbody>";
}

// ---------- Export ----------

$("#btn-export").addEventListener("click", (e) => {
  e.stopPropagation();
  $("#export-menue").hidden = !$("#export-menue").hidden;
});
document.addEventListener("click", () => ($("#export-menue").hidden = true));
document.querySelectorAll("[data-export]").forEach((b) =>
  b.addEventListener("click", async () => {
    try {
      const r = await rufe("export_dialog", b.dataset.export);
      if (!r.abgebrochen) hinweis("Export gespeichert.");
    } catch (e) {
      hinweis(`Export fehlgeschlagen: ${e.message}`, true);
    }
  })
);

// ---------- Import ----------

$("#btn-import").addEventListener("click", async () => {
  let vorschau;
  try {
    vorschau = await rufe("import_dialog");
  } catch (e) {
    return hinweis(`Import nicht möglich: ${e.message}`, true);
  }
  if (vorschau.abgebrochen) return;

  const k = vorschau.konflikte;
  const teile = [];
  if (vorschau.neue_jahre) teile.push(`${vorschau.neue_jahre} neue Saison(s)`);
  if (vorschau.neue_tage) teile.push(`${vorschau.neue_tage} neue Tageseinträge`);
  if (k.length) teile.push(`${k.length} abweichende Werte`);
  $("#import-zusammenfassung").textContent =
    `Die Datei enthält die Jahre ${vorschau.jahre.join(", ") || "–"}. ` +
    (teile.length ? `Gefunden: ${teile.join(", ")}.` : "Alle Daten sind bereits vorhanden – es gibt nichts Neues.");

  $("#import-konflikte").hidden = k.length === 0;
  $("#konflikt-body").innerHTML = k
    .map((c, i) => {
      const was = c.art === "start" ? "Startdatum" : datumCH(c.datum);
      const fmt = (v) => (c.art === "start" ? datumCH(v) : `CHF ${chf(v)}`);
      return `<tr><td>${c.jahr}</td><td>${was}</td>
        <td class="zahl"><label class="wahl"><input type="radio" name="k${i}" value="mein" data-id="${c.id}" checked>${fmt(c.mein)}</label></td>
        <td class="zahl"><label class="wahl"><input type="radio" name="k${i}" value="import" data-id="${c.id}">${fmt(c.import)}</label></td></tr>`;
    })
    .join("");

  const dlg = $("#dlg-import");
  dlg.returnValue = "";
  dlg.showModal();
  dlg.addEventListener(
    "close",
    async () => {
      if (dlg.returnValue !== "ok") {
        await window.pywebview.api.import_abbrechen();
        return;
      }
      const wahl = {};
      dlg.querySelectorAll("#konflikt-body input:checked").forEach((r) => (wahl[r.dataset.id] = r.value));
      try {
        const info = await rufe("import_abschliessen", wahl);
        gespeichert();
        hinweis(
          `Import abgeschlossen: ${info.neue_jahre} neue Saison(s), ${info.neue_tage} neue Tage, ` +
            `${info.konflikte_import} Werte übernommen, ${info.konflikte_mein} eigene behalten.`
        );
        await statusLaden();
      } catch (e) {
        hinweis(`Import fehlgeschlagen: ${e.message}`, true);
      }
    },
    { once: true }
  );
});

const alleSetzen = (wert) => document.querySelectorAll(`#konflikt-body input[value="${wert}"]`).forEach((r) => (r.checked = true));
$("#alle-mein").addEventListener("click", () => alleSetzen("mein"));
$("#alle-import").addEventListener("click", () => alleSetzen("import"));

// ---------- Speicherort ----------

$("#btn-speicherort").addEventListener("click", () => speicherortDialog());

function speicherortDialog() {
  $("#dlg-pfad").textContent = $("#datenpfad").textContent;
  const dlg = $("#dlg-speicherort");
  if (!dlg.open) dlg.showModal();
}

$("#ort-verschieben").addEventListener("click", async () => {
  const dlg = $("#dlg-speicherort");
  try {
    let r = await rufe("speicherort_verschieben_dialog");
    if (r.abgebrochen) return;
    if (r.existiert) {
      dlg.close();
      const antwort = await frage(`Am gewählten Ort gibt es bereits eine Datei:\n${r.pfad}\n\nWas soll passieren?`, [
        { wert: "abbrechen", label: "Abbrechen" },
        { wert: "oeffnen", label: "Diese Datei öffnen" },
        { wert: "ueberschreiben", label: "Mit meinen Daten überschreiben", primaer: true },
      ]);
      if (antwort === "ueberschreiben") r = await rufe("speicherort_verschieben", r.pfad, true);
      else if (antwort === "oeffnen") r = await rufe("speicherort_oeffnen", r.pfad);
      else return;
    }
    if (dlg.open) dlg.close();
    hinweis(`Die Daten werden jetzt hier gespeichert: ${r.datenpfad}`);
    await statusLaden();
  } catch (e) {
    hinweis(e.message, true);
  }
});

$("#ort-oeffnen").addEventListener("click", async () => {
  try {
    const r = await rufe("speicherort_oeffnen_dialog");
    if (r.abgebrochen) return;
    $("#dlg-speicherort").close();
    $("#hinweis").hidden = true;
    hinweis(`Geöffnet: ${r.datenpfad}`);
    await statusLaden();
  } catch (e) {
    hinweis(e.message, true);
  }
});

// ---------- Brücke bereit ----------

if (new URLSearchParams(location.search).has("devapi")) {
  // Nur für Tests im normalen Browser: leitet Aufrufe an einen lokalen Testserver weiter.
  window.pywebview = {
    api: new Proxy({}, {
      get: (_, name) => (...args) =>
        fetch(`/api/${name}`, { method: "POST", body: JSON.stringify(args) }).then((r) => r.json()),
    }),
  };
  start();
} else if (window.pywebview && window.pywebview.api && window.pywebview.api.status) {
  start();
} else {
  window.addEventListener("pywebviewready", start, { once: true });
}
