---
name: Citation-Tracker muss Vornamen prüfen
description: Nachname allein reicht nicht für Citation-Matching — Vornamen-Initial muss geprüft werden, sonst False Positives bei Namesakes
type: feedback
---

Citation-Tracker darf nie nur auf Nachnamen matchen. Immer die 4 kanonischen Namensformen prüfen (Vorname Nachname, V. Nachname, Nachname Vorname, Nachname V.) und bei falschem Initial rejecten.

**Why:** J. Jörissen (2020) wurde fälschlich als Benjamin-Zitat erkannt. Bei häufigen Namen (Meier, Schmidt) wäre das katastrophal.

**How to apply:** Bei jeder Änderung am Citation-Tracker oder bei neuen Matching-Strategien: immer Vornamen-Disambiguierung beibehalten. Testfälle mit falschen Initialen laufen lassen.
