# devtrace_anchor.py

Anchored two-port comparison of the device-event ring. `devtrace_diff.py` compares over an absolute guest-cycle window, which only works when both ports are at the same guest point. They are not: psx-runtime and psx-beetle take different-length BIOS boot paths (the CD-controller version difference in `KNOWN_DIVERGENCES`), so each side is anchored independently at a named event and compared by per-source ordinal using cycles relative to that side's own anchor.

Shared logic (`query`, `SRC`, `KNOWN_DIVERGENCES`, `by_source`) is imported from `devtrace_diff.py`, not copied.

## Usage

```bash
python tools/devtrace_anchor.py [--native 4370] [--beetle 4380] \
    [--anchor-source sio0] [--anchor-ordinal 0] [--drift 2000000] \
    [--span CYCLES] [--align cdrom ...] [--strict]
```

Both ports need `PSX_DEVTRACE=1` or the rings do not arm, and native needs `PSX_BIOS_HLE=0` or it skips the BIOS boot. Drift is `beetle_rel - native_rel`; positive means Beetle's Nth event fires later than native's. The report is truncated to the common post-anchor span (or `--span`, for reproducible figures).

`--align` runs a difflib alignment over `(source, detail)` and splits the change in cycle offset into cycles across non-equal blocks (extra events on one side) and cycles across equal blocks (same events, different timing). A trailing unmatched run is treated as one port having run longer, not as extra events.

## Ring size and the one-pull rule

- The ring is 1M events (`DEVTRACE_RING_CAP`, `runtime/src/device_trace.c`); `seq` is monotonic since boot.
- `devtrace_dump` writes into a 12 MB response buffer and stops when it fills, which is about 157,700 events. It drops the NEWEST events and only signals it through `emitted` < `count`. The "rolling ~157k window" noted in earlier sessions is this truncation, not the ring size. Server-side fix is tracked separately.
- `pull_all` pages with `cyc_lo`, merges by `seq`, and stops at the first pull's `total`, so the anchor and every figure come from one consistent snapshot of the run. A `seq` gap means the ring wrapped mid-pull and raises `AnchorAgedOut`.
- Anchor ordinals are counted since boot. If the oldest retained `seq` is not 0 the ring has wrapped, and "the first SIO0 event" in the window is not the first since boot; the tool raises `AnchorAgedOut` instead of anchoring on a later event. Do not mix cycles from two separate pulls.

## Worked example (Azure Dreams, SCPH1001)

Native `PSX_BIOS_HLE=0` on 4370 and stock Beetle on 4380, anchored at each side's first SIO0 event (native cycle 421,670,333, Beetle 265,572,476), `--span 2584331764`:

| source | n cnt | b cnt | first >2M drift | max abs drift |
|---|---|---|---|---|
| vblank | 4578 | 4565 | #1223 +2,000,683 | +7,484,337 |
| cdrom (KNOWN) | 9728 | 9495 | #4 +2,033,308 | +60,459,543 |
| dma | 22326 | 21736 | #0 +14,404,375 | +72,434,931 |
| timer2 | 45068 | 45066 | none | +75,670 |
| sio0 | 28598 | 27654 | #11034 +2,006,944 | +132,796,968 |

These match the TASK-006 session 4 figures exactly.
