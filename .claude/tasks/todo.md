# Todo

## Storico completato

**Pre-refactoring** (12 bug fix): GenreDNA, popularity cache, wrapped slides, admin/friends error feedback, TrendTimeline, compound index, first_play_date, artist network threshold, login sync.

**Refactoring API** (Fasi 1-4): RequestDataBundle (13→7 call /wrapped, 5→4 /profile, 6→3 /trends), frontend rendering progressivo (WrappedPage POST/poll, skeleton loading), cache strategy documentata.

**Ottimizzazione Redis** (Fase 5): Lua script atomico 3→1 Redis round-trip, get_window_usage ZCOUNT, EmptyState convention fix (6 componenti).

**Playlist cache + Genre enrichment** (Fasi 6-7): PlaylistMetadata DB cache permanente + polling frontend. Spotify dev mode restituisce genres=[] e popularity=0 per tutti gli artisti → fallback 3 fonti: Spotify → MusicBrainz (43/83 artisti) → Playlist-inferred genres. Singleton cluster nascosti, SVG legend filtrata, disambiguation MusicBrainz, tag blocklist. 493 test.

---

## Prossimi passi

- [ ] Dedup nomi cerchie identici ("Hip Hop / Trap" × 2): usare genere terziario o nome artista top
- [ ] Artisti Ponte / Cerchie: layout gap nella vista Rete (serve scroll lungo per raggiungerle)
- [ ] Playlist inference retry: il warmup Phase 3 si ferma al primo rate limit — aggiungere retry con wait
- [ ] MusicBrainz disambiguation: nomi ambigui (Maz → folk canadese, FISHER → vocal trance)
- [ ] ~34 artisti ancora senza generi: valutare Last.fm API o accettare il limite
- [ ] Test end-to-end Docker: verificare WrappedPage POST/poll con dati reali
