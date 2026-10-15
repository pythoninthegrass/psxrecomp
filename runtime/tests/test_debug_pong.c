/*
 * The io-thread ping fast path answers with the frame and guest cycle, the
 * same fields psx-beetle's ping carries, so one poller serves both ports.
 *
 * Build/run: ctest -R debug_pong_test
 */
#include "debug_pong.h"

#include <stdio.h>
#include <string.h>

int main(void) {
    char buf[256];
    int n = debug_format_pong(buf, sizeof buf, 1234ull, 5678901234ull);
    const char *want = "{\"id\":0,\"ok\":true,\"pong\":true,\"io_thread\":true,"
                       "\"frame\":1234,\"guest_cycles\":5678901234}\n";
    if (n != (int)strlen(want) || strcmp(buf, want) != 0) {
        fprintf(stderr, "FAIL: pong line was %s", buf);
        return 1;
    }
    if (debug_format_pong(buf, 16, 1ull, 1ull) != -1) {
        fprintf(stderr, "FAIL: truncated pong must report failure\n");
        return 1;
    }
    puts("debug_pong_test: ok");
    return 0;
}
