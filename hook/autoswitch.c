/*
 * 커뮤니티 캠페인 번역 자동 전환 (nwn_korean_hook.c 에 #include 되어 한 번역 단위로 빌드된다)
 *
 * 원리 (2026-10-17 실험으로 확인):
 *   - 게임은 문서\development 의 '파일 이름 목록'을 시작할 때 정하고, 내용은 열 때마다 읽는다.
 *     지우면 모듈 안의 원본으로 돌아가고 다시 넣으면 다시 읽는다.
 *   - 게임은 캠페인을 열 때 로그(문서\logs\nwclientLog*.txt)에 "Loading Module: <manifest 해시>" 를 남긴다.
 *   => 시작할 때(엔진이 폴더를 읽기 전) 모든 캠페인의 파일 이름을 하드링크로 깔아 두고,
 *      로그에서 캠페인이 열리는 것을 보면 그 캠페인의 번역본만 남기고 나머지 이름은 지운다.
 *      번역본에 없는 모듈(공식 캠페인 등)이면 전부 지운다. 종료할 때 전부 지운다.
 *
 * 설정 파일: 게임 실행 폴더(bin\win32)의 nwn_ko_autoswitch.txt (UTF-8, 설치 프로그램이 만든다). 없거나 enabled=0 이면 아무것도 안 한다.
 *   enabled=1
 *   dev=<문서\development 절대 경로>
 *   lib=<문서\ko_campaigns 절대 경로>
 *   logs=<문서\logs 절대 경로>
 *   map<TAB><manifest 해시><TAB><캠페인 폴더 이름>        (캠페인마다 한 줄)
 * 번역본: <lib>\<캠페인 폴더 이름>\*  (설치 프로그램이 만든 번역된 게임 파일들, _complete.json 은 제외)
 * 비정상 종료로 남은 파일은 다음 실행 때 상태 파일(<lib>\_dll_seed.txt)을 보고 먼저 지운다.
 */

#define AS_MAX_SLUG 64
#define AS_PATH 1024

typedef struct {
    wchar_t dev[AS_PATH], lib[AS_PATH], logs[AS_PATH];
    int nslug;
    wchar_t slug[AS_MAX_SLUG][128];
    char sha[AS_MAX_SLUG][48];
    int nname;                 /* 합집합 이름 수 */
    wchar_t** name;            /* 정렬된 소문자 이름 */
    unsigned char* has;        /* has[s * nname + i] */
    signed char* cur;          /* cur[i] = 현재 연결된 캠페인 번호, -1 = 없음 */
    int nskip;                 /* 깔지 않을 이름 수(공식 모듈·hak 의 리소스 이름과 겹치는 것) */
    wchar_t** skip;            /* 정렬된 소문자 이름 */
    int enabled;
    volatile LONG stop;
    HANDLE thread;
} AutoSwitch;

static AutoSwitch as_g;

static wchar_t as_lower(wchar_t c) { return (c >= L'A' && c <= L'Z') ? (wchar_t)(c + 32) : c; }

static int as_cmp(const void* a, const void* b) {
    return wcscmp(*(wchar_t* const*)a, *(wchar_t* const*)b);
}

static void as_utf8_to_w(const char* s, wchar_t* out, int cap) {
    int n = MultiByteToWideChar(CP_UTF8, 0, s, -1, out, cap);
    if (n <= 0) out[0] = 0;
}

static void as_trim(char* s) {
    size_t n = strlen(s);
    while (n && (s[n - 1] == '\r' || s[n - 1] == '\n' || s[n - 1] == ' ')) s[--n] = 0;
}

