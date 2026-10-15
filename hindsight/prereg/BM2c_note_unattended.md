# BM-2c note: unattended execution of the manual-gate rungs (pre-run, 2026-09-14 02:05)

The prereg (afa19e6d) and the B-gate note require manual smoke inspection before
the full run for C, B0 and B1. The operator's machine may lose connectivity
overnight, so the server-side chain applies the automatic gate (>= 6 of 8 smoke
cells schema-valid) to these rungs as a pre-screen and proceeds to the full run
unattended. The manual inspection still happens — post hoc, on the archived
smoke cells, before any number from that rung is used; a rung whose smoke fails
manual inspection is discarded in full (GPU time is the only cost). Data
collection, estimands, gates and readings are unchanged. Recorded before any
call on C or ladder B.
