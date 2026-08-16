# Scan the running RPCS3 process memory for a UTF-8 needle, then dump nearby
# NUL-terminated JP strings (to find on-screen strings we failed to translate).
import ctypes, ctypes.wintypes as w, sys, re

PROCESS_QUERY = 0x0400
PROCESS_VM_READ = 0x0010
k = ctypes.windll.kernel32

def find_pid(name='rpcs3.exe'):
    import subprocess
    out = subprocess.check_output(['tasklist', '/FI', f'IMAGENAME eq {name}', '/FO', 'CSV'], text=True)
    for line in out.splitlines():
        if name in line:
            return int(line.split(',')[1].strip('"'))
    return None

class MEMINFO(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p),
                ('AllocationProtect', w.DWORD), ('__a', ctypes.c_uint32),
                ('RegionSize', ctypes.c_size_t), ('State', w.DWORD),
                ('Protect', w.DWORD), ('Type', w.DWORD), ('__b', ctypes.c_uint32)]

def main():
    needle = sys.argv[1].encode('utf-8') if len(sys.argv) > 1 else '뉴 게임'.encode('utf-8')
    pid = find_pid()
    if not pid:
        print('rpcs3 not running'); return
    h = k.OpenProcess(PROCESS_QUERY | PROCESS_VM_READ, False, pid)
    addr = 0
    mbi = MEMINFO()
    JP = re.compile(rb'(?:[\xe3][\x81-\x83][\x80-\xbf]|[\xe4-\xe9][\x80-\xbf][\x80-\xbf])+')
    hits = 0
    MAX = 0x400000000
    while addr < MAX:
        if not k.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi)):
            break
        base = mbi.BaseAddress or 0
        size = mbi.RegionSize
        if mbi.State == 0x1000 and (mbi.Protect & 0xEE):   # committed + readable
            buf = ctypes.create_string_buffer(size)
            read = ctypes.c_size_t(0)
            if k.ReadProcessMemory(h, ctypes.c_void_p(base), buf, size, ctypes.byref(read)):
                data = buf.raw[:read.value]
                start = 0
                while True:
                    p = data.find(needle, start)
                    if p < 0: break
                    hits += 1
                    seg = data[max(0, p-160):p+200]
                    jp = [m.group().decode('utf-8', 'replace') for m in JP.finditer(seg)]
                    print(f'hit @ {base+p:#x}  nearby JP: {jp}')
                    start = p + 1
                    if hits > 20: break
        addr = base + size
        if hits > 20: break
    print('done, hits', hits)

if __name__ == '__main__':
    main()
