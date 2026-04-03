# Todo

## Storico completato

**Pre-refactoring** (12 bug fix): GenreDNA, popularity cache, wrapped slides, admin/friends error feedback, TrendTimeline, compound index, first_play_date, artist network threshold, login sync.

**Refactoring API** (Fasi 1-4): RequestDataBundle (13→7 call /wrapped, 5→4 /profile, 6→3 /trends), frontend rendering progressivo (WrappedPage POST/poll, skeleton loading), cache strategy documentata.

**Ottimizzazione Redis + Playlist + Genre** (Fasi 5-7): Lua script atomico 3→1 Redis round-trip. PlaylistMetadata DB cache permanente + polling frontend. Spotify dev mode genres=[] → fallback Spotify → MusicBrainz (43/83 artisti) → Playlist-inferred. Singleton cluster nascosti, SVG legend filtrata, MusicBrainz disambiguation. 518 test.

**Budget + Analytics + Polish** (Sessione 2026-04-03): Budget per-user dinamico (1 user = 100% tier). Playlist analytics ordine crescente + retry paziente. WrappedPage crash fix. Cluster dedup cascading 4-pass. Obsidian KG documentazione (6 note).

---

## Fix/Refactor in corso

- [ ] B1: Dashboard — generi: donut chart al posto del treemap (phonk 79% nascondeva gli altri generi)
- [ ] B2: Dashboard — unificare selettore temporale (7gg/30gg/3M/Tutto per tutta la pagina, mapping a Spotify time_range)
- [ ] B3: Dashboard — ThrottleBanner: mostrare budget effettivo per-user, drain progressivo della barra, auto-hide
- [ ] C1: Ecosistema Artisti — fusione grafi KG + Rete con zoom semantico (KG overview, zoom-in rivela connessioni)

---

## Sviluppo futuro (PERSISTENTE)

### Discovery page rebuild
- Scoperte recenti: aggiungere contesto (genere, mood, trend, first_play_date, info tracce)
- Sezioni bloccate da dev mode: mood scatter, genre treemap, outliers → valutare librosa-only
- Nuova musica: API Recommendations deprecata → content-based filtering da DB, Last.fm similar, nuove uscite
- Playlist pubbliche come fonte di scoperta
- Trend analysis dai dati DB accumulati

### Profile page enhancement
- Confronto periodi (questo mese vs precedente) con trend indicators su KPI cards
- Confronto con amici
- Metriche di fedeltà artista (dati presenti, non esposti)

### Last.fm API integration
- Quarto fallback generi: Spotify → MusicBrainz → Playlist → Last.fm
- API key gratuita, `artist.gettoptags`, 5 req/s, copertura underground superiore
- Target: ridurre i 16 artisti senza generi
