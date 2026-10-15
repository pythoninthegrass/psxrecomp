#include "cyc_watch_region.h"

#include <assert.h>
#include <stdint.h>

#define A 0x00017FC4u
#define B 0x0001EFFCu
#define OTHER 0x00020000u

int main(void)
{
    CycWatchRegion r;
    uint64_t d = 0;

    /* clean A->B pass records the cycle delta */
    cyc_watch_region_init(&r, A, B, 0);
    assert(cyc_watch_region_step(&r, OTHER, 90, &d) == 0);
    assert(cyc_watch_region_step(&r, A, 100, &d) == 0);
    assert(r.in_region == 1);
    assert(cyc_watch_region_step(&r, B, 160, &d) == 1);
    assert(d == 60);
    assert(r.in_region == 0 && r.abandoned_reentry == 0 && r.abandoned_overrun == 0);

    /* A re-entered before B abandons the first pass and restarts at the new A */
    cyc_watch_region_init(&r, A, B, 0);
    assert(cyc_watch_region_step(&r, A, 100, &d) == 0);
    assert(cyc_watch_region_step(&r, A, 140, &d) == 0);
    assert(r.abandoned_reentry == 1);
    assert(cyc_watch_region_step(&r, B, 150, &d) == 1);
    assert(d == 10);

    /* tail call out of the region: a later unrelated B hit must not pair with A */
    cyc_watch_region_init(&r, A, B, 1000);
    assert(cyc_watch_region_step(&r, A, 100, &d) == 0);
    assert(cyc_watch_region_step(&r, OTHER, 5000, &d) == 0);
    assert(r.abandoned_overrun == 1 && r.in_region == 0);
    assert(cyc_watch_region_step(&r, B, 9000, &d) == 0);
    assert(r.abandoned_overrun == 1);

    /* a B hit that is itself past the bound is abandoned, not recorded */
    cyc_watch_region_init(&r, A, B, 1000);
    assert(cyc_watch_region_step(&r, A, 100, &d) == 0);
    assert(cyc_watch_region_step(&r, B, 2000, &d) == 0);
    assert(r.abandoned_overrun == 1);

    /* pass exactly at the bound still completes */
    cyc_watch_region_init(&r, A, B, 1000);
    assert(cyc_watch_region_step(&r, A, 100, &d) == 0);
    assert(cyc_watch_region_step(&r, B, 1100, &d) == 1);
    assert(d == 1000);

    /* overrun is detected at an observation that is a fresh A, which then opens a new pass */
    cyc_watch_region_init(&r, A, B, 1000);
    assert(cyc_watch_region_step(&r, A, 100, &d) == 0);
    assert(cyc_watch_region_step(&r, A, 5000, &d) == 0);
    assert(r.abandoned_overrun == 1 && r.abandoned_reentry == 0 && r.in_region == 1);

    /* per-pass deltas recorded from native on func_8006388C (A=0x8006388C, B=0x800638A0): pass 4 cost 1556 */
    {
        static const uint64_t recorded[16] = {22, 22, 22, 22, 1556, 22, 22, 22,
                                              22, 22, 22, 22, 22, 22, 22, 22};
        for (int bound = 0; bound <= 500; bound += 500) {
            uint64_t t = 1000, got[16];
            int n = 0;
            cyc_watch_region_init(&r, 0x0006388Cu, 0x000638A0u, (uint64_t)bound);
            for (int i = 0; i < 16; i++) {
                assert(cyc_watch_region_step(&r, 0x0006388Cu, t, &d) == 0);
                t += recorded[i];
                if (cyc_watch_region_step(&r, 0x000638A0u, t, &d)) got[n++] = d;
                t += 40;
            }
            if (bound == 0) {
                assert(n == 16 && got[4] == 1556 && r.abandoned_overrun == 0);
            } else {
                /* the bound is checked at the next observation, so B itself is the late hit */
                assert(n == 15 && r.abandoned_overrun == 1);
                for (int i = 0; i < n; i++) assert(got[i] == 22);
            }
        }
    }
    return 0;
}
