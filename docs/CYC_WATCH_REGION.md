# cyc_watch region mode

`cyc_watch` with an `end` anchor records, per pass, the guest cycles between a start anchor A and an end anchor B. The state machine is `runtime/include/cyc_watch_region.h`, shared by psx-runtime (`debug_server.c`) and psx-beetle (`beetle_libretro.cpp`) so both classify a pass identically. Driver: `tools/cycle_compare.py <A> --end <B>`, or `PSX_CYC_WATCH=<A>-<B>` with `PSX_CYC_WATCH_N=<hits>` in each process environment plus `--no-arm`.

Observations are dispatch points only on native (function entries, block leaders via `debug_server_cyc_observe`, dirty blocks) and every instruction on Beetle, so anchor block leaders on both.

## Abandoned passes

A pass is abandoned, counted and not recorded, when:

- A is re-entered before B (`abandoned_reentry`); the new A starts a fresh pass.
- The open pass is older than the declared bound at any later observation (`abandoned_overrun`). Arm with `max_cycles` (`cycle_compare.py --max-cycles N`). This is the tail-call case: a function that leaves the region through a jump never reaches B, and a later unrelated B hit would otherwise pair with A. The bound also abandons any legitimately long pass, for example one that ran an exception handler.

`cyc_watch_dump` returns `in_region`, `abandoned`, `abandoned_reentry`, `abandoned_overrun` on both ports; `cycle_compare.py` prints a warning for each port with abandoned passes or a pass still open, and for a port that does not report the fields.

Unknown, not guessed: with `max_cycles` = 0 (always the case for `PSX_CYC_WATCH` env arming), a region left via a tail call that never re-enters A cannot be told apart from a long pass; it shows only as `in_region` = 1 at dump time.

## Worked example: `func_80045310` (Azure Dreams, SLUS_006.14)

A leaf: it makes no calls and ends in `jr ra`. Both arms of its only branch reach B, so no control flow leaves the region A=`0x80045310` to B=`0x80045334`.

```text
80045310 LUI   v0, 0x8008
80045314 ADDIU a1, v0, 5240
80045318 LUI   v0, 0x8008
8004531C LW    v1, 12640(v0)
80045320 LUI   v0, 0x801D
80045324 ADDIU v0, v0, -25024
80045328 BEQ   v1, v0, 0x80045334
8004532C NOP
80045330 ADDIU a1, a1, 4          ; block leader, skipped when the branch is taken
80045334 LW    v0, 0(a1)          ; B, block leader reached on both arms
80045338 JR    ra
8004533C SLTU  v0, v0, a0
```

Measured with `PSX_CYC_WATCH=0x80045310-0x80045334 PSX_CYC_WATCH_N=32` on native (`PSX_BIOS_HLE=0`, port 4370) and stock Beetle (port 4380), from power-on, 32 passes each. Neither port reported an abandoned pass:

| arm | native cycles/pass | Beetle cycles/pass |
|---|---|---|
| shorter | 27 | 27 |
| longer | 35 | 35 |

Both ports show the same two values, repeating three passes at a time, shifted against each other by one phase, so a hit-index diff reads alternating +8/-8 although the per-arm cost is identical. Compare the sorted per-pass values, not the hit index. Which arm is the 27 and which the 35, and what accounts for the 8-cycle difference for one `ADDIU`, was not determined. This region is at parity today: use it as the regression target for each TASK-016 component (a component that moves either figure on one port only has broken parity here).

## Second example: a region the branch can leave

`func_8006388C` A=`0x8006388C`, B=`0x800638A0` (the fall-through block after its `beq`). The taken branch leaves the region, so most attempts are abandoned. Measured from power-on, 16 completed passes each: native 32,956 and Beetle 43,924 passes abandoned by A re-entry, completed passes cost 22 cycles on both ports except native pass 4 (1,556 cycles) and Beetle pass 15 (15 cycles). The cause of those two outliers was not determined. A `max_cycles` bound below 1,556 would abandon native pass 4 (not run).
