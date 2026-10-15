/* debug_pong.h - the lock-free ping reply the debug server's I/O thread sends
 * while the emu thread may be busy. Carries the frame and guest cycle like
 * psx-beetle's ping so a single poller works against both ports. */
#ifndef DEBUG_PONG_H
#define DEBUG_PONG_H

#include <stdint.h>
#include <stdio.h>

/* Returns the length written, or -1 when the line does not fit. */
static inline int debug_format_pong(char *buf, size_t cap, uint64_t frame, uint64_t guest_cycles)
{
    int n = snprintf(buf, cap,
                     "{\"id\":0,\"ok\":true,\"pong\":true,\"io_thread\":true,"
                     "\"frame\":%llu,\"guest_cycles\":%llu}\n",
                     (unsigned long long)frame, (unsigned long long)guest_cycles);
    return (n < 0 || (size_t)n >= cap) ? -1 : n;
}

#endif
