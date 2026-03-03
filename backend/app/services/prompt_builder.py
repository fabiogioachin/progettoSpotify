"""Generatore di prompt strutturati per analisi con Claude AI."""

import json


def build_claude_prompt(
    top_tracks: list[dict],
    features_profile: dict,
    trends: list[dict],
    genres: dict,
    playlist_comparison: list[dict] | None = None,
) -> dict:
    """Costruisce un export strutturato con dati + prompt per Claude."""

    # Sezione dati compatti
    data_section = _build_data_section(top_tracks, features_profile, trends, genres, playlist_comparison)

    # Prompt pre-compilato
    prompt = _build_prompt_text()

    full_export = f"""{data_section}

---

{prompt}"""

    # Stima token approssimativa (1 token ~ 4 caratteri per italiano)
    estimated_tokens = len(full_export) // 4

    return {
        "export_text": full_export,
        "estimated_tokens": estimated_tokens,
        "data_preview": data_section[:500] + "..." if len(data_section) > 500 else data_section,
    }


def _build_data_section(
    top_tracks: list[dict],
    features_profile: dict,
    trends: list[dict],
    genres: dict,
    playlist_comparison: list[dict] | None,
) -> str:
    lines = ["# Dati di Ascolto Spotify — Analisi Personale", ""]

    # Top tracks compatti
    lines.append("## Top 20 Brani (con audio features)")
    lines.append("```json")
    compact_tracks = []
    for t in top_tracks[:20]:
        entry = {
            "nome": t.get("name", ""),
            "artista": t.get("artist", ""),
            "popolarita": t.get("popularity", 0),
        }
        feat = t.get("features", {})
        if feat:
            entry["energia"] = feat.get("energy")
            entry["valence"] = feat.get("valence")
            entry["danceability"] = feat.get("danceability")
            entry["acousticness"] = feat.get("acousticness")
        compact_tracks.append(entry)
    lines.append(json.dumps(compact_tracks, ensure_ascii=False, indent=1))
    lines.append("```")
    lines.append("")

    # Profilo audio medio
    lines.append("## Profilo Audio Medio")
    if features_profile:
        for key, val in features_profile.items():
            label = {
                "energy": "Energia",
                "valence": "Positività (Valence)",
                "danceability": "Ballabilità",
                "acousticness": "Acusticità",
                "instrumentalness": "Strumentalità",
                "liveness": "Dal vivo",
                "speechiness": "Parlato",
                "tempo": "Tempo (BPM)",
            }.get(key, key)
            lines.append(f"- **{label}**: {val}")
    lines.append("")

    # Trend per periodo
    lines.append("## Trend per Periodo")
    for trend in trends:
        lines.append(f"### {trend.get('label', trend.get('period', ''))}")
        feat = trend.get("features", {})
        for key in ["energy", "valence", "danceability"]:
            val = feat.get(key, "N/A")
            lines.append(f"- {key}: {val}")
        lines.append(f"- Genere top: {trend.get('genres', {}).get(next(iter(trend.get('genres', {})), ''), 'N/A') if trend.get('genres') else 'N/A'}")
        lines.append("")

    # Generi
    lines.append("## Distribuzione Generi (Top 10)")
    for genre, pct in list(genres.items())[:10]:
        lines.append(f"- {genre}: {pct}%")
    lines.append("")

    # Confronto playlist (opzionale)
    if playlist_comparison:
        lines.append("## Confronto Playlist")
        for comp in playlist_comparison:
            lines.append(f"### Playlist: {comp.get('playlist_id', 'N/A')}")
            avg = comp.get("averages", {})
            for key, val in avg.items():
                lines.append(f"- {key}: {val}")
            lines.append("")

    return "\n".join(lines)


def _build_prompt_text() -> str:
    return """# Istruzioni per l'Analisi

Sei un esperto di analisi musicale. Analizza i dati di ascolto Spotify sopra e genera un report dettagliato in ITALIANO. Segui questa struttura:

## 1. Profilo d'Ascolto Narrativo
Non elencare numeri: interpreta. Che tipo di ascoltatore emerge da questi dati? Descrivi il gusto musicale come se stessi presentando una persona a qualcuno.

## 2. Trend Detection
Confronta i periodi (ultimo mese vs 6 mesi vs sempre). Il gusto si sta evolvendo? In che direzione? Usa frasi come:
- "Il tuo ascolto si sta spostando verso..."
- "Rispetto ai mesi precedenti..."
- "C'è una tendenza emergente verso..."

## 3. Correlazioni e Pattern
Cosa indicano le combinazioni di features? Esempi:
- Alta energia + bassa valence = intensità emotiva, magari musica catartica
- Alta danceability + alta valence = mood festivo, sociale
- Alta acousticness + bassa energia = fase riflessiva o intima
Trova i pattern specifici nei dati dell'utente.

## 4. Scoperte Nascoste
Ci sono brani nel profilo che si discostano molto dal pattern generale? Cosa potrebbe significare?

## 5. Suggerimenti Personalizzati
Basandoti sul profilo audio, suggerisci:
- 3 generi che l'utente potrebbe apprezzare ma potrebbe non conoscere
- Il "mood ideale" per una playlist personale
- Un'osservazione sorprendente che emerge dai dati

Rispondi in modo discorsivo, evita elenchi puntati dove possibile. Sii specifico con riferimenti ai dati reali dell'utente."""
