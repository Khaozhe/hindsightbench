# Extended-vocabulary masked-arm audit (POST-FREEZE EXPLORATORY, 2026-07-24)

Review objection: paper's crisis-node zero-instance claim used only 4 strings.
Extended vocabulary (20 terms, case-insensitive word-boundary regex, all string
fields of each sketch):

```
financial crisis, global financial crisis, gfc, lehman, bear stearns, subprime, bailout, tarp, credit crunch, mortgage crisis, housing crash, great recession, quantitative easing, covid, pandemic, lockdown, coronavirus, svb, silicon valley bank, stimulus
```

Crisis nodes: 2008-09-15, 2008-10-15, 2008-11-15, 2008-12-15, 2009-01-15, 2009-02-15, 2020-03-15, 2020-04-15, 2022-06-15, 2022-09-15, 2022-10-15

## Corpus: fm1_flash_M_all_reps

- files scanned: 720
- sketches scanned: 5760 (per rep: {'rep1': 1920, 'rep2': 1920, 'rep3': 1920})
- crisis-node hits (any term): 0

| term | sketches w/ hit (word-boundary) | occurrences | sketches w/ hit (substring) |
|---|---|---|---|
| credit crunch | 1 | 1 | 1 |
| quantitative easing | 1 | 1 | 1 |
| stimulus | 17 | 18 | 17 |

### Crisis-node hits: NONE

### Examples (up to 5)
- rep1 2009-08-15 [stimulus] "accommodative monetary policies or provides room for stimulus , which supports asset prices by lowering"
- rep1 2009-10-15 [stimulus] "as a 'liquidity trap' rather than a stimulus . 2009-10-15"
- rep1 2011-12-15 [stimulus] "a significant output gap and aggressive monetary stimulus , which creates an environment conducive to"
- rep1 2012-11-15 [stimulus] "forward returns due to lack of further stimulus . - FEDFUNDS FEDFUNDS < 0.2% series:FEDFUNDS"
- rep1 2013-02-15 [stimulus] "weakness (e.g., high unemployment) suggests aggressive monetary stimulus intended to support recovery, which can eventually"

## Corpus: kt1_masked_nodes

- files scanned: 240
- sketches scanned: 1920 (per rep: {'kt1': 1920})
- crisis-node hits (any term): 0

| term | sketches w/ hit (word-boundary) | occurrences | sketches w/ hit (substring) |
|---|---|---|---|
| stimulus | 7 | 8 | 7 |

### Crisis-node hits: NONE

### Examples (up to 5)
- kt1 2009-08-15 [stimulus] "accommodative monetary policies or provides room for stimulus , which supports asset prices by lowering"
- kt1 2009-10-15 [stimulus] "as a 'liquidity trap' rather than a stimulus . 2009-10-15"
- kt1 2011-12-15 [stimulus] "a significant output gap and aggressive monetary stimulus , which creates an environment conducive to"
- kt1 2012-11-15 [stimulus] "forward returns due to lack of further stimulus . - FEDFUNDS FEDFUNDS < 0.2% series:FEDFUNDS"
- kt1 2013-02-15 [stimulus] "weakness (e.g., high unemployment) suggests aggressive monetary stimulus intended to support recovery, which can eventually"

