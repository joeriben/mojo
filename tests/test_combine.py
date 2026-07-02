"""Tests für die Triage-Kombination (journal_bot/combine.py)."""

from journal_bot.combine import combine_triage, combine_votes


def test_konsens_behalten_ist_staerkstes_signal():
    c = combine_triage("lesenswert", "scannen")
    assert c.keep and c.consensus and not c.flagged
    assert c.state == "konsens_behalten"


def test_konsens_wegwerfen_ist_einziger_wegwurf():
    c = combine_triage("ignorieren", "ignorieren")
    assert not c.keep and c.consensus and not c.flagged
    assert c.state == "konsens_wegwerfen"


def test_dissens_wird_recall_schuetzend_behalten_und_geflaggt():
    # nur Cascade will behalten
    c1 = combine_triage("scannen", "ignorieren")
    assert c1.keep and not c1.consensus and c1.flagged and c1.state == "dissens"
    # nur LLM will behalten
    c2 = combine_triage("ignorieren", "lesenswert")
    assert c2.keep and not c2.consensus and c2.flagged and c2.state == "dissens"


def test_vereinigung_behalten_schnitt_wegwerfen():
    # Behalten gdw. mindestens eine Stimme behalten will.
    assert combine_triage("scannen", "ignorieren").keep
    assert combine_triage("ignorieren", "scannen").keep
    assert combine_triage("lesenswert", "lesenswert").keep
    # Wegwerfen nur wenn beide wegwerfen.
    assert not combine_triage("ignorieren", "ignorieren").keep


def test_pflichtlektuere_zaehlt_als_behalten():
    assert combine_triage("pflichtlektuere", "ignorieren").keep
    assert combine_triage("pflichtlektuere", "lesenswert").state == "konsens_behalten"


def test_display_label_nimmt_schaerferes_verdikt():
    assert combine_triage("lesenswert", "scannen").display_label == "lesenswert"
    assert combine_triage("scannen", "lesenswert").display_label == "lesenswert"
    assert combine_triage("ignorieren", "ignorieren").display_label == "ignorieren"


def test_nur_ein_signal_folgt_diesem_unsicher():
    c = combine_triage("scannen", None)
    assert c.keep and c.state == "ein_signal" and c.flagged
    c2 = combine_triage(None, "ignorieren")
    assert not c2.keep and c2.state == "ein_signal" and c2.flagged


def test_kein_signal_recall_schuetzend_behalten():
    c = combine_triage(None, "")
    assert c.keep and c.state == "ein_signal" and c.flagged


def test_unbekanntes_label_zaehlt_nicht_als_stimme():
    # 'unbekannt' ist keine Behalten- und keine Wegwerf-Stimme.
    c = combine_triage("unbekannt", "ignorieren")
    assert c.state == "ein_signal" and not c.keep


# ── N-Stimmen (Cascade + mehrere LLM) ────────────────────────────────────────

def test_n_stimmen_konsens_behalten():
    c = combine_votes(["scannen", "lesenswert", "scannen"])
    assert c.keep and c.state == "konsens_behalten" and c.consensus
    assert c.n_keep == 3 and c.n_votes == 3 and c.agreement == 1.0


def test_n_stimmen_konsens_wegwerfen():
    c = combine_votes(["ignorieren", "ignorieren", "ignorieren"])
    assert not c.keep and c.state == "konsens_wegwerfen" and c.consensus
    assert c.n_keep == 0 and c.n_votes == 3


def test_n_stimmen_dissens_behaelt_und_zaehlt_zustimmung():
    # 1 von 3 will behalten → recall-schützend behalten, geflaggt.
    c = combine_votes(["scannen", "ignorieren", "ignorieren"])
    assert c.keep and c.state == "dissens" and c.flagged
    assert c.n_keep == 1 and c.n_votes == 3
    assert abs(c.agreement - 1 / 3) < 1e-9


def test_n_stimmen_ignoriert_fehlende_stimmen():
    # None/"" zählen nicht; zwei echte Behalten-Stimmen → Konsens behalten.
    c = combine_votes([None, "scannen", "", "lesenswert"])
    assert c.state == "konsens_behalten" and c.n_votes == 2


def test_combine_triage_ist_zwei_stimmen_spezialfall():
    a = combine_triage("scannen", "ignorieren")
    b = combine_votes(["scannen", "ignorieren"])
    assert (a.decision, a.state, a.n_keep, a.n_votes) == (b.decision, b.state, b.n_keep, b.n_votes)
