/*
 * png_write_file_verified: a success answer means a complete PNG is at the
 * path; every failure names its reason and leaves no partial or temp file.
 *
 * Build/run: ctest -R png_write_verified_test
 */
#include "png_write.h"

#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <direct.h>
#define MKDIR(p) _mkdir(p)
#else
#include <unistd.h>
#define MKDIR(p) mkdir((p), 0755)
#endif

static int failures;
#define CHECK(cond, label) do { if (!(cond)) { fprintf(stderr, "FAIL: %s\n", (label)); failures++; } } while (0)

static long file_size(const char *p) {
    struct stat st;
    return stat(p, &st) == 0 ? (long)st.st_size : -1;
}

int main(void) {
    uint8_t rgb[4 * 3 * 3];
    memset(rgb, 0x7F, sizeof rgb);
    const char *dir = "png_verified_test_dir";
    MKDIR(dir);
    char path[256], tmp[300];
    snprintf(path, sizeof path, "%s/shot.png", dir);
    snprintf(tmp, sizeof tmp, "%s.tmp", path);

    CHECK(png_write_file_verified(path, rgb, 4, 3) == NULL, "write succeeds");
    long first = file_size(path);
    CHECK(first > 8, "file exists with content");
    CHECK(file_size(tmp) < 0, "no temp file left behind");
    FILE *f = fopen(path, "rb");
    unsigned char sig[8] = {0};
    CHECK(f && fread(sig, 1, 8, f) == 8 && memcmp(sig, "\x89PNG\r\n\x1a\n", 8) == 0, "PNG signature");
    if (f) fclose(f);

    CHECK(png_write_file_verified(path, rgb, 4, 3) == NULL, "overwrite succeeds");
    CHECK(file_size(path) == first, "overwrite replaces the file");

    const char *err = png_write_file_verified("png_verified_no_such_dir/x.png", rgb, 4, 3);
    CHECK(err && strstr(err, "cannot open"), "missing directory names the reason");

    char dest_dir[300];
    snprintf(dest_dir, sizeof dest_dir, "%s/is_a_dir.png", dir);
    MKDIR(dest_dir);
    err = png_write_file_verified(dest_dir, rgb, 4, 3);
    CHECK(err != NULL, "destination that cannot be replaced is an error");
    char dest_tmp[320];
    snprintf(dest_tmp, sizeof dest_tmp, "%s.tmp", dest_dir);
    CHECK(file_size(dest_tmp) < 0, "failed write leaves no temp file");

    remove(path);
    rmdir(dest_dir);
    rmdir(dir);
    if (failures) return 1;
    puts("png_write_verified_test: ok");
    return 0;
}