static int as_load_config(void) {
    FILE* f = fopen("nwn_ko_autoswitch.txt", "rb");
    if (!f) return 0;
    char line[2048];
    memset(&as_g, 0, sizeof(as_g));
    while (fgets(line, sizeof(line), f)) {
        as_trim(line);
        if (!strncmp(line, "enabled=", 8)) as_g.enabled = atoi(line + 8);
        else if (!strncmp(line, "dev=", 4)) as_utf8_to_w(line + 4, as_g.dev, AS_PATH);
        else if (!strncmp(line, "lib=", 4)) as_utf8_to_w(line + 4, as_g.lib, AS_PATH);
        else if (!strncmp(line, "logs=", 5)) as_utf8_to_w(line + 5, as_g.logs, AS_PATH);
        else if (!strncmp(line, "map\t", 4) && as_g.nslug < AS_MAX_SLUG) {
            char* sha = line + 4;
            char* tab = strchr(sha, '\t');
            if (!tab) continue;
            *tab = 0;
            strncpy(as_g.sha[as_g.nslug], sha, 47);
            as_utf8_to_w(tab + 1, as_g.slug[as_g.nslug], 128);
            as_g.nslug++;
        }
    }
    fclose(f);
    /* 공식 모듈과 이름이 겹치는 리소스 목록(한 줄에 하나, UTF-8). 이 이름이 development 에 있으면 엔진이
     * 공식 모듈 자신의 같은 이름 리소스 대신 그 파일을 찾다가 모듈 로드에 실패한다. 없으면 아무것도 안 한다. */
    FILE* sf = fopen("nwn_ko_autoswitch_skip.txt", "rb");
    if (sf) {
        int cap = 1024;
        as_g.skip = (wchar_t**)malloc(cap * sizeof(wchar_t*));
        while (fgets(line, sizeof(line), sf)) {
            as_trim(line);
            if (!line[0]) continue;
            if (as_g.nskip == cap) { cap *= 2; as_g.skip = (wchar_t**)realloc(as_g.skip, cap * sizeof(wchar_t*)); }
            wchar_t w[128];
            as_utf8_to_w(line, w, 128);
            for (wchar_t* p = w; *p; p++) *p = as_lower(*p);
            as_g.skip[as_g.nskip++] = _wcsdup(w);
        }
        fclose(sf);
        qsort(as_g.skip, as_g.nskip, sizeof(wchar_t*), as_cmp);
    }
    return as_g.enabled && as_g.dev[0] && as_g.lib[0] && as_g.logs[0] && as_g.nslug > 0;
}

static void as_path(wchar_t* out, const wchar_t* a, const wchar_t* b, const wchar_t* c) {
    out[0] = 0;
    wcsncat(out, a, AS_PATH - 1);
    if (b) { wcsncat(out, L"\\", AS_PATH - wcslen(out) - 1); wcsncat(out, b, AS_PATH - wcslen(out) - 1); }
    if (c) { wcsncat(out, L"\\", AS_PATH - wcslen(out) - 1); wcsncat(out, c, AS_PATH - wcslen(out) - 1); }
}

/* 상태 파일: seed 로 깐 이름들(한 줄에 하나). 비정상 종료 뒤 정리용. */
static void as_state_path(wchar_t* out) { as_path(out, as_g.lib, L"_dll_seed.txt", NULL); }

static void as_remove_listed(void) {
    wchar_t sp[AS_PATH];
    as_state_path(sp);
    FILE* f = _wfopen(sp, L"rb");
    if (!f) return;
    char line[1024];
    int n = 0;
    while (fgets(line, sizeof(line), f)) {
        as_trim(line);
        if (!line[0]) continue;
        wchar_t w[AS_PATH], p[AS_PATH];
        as_utf8_to_w(line, w, AS_PATH);
        as_path(p, as_g.dev, w, NULL);
        if (DeleteFileW(p)) n++;
    }
    fclose(f);
    DeleteFileW(sp);
    write_log("[AutoSwitch] cleaned %d leftover files\n", n);
}

static void as_write_state(void) {
    wchar_t sp[AS_PATH];
    as_state_path(sp);
    FILE* f = _wfopen(sp, L"wb");
    if (!f) return;
    for (int i = 0; i < as_g.nname; i++) {
        char u[1024];
        WideCharToMultiByte(CP_UTF8, 0, as_g.name[i], -1, u, sizeof(u), NULL, NULL);
        fprintf(f, "%s\n", u);
    }
    fclose(f);
}

