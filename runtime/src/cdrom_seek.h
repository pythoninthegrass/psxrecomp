/* cdrom_seek.h - CD head-travel / spin-up / restart latency, in CPU cycles.
 *
 * Source: the in-tree Beetle oracle, mednafen/psx/cdc.cpp PS_CDC::CalcSeekTime.
 * psx-spx gives no seek-time figures (only "about 1 second" ReadTOC, ~1 s Stop,
 * 1/8 s Reset), so the constants below are Beetle's and are not independently
 * confirmed against hardware.
 *
 *   travel     = |initial - target| sectors * CPU_HZ / (72 min * 60 * 75), i.e.
 *                one second for a full-disc stroke of 324000 sectors, with a
 *                20000-cycle floor.
 *   long stroke >= 2250 sectors adds 300 ms.
 *   restart    when paused (and not a long stroke): 1237952 cycles in 2x mode,
 *                twice that in 1x mode. Beetle itself calls this "EXTREMELY
 *                simplified".
 *   spin-up    motor off: +1 s and the head is taken to be at LBA 0.
 *
 * Beetle adds PSX_GetRandU32(0, 25000) per seek. It is omitted here: the guest
 * cycle ruler must be deterministic, and the mean 12500-cycle term is far below
 * the travel term. */
#ifndef CDROM_SEEK_H
#define CDROM_SEEK_H

#include <stdint.h>
#include <stdlib.h>

#define PSX_CD_CPU_HZ            33868800LL
#define PSX_CD_DISC_SECTORS      (72LL * 60 * 75)
#define PSX_CD_SEEK_FLOOR        20000LL
#define PSX_CD_LONG_STROKE       2250
#define PSX_CD_PAUSE_RESTART_2X  1237952LL

static inline int64_t psx_cd_seek_cycles(int initial_lba, int target_lba, int motor_on,
                                         int paused, int double_speed)
{
    int64_t ret = 0;
    if (!motor_on) {
        initial_lba = 0;
        ret += PSX_CD_CPU_HZ;
    }
    int dist = abs(initial_lba - target_lba);
    int64_t travel = (int64_t)dist * PSX_CD_CPU_HZ / PSX_CD_DISC_SECTORS;
    ret += travel > PSX_CD_SEEK_FLOOR ? travel : PSX_CD_SEEK_FLOOR;
    if (dist >= PSX_CD_LONG_STROKE)
        ret += PSX_CD_CPU_HZ * 300 / 1000;
    else if (paused)
        ret += double_speed ? PSX_CD_PAUSE_RESTART_2X : PSX_CD_PAUSE_RESTART_2X * 2;
    return ret;
}

#endif
