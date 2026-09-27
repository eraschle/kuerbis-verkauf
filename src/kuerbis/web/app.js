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
const LINIENFARBE = "#2a78d6";
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
  return dialogAntwort(dlg);
}

// Liefert den Wert des geklickten Knopfs ("ok", "abbrechen", …) bzw. "abbrechen" bei Escape.
// Bewusst über submit statt close: close wird bei verdecktem Fenster verzögert ausgelöst.
function dialogAntwort(dlg) {
  return new Promise((ok) => {
    const form = dlg.querySelector("form");
    const fertig = (wert) => {
      form.removeEventListener("submit", beiSubmit);
      dlg.removeEventListener("cancel", beiAbbruch);
      ok(wert);
    };
    const beiSubmit = (e) => fertig(e.submitter ? e.submitter.value : "");
    const beiAbbruch = () => fertig("abbrechen");
    form.addEventListener("submit", beiSubmit);
    dlg.addEventListener("cancel", beiAbbruch);
  });
}

// ---------- Zustand ----------

const zustand = {
  jahre: [],
  jahr: null,
  saison: null,
  ansicht: "erfassung",
  vergleich: null, // letzte Antwort von api.vergleich()
  vergleichAuswahl: null, // Set der gezeigten Jahre; null = Standard (letzte N Jahre)
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
  if (zustand.vergleichAuswahl) {
    for (const j of [...zustand.vergleichAuswahl]) if (!zustand.jahre.includes(j)) zustand.vergleichAuswahl.delete(j);
    // Leere Auswahl (z. B. vor dem ersten Import) wieder auf den Standard setzen
    if (zustand.vergleichAuswahl.size === 0) zustand.vergleichAuswahl = null;
  }
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
  $("#jahr-wahl").parentElement.hidden = leer;
  $("#bereich-anzeige").textContent = "";
  if (leer) return;
  $("#jahr-wahl").value = zustand.jahr;
  zustand.saison = await rufe("saison", zustand.jahr);
  tabelleAufbauen();
  neueZeileVorbereiten();
  saisonAktualisieren();
  zurRelevantenZeile();
}

// Kennung der Tabellenform: ändert sie sich, wird die Tabelle neu aufgebaut
const tabellenForm = (s) => (s.zeilen.length ? `${s.zeilen[0].datum}/${s.zeilen.length}` : "leer");

