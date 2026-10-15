/* cyc_watch_region.h — two-anchor REGION state machine shared by psx-runtime
 * (debug_server.c) and psx-beetle (beetle_libretro.cpp) so both backends
 * classify a pass identically. Pure: no I/O, no globals.
 *
 * A pass opens at anchor A and completes at anchor B. A pass is ABANDONED, not
 * recorded, when A is re-entered before B (abandoned_reentry), or when the open
 * pass has outlived the declared max_cycles bound at any later observation
 * (abandoned_overrun; this is the tail-call case, where a later unrelated B hit
 * would otherwise pair with A). max_cycles == 0 disables the bound; then a
 * region that is left and never re-enters A stays open and is only visible as
 * in_region == 1. Observations are dispatch points only, so that is the limit
 * of what can be known. */
#ifndef CYC_WATCH_REGION_H
#define CYC_WATCH_REGION_H

#include <stdint.h>

typedef struct {
    uint32_t anchor_phys;
    uint32_t end_phys;
    uint64_t max_cycles;
    int      in_region;
    uint64_t region_start;
    uint32_t abandoned_reentry;
    uint32_t abandoned_overrun;
} CycWatchRegion;

static inline void cyc_watch_region_init(CycWatchRegion *r, uint32_t anchor_phys,
                                         uint32_t end_phys, uint64_t max_cycles)
{
    r->anchor_phys = anchor_phys;
    r->end_phys = end_phys;
    r->max_cycles = max_cycles;
    r->in_region = 0;
    r->region_start = 0;
    r->abandoned_reentry = 0;
    r->abandoned_overrun = 0;
}

/* Returns 1 and sets *delta when this observation completes a pass. */
static inline int cyc_watch_region_step(CycWatchRegion *r, uint32_t phys,
                                        uint64_t cycle, uint64_t *delta)
{
    if (r->in_region && r->max_cycles != 0 && cycle - r->region_start > r->max_cycles) {
        r->in_region = 0;
        r->abandoned_overrun++;
    }
    if (!r->in_region) {
        if (phys == r->anchor_phys) {
            r->region_start = cycle;
            r->in_region = 1;
        }
        return 0;
    }
    if (phys == r->anchor_phys) {
        r->abandoned_reentry++;
        r->region_start = cycle;
        return 0;
    }
    if (phys == r->end_phys) {
        *delta = cycle - r->region_start;
        r->in_region = 0;
        return 1;
    }
    return 0;
}

#endif
