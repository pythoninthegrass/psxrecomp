/* device_trace_note_raise records only I_STAT rising edges, matching Beetle's
 * IRQ_Assert edge semantics. Build/run: ctest -R device_trace_edge_test */
#include "device_trace.h"

#include <stdio.h>

uint32_t parity_host_frame(void) { return 0; }
uint64_t parity_host_cycle(void) { return 0; }

static int failures;

#define EXPECT(total, label) do {                                             \
    if (device_trace_total() != (uint64_t)(total)) {                          \
        fprintf(stderr, "FAIL: %s (expected %d events, got %llu)\n", (label), \
                (int)(total), (unsigned long long)device_trace_total());      \
        failures++;                                                           \
    }                                                                         \
} while (0)

int main(void) {
    device_trace_reset();
    device_trace_arm(1);

    device_trace_note_raise(0u, DEV_IRQ_VBLANK, 0);
    EXPECT(1, "raise with bit clear is recorded");

    device_trace_note_raise(1u << DEV_IRQ_VBLANK, DEV_IRQ_VBLANK, 0);
    EXPECT(1, "raise with bit already pending is not an edge");

    device_trace_note_raise(1u << DEV_IRQ_VBLANK, DEV_IRQ_CDROM, 3);
    EXPECT(2, "other pending bits do not suppress a different source");

    device_trace_reset();
    device_trace_note_at(DEV_IRQ_SIO0, 0, 123456u);
    device_trace_note_at(DEV_IRQ_SIO0, 0, 123999u);
    DevEvent rows[2];
    if (device_trace_get(rows, 2) != 2 || rows[0].cycle != 123456u || rows[1].cycle != 123999u) {
        fprintf(stderr, "FAIL: device_trace_note_at must stamp the supplied cycle\n");
        failures++;
    }

    if (failures) {
        fprintf(stderr, "FAILED (%d)\n", failures);
        return 1;
    }
    puts("ALL PASS");
    return 0;
}
