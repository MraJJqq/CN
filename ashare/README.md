# CN A-share exclusive modules

This directory is the A-share-specific runtime, separate from the copied V6 presentation system.

## Fixed boundaries
- Universe: exactly 500 entries from ashare/data/cn500.csv; no runtime constituent rotation or dynamic replacement.
- Reject duplicate codes and names containing ST, *ST, 退, or 退市.
- Market data: Tencent Securities daily K-lines, QFQ (前复权), up to 10 years; request history in bounded date segments and retain a local cache.
- Signal timeframe: daily only. Never form a signal from an unfinished intraday candle.
- Vegas EMA periods: 12, 144, 169, 576, 676 only.
- A wick overlapping either EMA144/169 or EMA576/676 zone starts an observation. A later daily close crossing EMA12 confirms; the touch candle itself cannot confirm.
- Publish only after every member of the fixed 500-stock pool passes validation and the scan data date is consistent. A partial scan must not replace the last good publication.
- Beijing close scan: weekdays at 15:35 China time (07:35 UTC); manual workflow dispatch is supported.
- Intraday refresh is for displayed K-lines only and must not generate signals.

## Required input
ashare/data/cn500.csv must contain exactly 500 fixed rows with columns code,name. The file is intentionally not fabricated: the fixed approved constituent list must be supplied before the scan can be enabled.

## Runtime
Python 3.11+, standard library only. Secrets are not stored in this repository. Bark delivery is enabled only when BARK_KEY is configured.

## Outputs
- public/data/ashare-signals.json: current published signal payload.
- public/data/ashare-diagnostics.json: scan diagnostics and per-symbol status.
- data/cache/: cached Tencent QFQ daily bars.

The workflow must fail closed on missing/invalid universe, stale or mixed-date data, or any symbol failure.