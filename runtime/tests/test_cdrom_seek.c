/*
 * CD seek latency model: travel distance, long-stroke, restart-from-pause.
 *
 * Build/run: ctest -R cdrom_seek_test
 */
#include "cdrom_seek.h"

#include <stdint.h>
#include <stdio.h>

static int failures;

#define CHECK(cond, label) do {                                                \
    if (!(cond)) { fprintf(stderr, "FAIL: %s\n", (label)); failures++; }       \
} while (0)

int main(void) {
    /* Same position settles at the travel floor. */
    CHECK(psx_cd_seek_cycles(1000, 1000, 1, 0, 0) == 20000, "same lba costs the 20000-cycle floor");

    /* A near seek (<= 16 sectors) stays at the floor: quick, no restart cost. */
    CHECK(psx_cd_seek_cycles(1000, 1016, 1, 0, 0) == 20000, "16-sector seek stays at the floor");
    CHECK(psx_cd_seek_cycles(1016, 1000, 1, 0, 0) == 20000, "backward near seek is symmetric");

    /* Travel grows with distance: 1 s per 324000 sectors (72 min * 60 * 75). */
    CHECK(psx_cd_seek_cycles(0, 1000, 1, 0, 0) == 1000 * 33868800LL / 324000, "1000-sector travel");
    CHECK(psx_cd_seek_cycles(0, 2000, 1, 0, 0) > psx_cd_seek_cycles(0, 1000, 1, 0, 0), "travel increases with distance");

    /* Long stroke (>= 2250 sectors) adds 300 ms. */
    CHECK(psx_cd_seek_cycles(0, 2249, 1, 0, 0) == 2249 * 33868800LL / 324000, "2249 sectors has no long-stroke term");
    CHECK(psx_cd_seek_cycles(0, 2250, 1, 0, 0) == 2250 * 33868800LL / 324000 + 33868800LL * 300 / 1000,
          "2250 sectors adds 300 ms");

    /* The reported worst case: LBA 413 -> 87535 (87122 sectors). */
    CHECK(psx_cd_seek_cycles(413, 87535, 1, 0, 0) == 87122 * 33868800LL / 324000 + 33868800LL * 300 / 1000,
          "87122-sector stroke");

    /* Restart from a paused state: 2 x 1237952 at 1x, 1237952 at 2x. */
    CHECK(psx_cd_seek_cycles(1000, 1000, 1, 1, 0) == 20000 + 2 * 1237952, "paused restart at 1x");
    CHECK(psx_cd_seek_cycles(1000, 1000, 1, 1, 1) == 20000 + 1237952, "paused restart at 2x");

    /* The long-stroke term replaces the restart term rather than adding to it. */
    CHECK(psx_cd_seek_cycles(0, 5000, 1, 1, 0) == psx_cd_seek_cycles(0, 5000, 1, 0, 0), "long stroke supersedes pause restart");

    /* Motor off: a one second spin-up, with the head treated as at LBA 0. */
    CHECK(psx_cd_seek_cycles(50000, 1000, 0, 0, 0) == 33868800LL + 1000 * 33868800LL / 324000, "spin-up from stopped");

    /* Near seeks stay far below the previous flat far-seek cost of 1806336 cycles. */
    CHECK(psx_cd_seek_cycles(1000, 1010, 1, 0, 0) < 1806336 / 10, "near seek stays quick");
    CHECK(psx_cd_seek_cycles(413, 87535, 1, 0, 0) > 19000000, "long stroke is an order above the flat model");

    if (failures) return 1;
    puts("cdrom_seek_test: ok");
    return 0;
}