/* 캠페인 폴더의 파일 이름을 소문자로 모은다 */
static int as_scan(int s, wchar_t*** out) {
    wchar_t pat[AS_PATH];
    as_path(pat, as_g.lib, as_g.slug[s], L"*");
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(pat, &fd);
    if (h == INVALID_HANDLE_VALUE) { *out = NULL; return 0; }
    int cap = 1024, n = 0;
    wchar_t** v = (wchar_t**)malloc(cap * sizeof(wchar_t*));
    do {
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        if (!_wcsicmp(fd.cFileName, L"_complete.json")) continue;
        if (n == cap) { cap *= 2; v = (wchar_t**)realloc(v, cap * sizeof(wchar_t*)); }
        wchar_t* d = _wcsdup(fd.cFileName);
        for (wchar_t* p = d; *p; p++) *p = as_lower(*p);
        if (as_g.nskip && bsearch(&d, as_g.skip, as_g.nskip, sizeof(wchar_t*), as_cmp)) { free(d); continue; }
        v[n++] = d;
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    *out = v;
    return n;
}

static int as_find(const wchar_t* nm) {
    wchar_t** r = (wchar_t**)bsearch(&nm, as_g.name, as_g.nname, sizeof(wchar_t*), as_cmp);
    return r ? (int)(r - as_g.name) : -1;
}

static void as_link(int s, int i) {
    wchar_t src[AS_PATH], dst[AS_PATH];
    as_path(src, as_g.lib, as_g.slug[s], as_g.name[i]);
    as_path(dst, as_g.dev, as_g.name[i], NULL);
    DeleteFileW(dst);
    if (!CreateHardLinkW(dst, src, NULL)) CopyFileW(src, dst, FALSE);
    as_g.cur[i] = (signed char)s;
}

static void as_unlink(int i) {
    wchar_t dst[AS_PATH];
    as_path(dst, as_g.dev, as_g.name[i], NULL);
    DeleteFileW(dst);
    as_g.cur[i] = -1;
}

/* s 번 캠페인의 번역본만 남긴다. s < 0 이면 전부 지운다. */
static void as_activate(int s, int* added, int* removed) {
    int a = 0, r = 0;
    for (int i = 0; i < as_g.nname; i++) {
        int want = (s >= 0) && as_g.has[(size_t)s * as_g.nname + i];
        if (want) {
            if (as_g.cur[i] != s) { as_link(s, i); a++; }
        } else if (as_g.cur[i] >= 0) {
            as_unlink(i); r++;
        }
    }
    *added = a;
    *removed = r;
}

static int as_seed(void) {
    wchar_t*** lists = (wchar_t***)calloc(as_g.nslug, sizeof(wchar_t**));
    int* counts = (int*)calloc(as_g.nslug, sizeof(int));
    int total = 0;
    for (int s = 0; s < as_g.nslug; s++) { counts[s] = as_scan(s, &lists[s]); total += counts[s]; }
    if (total == 0) { free(lists); free(counts); return 0; }
    wchar_t** all = (wchar_t**)malloc(total * sizeof(wchar_t*));
    int k = 0;
    for (int s = 0; s < as_g.nslug; s++)
        for (int j = 0; j < counts[s]; j++) all[k++] = lists[s][j];
    qsort(all, total, sizeof(wchar_t*), as_cmp);
    int u = 0;
    for (int j = 0; j < total; j++)
        if (u == 0 || wcscmp(all[u - 1], all[j]) != 0) all[u++] = all[j];
    as_g.name = all;
    as_g.nname = u;
    as_g.has = (unsigned char*)calloc((size_t)as_g.nslug * u, 1);
    as_g.cur = (signed char*)malloc(u);
    memset(as_g.cur, -1, u);
    for (int s = 0; s < as_g.nslug; s++)
        for (int j = 0; j < counts[s]; j++) {
            int i = as_find(lists[s][j]);
            if (i >= 0) as_g.has[(size_t)s * u + i] = 1;
        }
    CreateDirectoryW(as_g.dev, NULL);
    for (int i = 0; i < u; i++)
        for (int s = 0; s < as_g.nslug; s++)
            if (as_g.has[(size_t)s * u + i]) { as_link(s, i); break; }
    as_write_state();
    return u;
}

/* 가장 최근에 수정된 nwclientLog*.txt */
static int as_newest_log(wchar_t* out) {
    wchar_t pat[AS_PATH];
    as_path(pat, as_g.logs, L"nwclientLog*.txt", NULL);
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW(pat, &fd);
    if (h == INVALID_HANDLE_VALUE) return 0;
    FILETIME best = {0, 0};
    int found = 0;
    do {
        if (!found || CompareFileTime(&fd.ftLastWriteTime, &best) > 0) {
            best = fd.ftLastWriteTime;
            as_path(out, as_g.logs, fd.cFileName, NULL);
            found = 1;
        }
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return found;
}

static DWORD WINAPI as_watch(LPVOID unused) {
    (void)unused;
    wchar_t cur_log[AS_PATH] = L"";
    LONGLONG pos = 0;
    int first = 1;
    while (!as_g.stop) {
        wchar_t p[AS_PATH];
        if (as_newest_log(p)) {
            HANDLE h = CreateFileW(p, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, NULL, OPEN_EXISTING, 0, NULL);
            if (h != INVALID_HANDLE_VALUE) {
                LARGE_INTEGER sz;
                GetFileSizeEx(h, &sz);
                if (wcscmp(p, cur_log) != 0) {
                    wcscpy(cur_log, p);
                    pos = first ? sz.QuadPart : 0;          /* 시작 직후의 옛 로그는 건너뛰고, 새로 생긴 로그는 처음부터 */
                } else if (sz.QuadPart < pos) {
                    pos = 0;
                }
                first = 0;
                while (sz.QuadPart > pos && !as_g.stop) {
                    char buf[8192];
                    DWORD want = (DWORD)((sz.QuadPart - pos) > (LONGLONG)(sizeof(buf) - 1) ? (sizeof(buf) - 1) : (sz.QuadPart - pos)), got = 0;
                    LARGE_INTEGER off; off.QuadPart = pos;
                    SetFilePointerEx(h, off, NULL, FILE_BEGIN);
                    if (!ReadFile(h, buf, want, &got, NULL) || got == 0) break;
                    buf[got] = 0;
                    pos += got;
                    char* q = buf;
                    while ((q = strstr(q, "Loading Module:")) != NULL) {
                        q += 15;
                        while (*q == ' ') q++;
                        char sha[64]; int n = 0;
                        while (*q && *q != '\r' && *q != '\n' && *q != ' ' && n < 63) sha[n++] = *q++;
                        sha[n] = 0;
                        int s = -1;
                        for (int k = 0; k < as_g.nslug; k++) if (!strcmp(as_g.sha[k], sha)) { s = k; break; }
                        DWORD t0 = GetTickCount();
                        int a = 0, r = 0;
                        as_activate(s, &a, &r);
                        write_log("[AutoSwitch] module %.12s -> %s: +%d -%d (%lu ms)\n", sha, s >= 0 ? "campaign" : "none", a, r, (unsigned long)(GetTickCount() - t0));
                    }
                }
                CloseHandle(h);
            }
        }
        Sleep(150);
    }
    return 0;
}

static void autoswitch_init(void) {
    if (!as_load_config()) return;
    as_remove_listed();                       /* 이전 비정상 종료의 잔여 정리 */
    DWORD t0 = GetTickCount();
    int n = as_seed();
    write_log("[AutoSwitch] seeded %d names for %d campaigns (%lu ms)\n", n, as_g.nslug, (unsigned long)(GetTickCount() - t0));
    if (n > 0) as_g.thread = CreateThread(NULL, 0, as_watch, NULL, 0, NULL);
}

static void autoswitch_shutdown(void) {
    if (!as_g.enabled || !as_g.nname) return;
    InterlockedExchange(&as_g.stop, 1);
    if (as_g.thread) WaitForSingleObject(as_g.thread, 500);
    for (int i = 0; i < as_g.nname; i++) if (as_g.cur[i] >= 0) as_unlink(i);
    wchar_t sp[AS_PATH];
    as_state_path(sp);
    DeleteFileW(sp);
    write_log("[AutoSwitch] cleaned up\n");
}
