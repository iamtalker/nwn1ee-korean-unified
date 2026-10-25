/* 시스템 version.dll 의 내보내기 17개를 전부 진짜 함수로 넘겨 주는 프록시.
 * 게임 폴더의 version.dll 이 먼저 로드되면, 같은 프로세스의 다른 모듈(예: 그래픽 드라이버)이
 * version.dll 의 다른 함수를 가져다 쓸 때도 같은 파일을 보게 되므로 빠진 함수가 없어야 한다. */
#include <windows.h>

#define FN_LIST(X) \
    X(GetFileVersionInfoA) X(GetFileVersionInfoByHandle) X(GetFileVersionInfoExA) \
    X(GetFileVersionInfoExW) X(GetFileVersionInfoSizeA) X(GetFileVersionInfoSizeExA) \
    X(GetFileVersionInfoSizeExW) X(GetFileVersionInfoSizeW) X(GetFileVersionInfoW) \
    X(VerFindFileA) X(VerFindFileW) X(VerInstallFileA) X(VerInstallFileW) \
    X(VerLanguageNameA) X(VerLanguageNameW) X(VerQueryValueA) X(VerQueryValueW)

#define DECL_PTR(n) FARPROC pfn_##n;
FN_LIST(DECL_PTR)

/* 각 함수는 진짜 함수 주소로 그냥 점프한다(인자·반환을 건드리지 않음) */
#define DEF_STUB(n) __asm__(".text\n.globl " #n "\n" #n ":\n\tjmp *pfn_" #n "(%rip)\n");
FN_LIST(DEF_STUB)

#define LOAD_PTR(n) pfn_##n = GetProcAddress(h, #n);

__attribute__((constructor)) static void proxy_init(void) {
    wchar_t p[MAX_PATH];
    UINT n = GetSystemDirectoryW(p, MAX_PATH);
    if (n == 0 || n > MAX_PATH - 16) return;
    lstrcatW(p, L"\\version.dll");
    HMODULE h = LoadLibraryW(p);
    if (!h) return;
    FN_LIST(LOAD_PTR)
}
