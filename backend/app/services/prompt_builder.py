"""Generatore di prompt strutturati per analisi con Claude AI."""

import json


def build_claude_prompt(
    top_tracks: list[dict],
    features_profile: dict,
    trends: list[dict],
    genres: dict,
    playlist_comparison: list[dict] | None = None,
    taste_evolution: dict | None = None,
    artist_network: dict | None = None,
    temporal_patterns: dict | None = None,
) -> dict:
    """Costruisce un export strutturato con dati + prompt per Claude."""

    # Sezione dati compatti
    data_section = _build_data_section(
        top_tracks, features_profile, trends, genres, playlist_comparison,
        taste_evolution, artist_network, temporal_patterns,
    )

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
    taste_evolution: dict | None = None,
    artist_network: dict | None = None,
    temporal_patterns: dict | None = None,
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

    # Evoluzione gusto (opzionale)
    if taste_evolution:
        lines.append("## Evoluzione Gusto")
        artists = taste_evolution.get("artists", {})
        rising = artists.get("rising", [])
        loyal = artists.get("loyal", [])
        falling = artists.get("falling", [])
        if rising:
            lines.append(f"- **Rising**: {', '.join(a.get('name', '') for a in rising[:10])}")
        if loyal:
            lines.append(f"- **Loyal**: {', '.join(a.get('name', '') for a in loyal[:10])}")
        if falling:
            lines.append(f"- **Falling**: {', '.join(a.get('name', '') for a in falling[:10])}")
        metrics = taste_evolution.get("metrics", {})
        if metrics:
            lines.append(f"- **Loyalty Score**: {metrics.get('loyalty_score', 'N/A')}%")
            lines.append(f"- **Turnover Rate**: {metrics.get('turnover_rate', 'N/A')}%")
        lines.append("")

    # Ecosistema artisti (opzionale)
    if artist_network:
        lines.append("## Ecosistema Artisti")
        clusters = artist_network.get("clusters", [])
        for i, cluster in enumerate(clusters[:5]):
            artist_names = [a.get("name", "") for a in cluster.get("artists", [])[:8]]
            lines.append(f"- **Cluster {i + 1}**: {', '.join(artist_names)}")
        bridges = artist_network.get("bridge_artists", [])
        if bridges:
            bridge_strs = [f"{b.get('name', '')} (score: {b.get('score', 0)})" for b in bridges[:5]]
            lines.append(f"- **Bridge Artists**: {', '.join(bridge_strs)}")
        lines.append(f"- **Total Nodes**: {artist_network.get('total_nodes', 'N/A')}")
        lines.append(f"- **Cluster Count**: {artist_network.get('cluster_count', 'N/A')}")
        lines.append("")

    # Pattern temporali (opzionale)
    if temporal_patterns:
        lines.append("## Pattern Temporali")
        peak_hours = temporal_patterns.get("peak_hours", [])
        if peak_hours:
            lines.append(f"- **Ore di Punta**: {', '.join(str(h) for h in peak_hours[:5])}")
        lines.append(f"- **Max Streak**: {temporal_patterns.get('max_streak', 'N/A')} giorni")
        lines.append(f"- **Weekday %**: {temporal_patterns.get('weekday_pct', 'N/A')}%")
        avg_session = temporal_patterns.get("avg_session_duration", "N/A")
        lines.append(f"- **Durata Media Sessione**: {avg_session} min")
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

## 6. Analisi Ecosistema Artisti
Se disponibili i dati dell'ecosistema artisti:
- Analizza i bridge artists per suggerire zone musicali inesplorate che collegano i cluster di ascolto
- Identifica quali cluster rappresentano nicchie consolidate e quali sono in espansione

## 7. Playlist Contestuali
Se disponibili i pattern temporali:
- Suggerisci playlist contestuali basate sulle abitudini temporali (mattina, sera, weekend)
- Usa le ore di punta e la percentuale weekday/weekend per personalizzare i suggerimenti

## 8. Previsione Scoperte
Se disponibili i dati di evoluzione del gusto:
- Identifica i trend nell'evoluzione del gusto musicale (artisti rising vs falling)
- Predici le prossime scoperte musicali basandoti sulla traiettoria attuale
- Usa loyalty score e turnover rate per capire quanto l'utente sia aperto a nuove scoperte

Rispondi in modo discorsivo, evita elenchi puntati dove possibile. Sii specifico con riferimenti ai dati reali dell'utente."""
