#include <windows.h>
#include <string.h>
static HMODULE real_ver;
static FARPROC real_fn(const char* name) {
    if (!real_ver) {
        char p[MAX_PATH];
        GetSystemDirectoryA(p, MAX_PATH);
        strcat(p, "\\version.dll");  /* C 문자열에서 역슬래시는 두 개여야 한다(하나면  가 세로탭이 되어 진짜 version.dll 을 못 불러온다) */
        real_ver = LoadLibraryA(p);
    }
    return real_ver ? GetProcAddress(real_ver, name) : NULL;
}
__declspec(dllexport) BOOL WINAPI GetFileVersionInfoA(LPCSTR f, DWORD h, DWORD l, LPVOID d) {
    BOOL (WINAPI *fn)(LPCSTR, DWORD, DWORD, LPVOID) = (void*)real_fn("GetFileVersionInfoA");
    return fn ? fn(f, h, l, d) : FALSE;
}
__declspec(dllexport) DWORD WINAPI GetFileVersionInfoSizeA(LPCSTR f, LPDWORD h) {
    DWORD (WINAPI *fn)(LPCSTR, LPDWORD) = (void*)real_fn("GetFileVersionInfoSizeA");
    return fn ? fn(f, h) : 0;
}
__declspec(dllexport) BOOL WINAPI VerQueryValueA(LPCVOID b, LPCSTR s, LPVOID* p, PUINT l) {
    BOOL (WINAPI *fn)(LPCVOID, LPCSTR, LPVOID*, PUINT) = (void*)real_fn("VerQueryValueA");
    return fn ? fn(b, s, p, l) : FALSE;
}
