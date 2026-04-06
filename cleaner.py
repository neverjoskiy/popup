import pymem
import pymem.process
import ctypes
import os

TARGET_STRINGS = [
    "OgUwQPNl",
]

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def wipe_memory():
    if not is_admin():
        print("[-] error: launch script from admin permission!")
        return

    try:
        pm = pymem.Pymem("javaw.exe")
        print(f"[+] Connected to javaw.exe (PID: {pm.process_id})")
    except Exception:
        print("[-] error: process javaw.exe not found.")
        return

    patterns = []
    for s in TARGET_STRINGS:
        patterns.append(s.encode('utf-8'))
        patterns.append(s.encode('utf-16-le'))

    MEM_COMMIT = 0x1000
    MEM_DECOMMIT = 0x4000
    PAGE_READWRITE = 0x04
    PAGE_EXECUTE_READWRITE = 0x40

    cleared_count = 0
    regions_scanned = 0
    regions_matched = 0

    current_address = 0
    max_address = 0x7FFFFFFFFFFF

    print("[*] Scanning and cleaning...")

    while current_address < max_address:
        try:
            mbi = pymem.memory.virtual_query(pm.process_handle, current_address)
            regions_scanned += 1

            if regions_scanned % 100 == 0:
                print(f"[*] Progress: {regions_scanned} regions, currently at 0x{current_address:X}")

            if mbi.State == MEM_COMMIT and \
               mbi.Protect in [PAGE_READWRITE, PAGE_EXECUTE_READWRITE]:

                try:
                    region_size = mbi.RegionSize
                    read_size = min(region_size, 10 * 1024 * 1024)
                    
                    region_data = pm.read_bytes(current_address, read_size)
                    
                    if region_data is None or len(region_data) == 0:
                        current_address += mbi.RegionSize
                        continue

                    found_in_region = 0
                    for pattern in patterns:
                        start = 0
                        while True:
                            idx = region_data.find(pattern, start)
                            if idx == -1:
                                break
                            
                            target_addr = current_address + idx
                            print(f"[!] Found pattern at 0x{target_addr:X}")

                            random_bytes = os.urandom(len(pattern))
                            pm.write_bytes(target_addr, random_bytes, len(pattern))
                            cleared_count += 1
                            found_in_region += 1
                            start = idx + len(pattern)
                    
                    if found_in_region > 0:
                        regions_matched += 1
                        print(f"    -> Cleared {found_in_region} matches in this region")
                        
                except Exception as e:
                    print(f"[-] Error reading region at 0x{current_address:X}: {e}")
            
            current_address += mbi.RegionSize
        except StopIteration:
            break
        except Exception as e:
            print(f"[-] Unexpected error at 0x{current_address:X}: {e}")
            current_address += 0x10000

    print(f"[+] Done! Scanned regions: {regions_scanned}")
    print(f"[+] Regions with matches: {regions_matched}")
    print(f"[+] Total cleared strings: {cleared_count}")
    print("[!] Launch a search in System Informer again for test.")

if __name__ == "__main__":
    wipe_memory()