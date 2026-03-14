"""Servizio per il calcolo dell'archetipo musicale dell'utente."""

import logging

logger = logging.getLogger(__name__)

ARCHETYPES = {
    "cercatore_nicchia": {
        "name": "Cercatore di Nicchia",
        "emoji": "\ud83d\udd0d",
        "description": (
            "Il tuo gusto musicale è unico e variegato. Ami esplorare generi nascosti "
            "e artisti underground, costruendo una libreria musicale eclettica e personale."
        ),
        "traits": ["Curioso", "Eclettico", "Indipendente"],
    },
    "fedelissimo": {
        "name": "Fedelissimo",
        "emoji": "\ud83d\udc8e",
        "description": (
            "Sai cosa ti piace e non hai paura di ammetterlo. I tuoi artisti preferiti "
            "sono gemme nascoste che ascolti con dedizione e passione."
        ),
        "traits": ["Leale", "Appassionato", "Selettivo"],
    },
    "esploratore": {
        "name": "Esploratore",
        "emoji": "\ud83e\udded",
        "description": (
            "La tua playlist \u00e8 un viaggio intorno al mondo musicale. Salti tra generi "
            "con facilit\u00e0, sempre alla ricerca del prossimo sound che ti far\u00e0 vibrare."
        ),
        "traits": ["Avventuroso", "Versatile", "Aperto"],
    },
    "mainstream_maven": {
        "name": "Mainstream Maven",
        "emoji": "\u2b50",
        "description": (
            "Hai il polso della musica del momento. Sai sempre quali sono i brani pi\u00f9 "
            "caldi e i trend musicali, con un gusto che risuona con milioni di ascoltatori."
        ),
        "traits": ["Connesso", "Trendy", "Sociale"],
    },
}


def compute_archetype(metrics: dict) -> dict:
    """Determina l'archetipo musicale basato sulle metriche del profilo.

    Quadrant mapping:
    - obscurity >= 50 AND diversity >= 50 -> Cercatore di Nicchia
    - obscurity >= 50 AND diversity < 50  -> Fedelissimo
    - obscurity < 50  AND diversity >= 50 -> Esploratore
    - obscurity < 50  AND diversity < 50  -> Mainstream Maven

    Loyalty modifier: loyalty > 70 biases toward Fedelissimo.
    """
    obscurity = metrics.get("obscurity_score", 0)
    diversity = metrics.get("genre_diversity_index", 0)
    loyalty = metrics.get("artist_loyalty_score", 0)

    # Base quadrant
    if obscurity >= 50 and diversity >= 50:
        archetype_key = "cercatore_nicchia"
    elif obscurity >= 50 and diversity < 50:
        archetype_key = "fedelissimo"
    elif obscurity < 50 and diversity >= 50:
        archetype_key = "esploratore"
    else:
        archetype_key = "mainstream_maven"

    # Loyalty modifier — only override near boundaries, not when quadrant is clear
    if loyalty > 70 and obscurity < 55 and diversity < 55:
        archetype_key = "fedelissimo"

    archetype = ARCHETYPES[archetype_key]
    return {
        "archetype": archetype["name"],
        "emoji": archetype["emoji"],
        "description": archetype["description"],
        "traits": archetype["traits"],
        "scores": {
            "obscurity": obscurity,
            "diversity": diversity,
            "loyalty": loyalty,
        },
    }
