"""Single choke-point for all user-visible vocabulary (German UI labels).

Rule: no raw DB field value, file name, or internal identifier may reach
a template unmapped. Domain language only — never implementation language.
"""

VERDICT_LABEL = {
    "pflichtlektuere": "Pflichtlektüre",
    "lesenswert": "Lesenswert",
    "scannen": "Scannen",
    "ignorieren": "Ignorieren",
}

RELATION_LABEL = {
    "erweitert": "erweitert",
    "widerspricht": "widerspricht",
    "parallelisiert": "parallel",
    "importiert": "Import",
    "tangential": "tangential",
}

# How an article entered the candidate set (shown as "Gefunden über: …").
# Every value that actually occurs in articles.selection_mode must be mapped —
# an unmapped value would leak a raw English enum into the UI.
SELECTION_MODE_LABEL = {
    "screening": "automatische Vorprüfung",
    "citation": "zitiert dein Werk",
    "similarity": "thematische Ähnlichkeit",
    "complementarity": "thematische Ergänzung zu deinem Werk",
    "mixed": "mehrere Signale",
    "trigger": "beobachtete:r Autor:in",
    "own_coupling": "geteilte Referenzen mit deinem Werk",
    "adversarial": "Signal für mögliche blinde Flecken",
}

DISCOURSE_INDICATOR_LABEL = {
    "starker_indikator": "starkes Signal",
    "schwacher_indikator": "schwaches Signal",
    "kein_indikator": "kein Signal",
}

# Signal-group slugs mirror the active research projects (projects.json).
# Shown as discourse motif groups and in the article "Gefunden über:" line.
SIGNAL_GROUP_LABEL = {
    "ai4artsed": "AI4ArtsEd",
    "cultural_resilience": "Cultural Resilience",
    "metakubi": "MetaKuBi",
    "comearts": "ComeArts",
    "diaes_kubi": "DiäS-KuBi",
}


# Haltung eines Werks zu einer Bezugsquelle (Fallgestalt-Kanten). Die internen
# Werte sind das englische Relations-Vokabular des Positionierungs-Passes —
# hier in die Sprache übersetzt, in der über Texte gesprochen wird.
STANCE_LABEL = {
    "affirms": "stützt sich auf",
    "extends": "führt weiter",
    "contrasts": "setzt sich ab",
    "reserves": "mit Vorbehalt",
    "rejects": "weist zurück",
    "coins": "prägt Begriff",
    "trajectory": "eigene Linie",
}

# Knotenarten der Fallgestalt / Profilform.
NODE_TYPE_LABEL = {
    "position": "Selbstverortung",
    "source": "Bezugsquelle",
    "term": "eigener Begriff",
}


def humanize_key(value: str | None) -> str:
    """Fallback: turn an internal snake_case key into display text."""
    return (value or "").replace("_", " ")


def selection_mode_label(value: str | None) -> str:
    return SELECTION_MODE_LABEL.get(value or "", humanize_key(value))


def discourse_indicator_label(value: str | None) -> str:
    return DISCOURSE_INDICATOR_LABEL.get(value or "", humanize_key(value))


def signal_group_label(value: str | None) -> str:
    return SIGNAL_GROUP_LABEL.get(value or "", humanize_key(value))


def stance_label(value: str | None) -> str:
    return STANCE_LABEL.get(value or "", humanize_key(value))


def node_type_label(value: str | None) -> str:
    return NODE_TYPE_LABEL.get(value or "", humanize_key(value))
