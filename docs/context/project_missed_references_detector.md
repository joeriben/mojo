---
name: Missed-References-Detektor
description: MOJO-Datenbank als Grundlage um in eigenen Textentwürfen übersehene relevante Bezüge zu finden
type: project
---

Die Kombination aus articles.db (17.465+ Artikel mit Opus-Verdicts, Kernthesen, Bezügen) und corpus.json (Benjamins 160 Publikationen) bildet ein Netzwerk, das erkennen kann, wenn Benjamin in einem Textentwurf einen relevanten Bezug übersieht.

Use-Case: Benjamin lädt einen Stub/Entwurf hoch → System gleicht ab gegen:
- Artikel mit Verdict "lesenswert"/"pflichtlektüre" im selben Themenfeld
- Bezüge die Opus identifiziert hat und die zum Entwurfsthema passen
- Thinker/Konzepte die im Entwurf fehlen aber in der DB als relevant markiert sind

Das ist Use-Case 3 aus den UI-Anforderungen (dialogischer Research-Agent), aber mit einem spezifischen Mehrwert: nicht nur Retrieval, sondern aktives "Du hast X nicht zitiert, obwohl Y und Z darauf aufbauen".

**How to apply:** Dieses Feature wird umso wertvoller, je mehr Artikel durch Opus verarbeitet sind. Es ist ein starkes Argument für den großen 2025+-Run — die Datenbank wird zum Research-Instrument.