function tabelleAufbauen() {
  const s = zustand.saison;
  const heute = heuteIso();
  const body = $("#tage-body");
  body.innerHTML = "";
  zustand.form = tabellenForm(s);
  if (!s.zeilen.length) {
    body.innerHTML = `<tr><td colspan="6" class="leer-hinweis">Noch keine Tage erfasst – unten in der Zeile „Neu“ beginnen.</td></tr>`;
    return;
  }
  s.zeilen.forEach((z, i) => {
    const tr = document.createElement("tr");
    tr.dataset.index = i;
    if (z.wochenstart) tr.classList.add("wochenstart");
    if (z.wochentag === "Samstag" || z.wochentag === "Sonntag") tr.classList.add("wochenende");
    if (z.datum === heute) tr.classList.add("heute");
    tr.innerHTML = `
      <td class="wo">${z.wochenstart ? z.kw : ""}</td>
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

const WOCHENTAGE_JS = ["Sonntag", "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag"];

function neueZeileVorbereiten() {
  const d = $("#neu-datum");
  d.min = `${zustand.jahr}-01-01`;
  d.max = `${zustand.jahr}-12-31`;
  d.value = zustand.saison.naechster_tag;
  $("#neu-betrag").value = "";
  $("#neu-betrag").classList.remove("ungueltig");
  neuWochentagZeigen();
}

function neuWochentagZeigen() {
  const v = $("#neu-datum").value;
  $("#neu-wochentag").textContent = v ? WOCHENTAGE_JS[new Date(v + "T00:00:00").getDay()] : "";
}
$("#neu-datum").addEventListener("change", neuWochentagZeigen);

$("#neu-betrag").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    neuenTagSpeichern();
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    const alle = document.querySelectorAll("#tage-body input");
    if (alle.length) alle[alle.length - 1].focus();
  }
});
$("#neu-datum").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    $("#neu-betrag").focus();
  }
});

async function neuenTagSpeichern() {
  const betrag = $("#neu-betrag");
  const datum = $("#neu-datum").value;
  if (!betrag.value.trim()) return;
  try {
    zustand.saison = await rufe("betrag_setzen", zustand.jahr, datum, betrag.value);
    $("#hinweis").hidden = true;
    tabelleAufbauen();
    neueZeileVorbereiten();
    saisonAktualisieren();
    gespeichert();
    const zeile = document.querySelector(`#tage-body input[data-datum="${datum}"]`);
    if (zeile) zeile.classList.add("gespeichert");
    $(".tabelle-rahmen").scrollTop = $(".tabelle-rahmen").scrollHeight;
    betrag.focus();
  } catch (e) {
    betrag.classList.add("ungueltig");
    hinweis(`${datumCH(datum)}: ${e.message}`, true);
  }
}

function saisonAktualisieren() {
  const s = zustand.saison;
  $("#bereich-anzeige").textContent = s.zeilen.length
    ? `${datumCH(s.zeilen[0].datum)} – ${datumCH(s.zeilen[s.zeilen.length - 1].datum)}`
    : "";
  const zeilen = $("#tage-body").children;
  s.zeilen.forEach((z, i) => {
    const tr = zeilen[i];
    if (!tr || !tr.querySelector(".laufend")) return;
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
  const datum = input.dataset.datum;
  try {
    zustand.saison = await rufe("betrag_setzen", zustand.jahr, datum, input.value);
    $("#hinweis").hidden = true;
    gespeichert();
    if (tabellenForm(zustand.saison) !== zustand.form) {
      // Erster oder letzter Tag entfernt: Tabelle neu aufbauen
      const fokus = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.datum : null;
      tabelleAufbauen();
      neueZeileVorbereiten();
      saisonAktualisieren();
      const ziel = fokus && document.querySelector(`#tage-body input[data-datum="${fokus}"]`);
      if (ziel) ziel.focus();
      return;
    }
    const z = zustand.saison.zeilen.find((r) => r.datum === datum);
    input.value = eingabeText(z ? z.betrag : null);
    input.dataset.alt = input.value;
    input.classList.remove("ungueltig");
    input.classList.remove("gespeichert");
    void input.offsetWidth; // Animation neu starten
    input.classList.add("gespeichert");
    saisonAktualisieren();
  } catch (e) {
    input.classList.add("ungueltig");
    hinweis(`${datumCH(datum)}: ${e.message}`, true);
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
  const ziel = alle[alle.indexOf(e.target) + richtung] || (richtung > 0 ? $("#neu-betrag") : null);
  if (ziel) {
    ziel.focus();
    ziel.closest("tr").scrollIntoView({ block: "nearest" });
  }
}

function zurRelevantenZeile() {
  const zeilen = zustand.saison.zeilen;
  const index = zeilen.findIndex((z) => z.datum === heuteIso());
  if (index >= 0) {
    const tr = $("#tage-body").children[index];
    tr.scrollIntoView({ block: "center" });
    tr.querySelector("input").focus({ preventScroll: true });
    return;
  }
  // Sonst ans Ende (dort wird weitergeschrieben)
  $(".tabelle-rahmen").scrollTop = $(".tabelle-rahmen").scrollHeight;
  if (zustand.jahr === new Date().getFullYear()) $("#neu-betrag").focus({ preventScroll: true });
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
  const zeilen = zustand.saison.zeilen; // bereits vom ersten bis zum letzten Tag
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
        borderColor: LINIENFARBE,
        backgroundColor: LINIENFARBE,
        borderWidth: 2,
        pointRadius: zeilen.length === 1 ? 4 : 0, // ein einzelner Tag ergibt sonst keine sichtbare Linie
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

// ---------- Saison anlegen ----------

$("#btn-neue-saison").addEventListener("click", () => {
  const jetzt = new Date().getFullYear();
  const jahr = zustand.jahre.includes(jetzt) ? Math.max(...zustand.jahre) + 1 : jetzt;
  const dlg = $("#dlg-saison");
  $("#dlg-jahr").value = jahr;
  $("#dlg-saison-fehler").textContent = "";
  dlg.returnValue = "";
  dlg.showModal();
  dlg.querySelector("form").onsubmit = async (e) => {
    if (e.submitter && e.submitter.value !== "ok") return;
    e.preventDefault();
    const j = Number($("#dlg-jahr").value);
    try {
      await rufe("neue_saison", j);
      dlg.close("ok");
      gespeichert();
      await statusLaden(j);
      if (zustand.ansicht !== "erfassung") await ansichtZeigen("erfassung");
      $("#neu-betrag").focus();
    } catch (err) {
      $("#dlg-saison-fehler").textContent = err.message;
    }
  };
});

// ---------- Vergleich ----------

// Farben nach Alter: laufendes Jahr kräftig orange, frühere Jahre ein Blau-Verlauf von dunkel (letztes Jahr)
// nach hell (ältere). Die Farbe hängt am Jahr selbst, nicht an der Auswahl – sie bleibt beim Umschalten stabil.
const AKTUELL_FARBE = "#eb6834";
const ALTERS_RAMPE = ["#0d366b", "#104281", "#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7", "#6da7ec", "#86b6ef"];
const BEREICH_RAND = "#898781";
const BEREICH_FLAECHE = "rgba(137, 135, 129, 0.16)";
const MAX_VERGLEICH = 10;

function jahresFarbe(jahr, aktuell) {
  if (jahr >= aktuell) return AKTUELL_FARBE;
  return ALTERS_RAMPE[Math.min(aktuell - jahr - 1, ALTERS_RAMPE.length - 1)];
}

function markeMinMax(jahr, bereich) {
  if (jahr === bereich.max) return ` <span class="marke-mm max">▲ Max</span>`;
  if (jahr === bereich.min) return ` <span class="marke-mm min">▼ Min</span>`;
  return "";
}

async function vergleichZeigen() {
  const daten = await rufe("vergleich");
  zustand.vergleich = daten;
  if (zustand.vergleichAuswahl === null) {
    // Standard: die letzten N Jahre (MIN/MAX sind als Fläche immer sichtbar)
    zustand.vergleichAuswahl = new Set(zustand.jahre.slice(0, daten.anzahl_jahre));
  }
  const wahl = $("#anzahl-jahre");
  wahl.innerHTML = Array.from({ length: MAX_VERGLEICH }, (_, i) => `<option value="${i + 1}">${i + 1}</option>`).join("");
  wahl.value = daten.anzahl_jahre;
  bereichInfoZeigen(daten);
  chipsZeigen(daten);
  vergleichsDiagramm(daten);
  jahresTotalDiagramm(daten);
}

function bereichInfoZeigen(daten) {
  const b = daten.bereich;
  $("#bereich-info").innerHTML =
    b.max === null
      ? `<span class="gedaempft">Noch keine abgeschlossenen Jahre für den MIN/MAX-Bereich</span>`
      : `<span class="flaeche"></span> Bereich: <span class="marke-mm min">▼ Min ${b.min}</span> – <span class="marke-mm max">▲ Max ${b.max}</span>` +
        (daten.ausgenommen.length ? ` <span class="gedaempft">(ohne ${daten.ausgenommen.join(", ")})</span>` : "");
}

$("#anzahl-jahre").addEventListener("change", async (e) => {
  try {
    await rufe("vergleich_einstellen", Number(e.target.value), zustand.vergleich.ausgenommen);
    zustand.vergleichAuswahl = null; // Auswahl auf den neuen Standard zurücksetzen
    await vergleichZeigen();
  } catch (err) {
    hinweis(err.message, true);
  }
});

function chipsZeigen(daten) {
  const box = $("#jahr-chips");
  const auswahl = zustand.vergleichAuswahl;
  const voll = auswahl.size >= MAX_VERGLEICH;
  box.innerHTML = "";
  for (const j of zustand.jahre) {
    const aktiv = auswahl.has(j);
    const b = document.createElement("button");
    b.className = "chip";
    b.setAttribute("aria-pressed", aktiv);
    b.disabled = !aktiv && voll;
    b.innerHTML = `<span class="punkt"></span>${j}${markeMinMax(j, daten.bereich)}`;
    if (aktiv) b.querySelector(".punkt").style.background = jahresFarbe(j, daten.aktuelles_jahr);
    b.addEventListener("click", () => {
      if (aktiv) auswahl.delete(j);
      else auswahl.add(j);
      vergleichZeigen();
    });
    box.appendChild(b);
  }
}

// Achsenposition (Tage seit Montag der KW 1) -> Kalenderwoche / Wochentag
const achseKw = (a) => Math.floor(a / 7) + 1;
const ACHSE_TAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"];

function datumPlus(iso, tage) {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + tage);
  return `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.`;
}

function vergleichsDiagramm(daten) {
  const nachJahr = new Map(daten.jahre.map((j) => [j.jahr, j]));
  const gewaehlt = daten.jahre
    .filter((j) => zustand.vergleichAuswahl.has(j.jahr) && j.erster_tag !== null)
    .sort((a, b) => b.jahr - a.jahr);
  const bandJahre = [daten.bereich.min, daten.bereich.max].map((j) => nachJahr.get(j)).filter((j) => j && j.erster_tag !== null);
  const alle = [...gewaehlt, ...bandJahre];

  // Achse: vom Montag der frühesten KW bis zum spätesten letzten Verkaufstag
  const von = alle.length ? Math.min(...alle.map((j) => j.erster_tag)) : 0;
  const achseStart = von - (((von % 7) + 7) % 7);
  const achseEnde = alle.length ? Math.max(...alle.map((j) => j.erster_tag + j.kumuliert.length - 1)) : -1;
  const positionen = Array.from({ length: Math.max(0, achseEnde - achseStart + 1) }, (_, i) => achseStart + i);

  const reihe = (j, auffuellen) =>
    positionen.map((a) => {
      const i = a - j.erster_tag;
      if (i >= 0 && i < j.kumuliert.length) return j.kumuliert[i];
      if (!auffuellen) return null;
      return i < 0 ? 0 : j.kumuliert[j.kumuliert.length - 1]; // vor Saisonbeginn 0, danach Endstand
    });

  const datasets = gewaehlt.map((j) => {
    const farbe = jahresFarbe(j.jahr, daten.aktuelles_jahr);
    const aktuell = j.jahr === daten.aktuelles_jahr;
    return {
      label: String(j.jahr),
      data: reihe(j, false),
      borderColor: farbe,
      backgroundColor: farbe,
      borderWidth: aktuell ? 3 : 2,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointHoverBorderColor: "#fcfcfb",
      pointHoverBorderWidth: 2,
      tension: 0,
      order: aktuell ? 0 : 1,
      _erster: j.erster_tag,
      _erstesDatum: j.erstes_datum,
    };
  });

  // MIN/MAX-Fläche: zuerst die MIN-Kurve, dann die MAX-Kurve mit Füllung bis zur vorherigen
  if (bandJahre.length === 2) {
    const [jMin, jMax] = bandJahre;
    const rand = { borderColor: BEREICH_RAND, borderWidth: 1, borderDash: [4, 3], pointRadius: 0, pointHoverRadius: 0, tension: 0, order: 5 };
    datasets.push(
      { ...rand, label: `Min ${jMin.jahr}`, data: reihe(jMin, true), fill: false, _band: "Min", _erster: jMin.erster_tag, _erstesDatum: jMin.erstes_datum },
      { ...rand, label: `Max ${jMax.jahr}`, data: reihe(jMax, true), fill: "-1", backgroundColor: BEREICH_FLAECHE, _band: "Max", _erster: jMax.erster_tag, _erstesDatum: jMax.erstes_datum }
    );
  }

  diagrammSetzen("vergleich", $("#chart-vergleich"), {
    type: "line",
    data: { labels: positionen, datasets },
    options: {
      maintainAspectRatio: false,
      animation: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        filler: { propagate: false },
        tooltip: {
          ...tooltipBasis,
          filter: (it) => it.raw !== null,
          itemSort: (a, b) => b.raw - a.raw,
          callbacks: {
            title: (it) => {
              const a = positionen[it[0].dataIndex];
              return `KW ${achseKw(a)}, ${ACHSE_TAGE[((a % 7) + 7) % 7]}`;
            },
            label: (it) => {
              const a = positionen[it.dataIndex];
              const i = a - it.dataset._erster;
              if (it.dataset._band) {
                const zusatz = i < 0 ? " (noch nicht begonnen)" : "";
                return ` ${it.dataset.label}${zusatz}: CHF ${chf(it.raw)}`;
              }
              return ` ${it.dataset.label} (${datumPlus(it.dataset._erstesDatum, i)}): CHF ${chf(it.raw)}`;
            },
          },
        },
      },
      scales: {
        ...achsen(),
        x: {
          ...achsen().x,
          title: { display: true, text: "Kalenderwoche", color: GEDAEMPFT },
          ticks: {
            color: GEDAEMPFT,
            maxRotation: 0,
            autoSkip: false,
            callback: (_, i) => (((positionen[i] % 7) + 7) % 7 === 0 ? `KW ${achseKw(positionen[i])}` : null),
          },
        },
      },
    },
  });

  const legende = gewaehlt.map(
    (j) => `<span><i style="background:${jahresFarbe(j.jahr, daten.aktuelles_jahr)}"></i>${j.jahr}: CHF ${chf(j.total)}${markeMinMax(j.jahr, daten.bereich)}</span>`
  );
  if (bandJahre.length === 2) {
    legende.push(`<span><i class="gestrichelt"></i>Bereich Min ${daten.bereich.min} – Max ${daten.bereich.max}</span>`);
  }
  $("#legende-vergleich").innerHTML = legende.join("");
}

// Zeichnet „Max“ / „Min“ über die entsprechenden Balken
const balkenMarken = {
  id: "balkenMarken",
  afterDatasetsDraw(chart, _args, opts) {
    const { ctx } = chart;
    const meta = chart.getDatasetMeta(0);
    ctx.save();
    ctx.font = "600 11px system-ui, -apple-system, 'Segoe UI', sans-serif";
    ctx.fillStyle = TINTE_2;
    ctx.textAlign = "center";
    (opts.marken || []).forEach((text, i) => {
      if (text && meta.data[i]) ctx.fillText(text, meta.data[i].x, meta.data[i].y - 5);
    });
    ctx.restore();
  },
};

function jahresTotalDiagramm(daten) {
  const jahre = daten.jahre;
  const b = daten.bereich;
  const farbe = (j) =>
    j.jahr === b.max || j.jahr === b.min ? "#b54a12" : j.jahr >= daten.aktuelles_jahr ? "#f5b58f" : TAGESFARBE;
  diagrammSetzen("jahre", $("#chart-jahre"), {
    type: "bar",
    plugins: [balkenMarken],
    data: {
      labels: jahre.map((j) => j.jahr),
      datasets: [{
        label: "Jahrestotal",
        data: jahre.map((j) => j.total),
        backgroundColor: jahre.map(farbe),
        hoverBackgroundColor: "#c9531f",
        borderRadius: { topLeft: 4, topRight: 4 },
        borderSkipped: "bottom",
        maxBarThickness: 28,
      }],
    },
    options: {
      maintainAspectRatio: false,
      animation: false,
      layout: { padding: { top: 16 } },
      plugins: {
        legend: { display: false },
        balkenMarken: { marken: jahre.map((j) => (j.jahr === b.max ? "Max" : j.jahr === b.min ? "Min" : "")) },
        tooltip: {
          ...tooltipBasis,
          displayColors: false,
          callbacks: {
            label: (it) => {
              const j = jahre[it.dataIndex];
              const zusatz = j.jahr === b.max ? " (Max)" : j.jahr === b.min ? " (Min)" : j.jahr >= daten.aktuelles_jahr ? " (laufend)" : "";
              return `CHF ${chf(it.raw)}${zusatz}`;
            },
          },
        },
      },
      scales: achsen(),
    },
  });
}

// ---------- MIN/MAX-Jahre anpassen ----------

$("#btn-bereich").addEventListener("click", async () => {
  const daten = zustand.vergleich;
  if (!daten) return;
  const aus = new Set(daten.ausgenommen);
  $("#bereich-body").innerHTML = daten.abgeschlossen.length
    ? daten.abgeschlossen
        .map(
          (j) => `<tr><td><label><input type="checkbox" value="${j.jahr}" ${aus.has(j.jahr) ? "" : "checked"}>${j.jahr}${markeMinMax(j.jahr, daten.bereich)}</label></td><td class="zahl">CHF ${chf(j.total)}</td></tr>`
        )
        .join("")
    : `<tr><td class="gedaempft">Noch keine abgeschlossenen Jahre.</td></tr>`;
  const dlg = $("#dlg-bereich");
  dlg.returnValue = "";
  dlg.showModal();
  if ((await dialogAntwort(dlg)) !== "ok") return;
  const ausgenommen = [...dlg.querySelectorAll("#bereich-body input:not(:checked)")].map((c) => Number(c.value));
  try {
    await rufe("vergleich_einstellen", daten.anzahl_jahre, ausgenommen);
    await vergleichZeigen();
  } catch (e) {
    hinweis(e.message, true);
  }
});
$("#bereich-alle").addEventListener("click", () => document.querySelectorAll("#bereich-body input").forEach((c) => (c.checked = true)));

// ---------- Übersicht ----------

async function uebersichtZeigen() {
  const u = await rufe("uebersicht");
  const kopfStat = "<thead><tr><th>Jahr</th><th>Erster Tag</th><th>Letzter Tag</th><th class='zahl'>Tage</th><th class='zahl'>Total</th><th class='zahl'>Mittel</th><th class='zahl'>Min</th><th class='zahl'>Max</th></tr></thead>";
  $("#tabelle-statistik").innerHTML =
    kopfStat +
    "<tbody>" +
    u.zeilen
      .map((z) => {
        const s = z.statistik;
        const klasse = z.jahr === u.bereich.max ? "zeile-max" : z.jahr === u.bereich.min ? "zeile-min" : "";
        return `<tr class="${klasse}"><td>${z.jahr}${markeMinMax(z.jahr, u.bereich)}</td><td>${datumCH(z.erster_tag)}</td><td>${datumCH(z.letzter_tag)}</td><td class="zahl">${s.tage}</td><td class="zahl">${chf(s.total)}</td><td class="zahl">${chf(s.mittel)}</td><td class="zahl">${chf(s.min)}</td><td class="zahl">${chf(s.max)}</td></tr>`;
      })
      .join("") +
    "</tbody>";

  const wochenKopf = u.kws.map((w) => `<th class="zahl">KW ${w}</th>`).join("");
  $("#tabelle-wochen").innerHTML =
    `<thead><tr><th>Jahr</th>${wochenKopf}</tr></thead><tbody>` +
    u.zeilen
      .map((z) => `<tr class="${z.jahr === u.bereich.max ? "zeile-max" : z.jahr === u.bereich.min ? "zeile-min" : ""}"><td>${z.jahr}${markeMinMax(z.jahr, u.bereich)}</td>${z.wochen.map((w) => `<td class="zahl">${chf(w)}</td>`).join("")}</tr>`)
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
      const was = datumCH(c.datum);
      const fmt = (v) => `CHF ${chf(v)}`;
      return `<tr><td>${c.jahr}</td><td>${was}</td>
        <td class="zahl"><label class="wahl"><input type="radio" name="k${i}" value="mein" data-id="${c.id}" checked>${fmt(c.mein)}</label></td>
        <td class="zahl"><label class="wahl"><input type="radio" name="k${i}" value="import" data-id="${c.id}">${fmt(c.import)}</label></td></tr>`;
    })
    .join("");

  const dlg = $("#dlg-import");
  dlg.returnValue = "";
  dlg.showModal();
  if ((await dialogAntwort(dlg)) !== "ok") {
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
