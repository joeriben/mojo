# Iter 30 — Abstract-Anreicherung via OpenAlex (Robustheits-Abschluss)

## Anforderung
Iter 23: 43 % des blinden Stroms abstract-los, Ranker dort ≈Zufall. articles.db hat `openalex_abstract`.
Rettet ein OpenAlex-Backfill die abstract-losen Artikel, erholt sich die rich-AUC?

## Messung (`iter_30_abstract_enrichment.py`)
abstract-arm (<50 Zeichen): 81 (18 %), davon blind 51.
- **mit OpenAlex-Abstract rettbar: 0 / 81 (0 %)**
- irreduzibel abstract-los: 81 / 81
- blind abstract-arm gerettet: 0 / 51

rich-AUC (Anreicherung ändert nichts, weil 0 gerettet): abstract-arm 0.650→0.650; blind gesamt 0.665→0.665.

## Harte Kritik
- **Der kostenlose Backfill-Fix scheitert vollständig (P6, P15):** OpenAlex hat für **0 von 81**
  abstract-losen Artikeln einen Abstract — `openalex_abstract` ist genau dort leer, wo der Haupt-Abstract
  fehlt. Das sind die OJS/RSS/Nicht-OpenAlex-Quellen (Memory-Sonderfälle zkmb/e-flux). Die naheliegende,
  billige Lösung für die Iter-23-Robustheitslücke existiert **nicht**. Ehrlich: ich hatte gehofft, hier
  einen leichten Fix zu finden; die Daten sagen nein.
- **Konsequenz, konkret (P7):** die abstract-lose Teilmenge (18 % gesamt, 43 % blind) ist nur über
  **echtes Volltext-/Landing-Page-Fetching** (die §2.5-Eskalations-Infrastruktur, Memory) erreichbar —
  oder muss auf einen **separaten Pfad** mit niedriger Konfidenz (Titel+Konzepte + Bibliometrie +
  Eskalations-Flag). Sie darf NICHT mit einem Zufalls-Score in die Hauptliste gemischt werden (Iter 24:
  das würde überdies die Kalibrierung verfälschen).
- **Selbstkorrektur gegen Scheinwiderspruch (P3):** die abstract-arm-AUC hier (0.650 auf alen<50
  *gemischt*) ist NICHT vergleichbar mit Iter 23s 0.532 (auf screening-alen<200). Die alen<50-Menge
  enthält die signalstarken intentional-positiven Altartikel (hohe keep-Rate, distinktive Titel/
  Konzepte), die auch ohne Abstract gut ranken. Andere Scheibe, kein Widerspruch — ich weise das aus,
  statt die höhere Zahl als „Erholung" zu verkaufen (das wäre genau die Art Selbsttäuschung, die P15
  verbietet; es gab keine Erholung, es wurden 0 Artikel verändert).
- **Was robust bleibt:** der Ranker funktioniert auf abstract-reichen Artikeln (~0.65 blind); die
  abstract-lose Lücke ist real, irreduzibel ohne Fetching, und jetzt **beziffert** (51/120 blind). Eine
  bekannte, eingegrenzte Schwäche ist besser als eine kaschierte.

## → nächste Iteration (Phase E — Synthese)
Iter 31: **Gesamt-Architektur-Synthese** — alle belastbaren Befunde (01–30) zu einem dokumentierten
Filter-System-Entwurf zusammenführen: blinder Ranker (rich+journal-lift-only), Bibliometrie-Präzisions-
Anker, substitutiver Komponist (3 Enrichment-Achsen), Abstract-Gate + Eskalationspfad, Ehrlichkeits-
Regeln (Rang statt Prozent, screening-only-Messung). Mit der ehrlichen Leistungs-Bilanz, nicht der Headline.
