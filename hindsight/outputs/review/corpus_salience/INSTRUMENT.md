# Corpus-salience instrument (frozen 2026-10-14, before the full sample)
- Source: Infini-gram `search_docs`, index v4_dolma-v1_7_llama; each call returns 10 random documents containing the needle,
  displayed as a +-200-token window (max_disp_len 400). Deduplicated by doc_ix; throttled 1 req/s.
- Temporal needle: "Month YYYY" for each of the 240 macro panel months; target 100 windows per month.
- S_T(t): share of windows matching CRISIS_RX = crisis|recession|crash|collapse|meltdown|panic|bailout|depression|turmoil|pandemic|lockdown.
  Secondary S_fin: financial crisis|recession|market crash|stock market|bailout|Lehman|subprime|bear market.
- Spatial needle: region name (New York City, Milan, London, Madrid, Tokyo, Melbourne, Sydney, Delhi, Hong Kong, Singapore); 200 windows each;
  S_P(c): share matching PAND_RX = lockdown|COVID|coronavirus|pandemic|quarantine|stay-at-home|social distancing.
- Analysis: per leaderboard row, Spearman rho of h_t = bearish_D(t) - bearish_M(t) on S_T(t) over all dates and over the 229 dates
  outside the preregistered crisis set; spatial: Spearman of S_P on per-region LAP recall and hit (n = 10).
- Caveat: Dolma is a proxy for vendor corpora. Windows are cached raw (windows.jsonl); vocabulary is applied at analysis time.
