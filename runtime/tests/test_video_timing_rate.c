/*
 * The frame periods follow the real vertical rates (psx-spx "GPU Timings":
 * NTSC non-interlaced 59.826 Hz, PAL non-interlaced 49.761 Hz), not round
 * 60 / 50 Hz.
 *
 * Build/run: ctest -R video_timing_rate_test
 */
#include "psx_video_timing.h"

#include <stdio.h>
#include <stdlib.h>

static int failures;
#define CHECK(cond, label) do { if (!(cond)) { fprintf(stderr, "FAIL: %s\n", (label)); failures++; } } while (0)

int main(void) {
    /* 33,868,800 Hz / 59.826 Hz = 566,121.75 cycles; the rate is given to 3
     * decimals, so the period is good to about +-5 cycles. */
    long ntsc = (long)PSX_VBLANK_CYCLES_NTSC;
    CHECK(labs(ntsc - 566122L) <= 2, "NTSC frame period is 33.8688 MHz / 59.826 Hz");
    long pal = (long)PSX_VBLANK_CYCLES_PAL;
    CHECK(labs(pal - 680629L) <= 2, "PAL frame period is 33.8688 MHz / 49.761 Hz");

    CHECK(PSX_VBLANK_CYCLES_NTSC != 564480u, "NTSC period is not the round 60 Hz value");
    CHECK(PSX_VBLANK_CYCLES_PAL != 677376u, "PAL period is not the round 50 Hz value");

    /* HBlank clock: whole cycles per line, truncated; the remainder is the
     * cycles a frame has beyond lines * hblank. */
    CHECK(PSX_HBLANK_CYCLES_NTSC == PSX_VBLANK_CYCLES_NTSC / PSX_LINES_PER_FRAME_NTSC, "NTSC hblank derives from the frame period");
    CHECK(PSX_HBLANK_CYCLES_NTSC * PSX_LINES_PER_FRAME_NTSC <= PSX_VBLANK_CYCLES_NTSC, "NTSC lines never exceed the frame");
    CHECK(PSX_VBLANK_CYCLES_NTSC - PSX_HBLANK_CYCLES_NTSC * PSX_LINES_PER_FRAME_NTSC < PSX_LINES_PER_FRAME_NTSC, "NTSC truncation loses under one cycle per line");
    CHECK(PSX_VBLANK_CYCLES_PAL - PSX_HBLANK_CYCLES_PAL * PSX_LINES_PER_FRAME_PAL < PSX_LINES_PER_FRAME_PAL, "PAL truncation loses under one cycle per line");

    if (failures) return 1;
    puts("video_timing_rate_test: ok");
    return 0;
}
