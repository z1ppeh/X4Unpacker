"""
X4 Foundations Cat/Dat Unpacker
Combines interactive UI, Multithreading, and high-speed binary extraction.
Now correctly separates Base Game and Extension/DLC files.
"""

import os
import sys
import glob
import time
import fnmatch
import hashlib
import argparse
import re
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
if os.name == 'nt':
    os.system("")
C_WHITE = "\033[97;40m"
C_RED = "\033[91;40m"
C_GREEN = "\033[92;40m"
C_RESET = "\033[0m"
C_CLEAR_LINE = "\033[K"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def draw_banner():
    print(f"{C_WHITE}")
    print("██╗  ██╗██╗  ██╗    ██╗   ██╗███╗   ██╗██████╗  █████╗  ██████╗██╗  ██╗    ███████╗ █████╗ ███████╗████████╗██████╗ ")
    print("╚██╗██╔╝██║  ██║    ██║   ██║████╗  ██║██╔══██╗██╔══██╗██╔════╝██║ ██╔╝    ██╔════╝██╔══██╗██╔════╝╚══██╔══╝██╔══██╗")
    print(" ╚███╔╝ ███████║    ██║   ██║██╔██╗ ██║██████╔╝███████║██║     █████╔╝     █████╗  ███████║███████╗   ██║   ██████╔╝")
    print(" ██╔██╗ ╚════██║    ██║   ██║██║╚██╗██║██╔═══╝ ██╔══██║██║     ██╔═██╗     ██╔══╝  ██╔══██║╚════██║   ██║   ██╔══██╗")
    print("██╔╝ ██╗     ██║    ╚██████╔╝██║ ╚████║██║     ██║  ██║╚██████╗██║  ██╗    ██║     ██║  ██║███████║   ██║   ██║  ██║")
    print("╚═╝  ╚═╝     ╚═╝     ╚═════╝ ╚═╝  ╚═══╝╚═╝     ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝    ╚═╝     ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝")
    print(f"{C_RESET}")


def is_valid_x4_dir(directory):
    """Validates if a directory exists and contains .cat files in root or extensions."""
    try:
        if not directory or not os.path.exists(directory) or not os.path.isdir(directory):
            return False
        if any(f.endswith('.cat') for f in os.listdir(directory)):
            return True
        ext_dir = os.path.join(directory, 'extensions')
        if os.path.isdir(ext_dir):
            for root, dirs, files in os.walk(ext_dir):
                if any(f.endswith('.cat') for f in files):
                    return True
    except Exception:
        pass
    return False


def find_x4_installations():
    """Concurrently searches default store paths and the Windows Registry for X4 installations."""
    candidates = set()
    
    def check_defaults():
        default_paths = [
            r"C:\Program Files (x86)\Steam\steamapps\common\X4 Foundations",
            r"C:\Program Files\Steam\steamapps\common\X4 Foundations",
            r"C:\Program Files (x86)\GOG Galaxy\Games\X4 Foundations",
            r"C:\Program Files\GOG Galaxy\Games\X4 Foundations",
            r"C:\Program Files\Epic Games\X4Foundations",
            r"C:\Program Files (x86)\Epic Games\X4Foundations",
        ]
        found = set()
        for p in default_paths:
            if os.path.exists(p):
                found.add(os.path.normpath(p))
        return found

    def check_registry():
        found = set()
        if os.name != 'nt':
            return found
            
        target_key = r"HKEY_CLASSES_ROOT\Local Settings\Software\Microsoft\Windows"
        path_regex = re.compile(r'([a-zA-Z]:\\[^:*?"<>|]*?(?i:x4.*?\.exe))')
        
        try:
            command = ['reg', 'query', target_key, '/f', 'X4', '/s', '/d']
            process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True, 
                encoding='utf-8', 
                errors='ignore'
            )
            stdout, _ = process.communicate()
            for line in stdout.splitlines():
                match = path_regex.search(line)
                if match:
                    exe_path = match.group(1).strip()
                    base_dir = os.path.dirname(exe_path)
                    found.add(os.path.normpath(base_dir))
        except Exception:
            pass
        return found
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_defaults = executor.submit(check_defaults)
        f_registry = executor.submit(check_registry)
        
        candidates.update(f_defaults.result())
        candidates.update(f_registry.result())

    valid_locations = [d for d in candidates if is_valid_x4_dir(d)]
    return sorted(valid_locations)


def interactive_wizard():
    state = {
        'install': None,
        'version': None,
        'output': None,
        'file_types': None,
        'threads': None,
        'overwrite': None
    }

    def redraw_ui(error_msg=None):
        clear_screen()
        draw_banner()
        
        if state['install']: 
            print(f"{C_RED}X4 Installation:{C_RESET} {state['install']} {C_GREEN}(v{state['version']}){C_RESET}")
        if state['output']:  
            print(f"{C_RED}Output Directory:{C_RESET} {state['output']}")
        if state['file_types']: 
            print(f"{C_RED}File Types:{C_RESET} {state['file_types']}")
        if state['threads']: 
            print(f"{C_RED}Multithreading:{C_RESET} {state['threads']} threads")
        if state['overwrite']: 
            print(f"{C_RED}Existing Files:{C_RESET} {state['overwrite']}")
            
        if any(state.values()): 
            print("")
            
        if error_msg:
            print(f"{C_RED}[ERROR] {error_msg}{C_RESET}\n")
    clear_screen()
    draw_banner()
    print("Searching for X4 Installation Directories...\n")
    valid_locations = find_x4_installations()
    x4_dir = ""
    error = None
    while True:
        redraw_ui(error)
        error = None
        
        if valid_locations:
            print(f"{C_GREEN}Found the following X4 Foundations installations:{C_RESET}")
            for i, loc in enumerate(valid_locations, start=1):
                print(f"  [{i}] {loc}")
                
            manual_opt = len(valid_locations) + 1
            print(f"  [{manual_opt}] Manual Entry (Type your own path)\n")
            
            choice = input(f"Select an installation [1-{manual_opt}] [Default: 1]: ").strip()
            if choice == '': choice = '1'
            
            if choice.isdigit():
                idx = int(choice)
                if 1 <= idx <= len(valid_locations):
                    x4_dir = valid_locations[idx - 1]
                    break
                elif idx == manual_opt:
                    print("")
                    x4_dir = input("Please enter custom path to X4 Foundations: ").strip(' "\'')
                    if is_valid_x4_dir(x4_dir):
                        break
                    else:
                        error = f"Valid X4 directory not found at: {x4_dir}\nCould not locate any .cat files."
                else:
                    error = "Invalid selection number."
            else:
                error = "Please enter a valid number."
        else:
            print("X4 Folder not found automatically.\n")
            x4_dir = input(f"Please enter path to X4 Foundations: ").strip(' "\'')
            if is_valid_x4_dir(x4_dir):
                break
            else:
                error = f"Valid X4 directory not found at: {x4_dir}\nCould not locate any .cat files."

    formatted_ver = "0.00"
    ver_path = os.path.join(x4_dir, "version.dat")
    if os.path.exists(ver_path):
        try:
            with open(ver_path, 'r') as f:
                ver_raw = int(f.read().strip())
                major = ver_raw // 100
                minor = ver_raw % 100
                formatted_ver = f"{major}.{minor:02d}"
        except:
            pass
            
    state['install'] = x4_dir
    state['version'] = formatted_ver
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    base_out = os.path.join(base_dir, f"X4 unpacked {formatted_ver}")
    output_dir = ""
    error = None
    
    while True:
        redraw_ui(error)
        error = None
        
        print(f"Proposed unpack folder: \"{base_out}\"")
        out_ok = input("Is this location OK? (Y/N) [Default: Y]: ").strip().upper()
        
        if out_ok == 'Y' or out_ok == '':
            output_dir = base_out
            break
        elif out_ok == 'N':
            print("")
            output_dir = input("Enter full path for custom unpack location: ").strip(' "\'')
            if output_dir:
                break
            else:
                error = "Directory path cannot be empty."
        else:
            error = "Please enter Y or N."
            
    state['output'] = output_dir
    error = None
    while True:
        redraw_ui(error)
        error = None
        
        print("Select File Types to Unpack")
        print("[1] Standard text files only (xml, xsd, lua, xpl, txt) - Recommended")
        print("[2] ALL files (Models, sounds, textures, EVERYTHING - Takes massive space)")
        print("[3] Manual Entry (Type your own Regex parameters)\n")
        
        choice = input("Select an option [1-3]: ").strip()
        if choice == '1':
            regex_patterns = r".*\.xml|.*\.xsd|.*\.lua|.*\.xpl|.*\.txt"
            state['file_types'] = "Standard text files only"
            break
        elif choice == '2':
            regex_patterns = r".*"
            state['file_types'] = "ALL files"
            break
        elif choice == '3':
            print('\nExample: .*\\.xml|.*\\.lua')
            regex_patterns = input("Enter your custom Regex string: ").strip()
            if regex_patterns:
                state['file_types'] = f"Custom Regex ({regex_patterns})"
                break
            else:
                error = "Regex string cannot be empty."
        else:
            error = "Please enter 1, 2, or 3."
    max_system_threads = os.cpu_count() or 4
    error = None
    while True:
        redraw_ui(error)
        error = None
        
        print("Multithreading Setup")
        print(f"Your system has {max_system_threads} logical CPU cores available.")
        print("Recommended Settings: 2 on HDD | 4-6 on SSD | 8+ on NVME\n")
        
        t_in = input(f"Enter Thread Count (Press ENTER for default 4): ").strip()
        if t_in == '':
            threads = 4
            break
        if t_in.isdigit() and int(t_in) > 0:
            threads = int(t_in)
            break
        else:
            error = "Please enter a valid positive number."
            
    state['threads'] = str(threads)
    error = None
    force_overwrite = False
    while True:
        redraw_ui(error)
        error = None
        
        print("File Conflict Behavior")
        print("If a file has already been extracted to your output folder, what should the script do?")
        print("[1] Skip existing files (Recommended - Saves time if resuming a previous run)")
        print("[2] Overwrite existing files (Forces re-extraction)\n")
        
        choice = input("Select an option [1-2] [Default: 1]: ").strip()
        if choice == '' or choice == '1':
            force_overwrite = False
            state['overwrite'] = "Skip (Keep existing)"
            break
        elif choice == '2':
            force_overwrite = True
            state['overwrite'] = "Overwrite (Force replace)"
            break
        else:
            error = "Please enter 1 or 2."
    redraw_ui()
    print("Starting Unpack Process...\n")

    return {
        'mode': 'all_folders',
        'source': x4_dir,
        'command': 'x',
        'filter': regex_patterns,
        'dest_dir': output_dir,
        'threads': threads,
        'is_regex': True,
        'force': force_overwrite
    }


def setup_argparse():
    help_text = """
Usage: x4_unpack.py [OPTIONS] <mode> <source> <command> <path_or_mask> [<dest_dir>]

  (Run without arguments to launch the Interactive UI Wizard)

  mode          file        — Only process the specific file(s) provided.
                folder      — Process all .cat files ONLY in the target folder.
                all_folders — Process all .cat files in the folder AND all subfolders.

  source        Path to the file or folder (depending on mode).
  command       x   — extract matched files to dest_dir
                ls  — list matched files (no extraction; dest_dir not needed)
  path_or_mask  Path prefix ("assets/textures") or glob mask ("assets/*.xml")
  dest_dir      Output directory (required for 'x', ignored for 'ls')

Options:
  -t, --threads   Number of threads for extraction (default: 4)
  -f, --force     Force overwrite of existing files (x only)
"""
    parser = argparse.ArgumentParser(description=help_text, formatter_class=argparse.RawTextHelpFormatter, usage=argparse.SUPPRESS)
    parser.add_argument('-t', '--threads', type=int, default=4, help=argparse.SUPPRESS)
    parser.add_argument('-f', '--force', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('mode', choices=['file', 'folder', 'all_folders'], help=argparse.SUPPRESS)
    parser.add_argument('source', help=argparse.SUPPRESS)
    parser.add_argument('command', choices=['x', 'ls'], help=argparse.SUPPRESS)
    parser.add_argument('filter', help=argparse.SUPPRESS)
    parser.add_argument('dest_dir', nargs='?', default=None, help=argparse.SUPPRESS)
    return parser


def log(msg):
    print(msg, file=sys.stderr)


def extract_worker(job):
    """ Worker function executed by thread pool """
    fp, info, dest_dir, force = job
    size = info['size']
    out_path = os.path.normpath(os.path.join(dest_dir, fp))

    if os.path.exists(out_path) and not force:
        return (False, "skipped")

    try:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(info['dat'], 'rb') as d_file:
            d_file.seek(info['offset'])
            data = d_file.read(size)
            
        with open(out_path, 'wb') as out_file:
            out_file.write(data)
        return (True, "success")
    except Exception as e:
        return (False, f"error: {e}")


def print_progress(current, total, bar_length=40):
    """ Draws the dynamic progress bar on a single line """
    if total == 0: return
    pct = (current / total) * 100
    filled = int((pct * bar_length) / 100)
    bar = '#' * filled + '-' * (bar_length - filled)
    sys.stdout.write(f"\r\033[1G[{bar}] {pct:.1f}% ({current}/{total} files extracted){C_CLEAR_LINE}")
    sys.stdout.flush()


def main():
    if len(sys.argv) == 1:
        args_dict = interactive_wizard()
        class Args: pass
        args = Args()
        for k, v in args_dict.items(): setattr(args, k, v)
    else:
        parser = setup_argparse()
        if len(sys.argv) < 5:
            parser.print_help()
            sys.exit(1)
        args = parser.parse_args()
        args.is_regex = False
        if args.command == 'x' and not args.dest_dir:
            log("Error: dest_dir is required for the 'x' command.")
            sys.exit(1)

    start_time = time.perf_counter()
    if os.path.isdir(args.source):
        base_install_dir = args.source
    else:
        base_install_dir = os.path.dirname(args.source)
    cat_files = []
    if args.mode == 'file':
        matched = glob.glob(args.source)
        if not matched and os.path.isfile(args.source): matched = [args.source]
        cat_files.extend([f for f in matched if f.endswith('.cat') and not f.endswith('_sig.cat')])
    elif args.mode == 'folder':
        search_pattern = os.path.join(args.source, '*.cat')
        cat_files.extend([f for f in glob.glob(search_pattern) if not f.endswith('_sig.cat')])
    elif args.mode == 'all_folders':
        for root, dirs, files in os.walk(args.source):
            for f in files:
                if f.endswith('.cat') and not f.endswith('_sig.cat'):
                    cat_files.append(os.path.join(root, f))

    if not cat_files:
        log(f"Error: No valid .cat files found for source '{args.source}'.")
        sys.exit(1)
    base_path = args.source.replace('\\', '/').rstrip('/')
    base_depth = base_path.count('/')
    cat_files.sort(key=lambda f: (f.replace('\\', '/').rstrip('/').count('/') - base_depth, f))

    catalog = {}
    ignored_deletions = 0
    total_parsed_lines = 0

    log("Building catalog dictionary...")
    for cat_path in cat_files:
        dat_path = cat_path[:-4] + '.dat'
        cat_name = os.path.basename(cat_path)
        cum_offset = 0
        rel_dir = os.path.relpath(os.path.dirname(cat_path), base_install_dir).replace('\\', '/')
        if rel_dir == '.':
            rel_dir = "" # Base game file, no prefix needed
            
        try:
            with open(cat_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    parts = line.split()
                    if len(parts) < 4: continue
                    
                    size_str = parts[-3]
                    fp = " ".join(parts[:-3]).replace('\\', '/').lower()
                    while fp.startswith('./'): fp = fp[2:]
                    while fp.startswith('/'): fp = fp[1:]
                    if rel_dir:
                        fp = f"{rel_dir}/{fp}"
                    
                    try: size = int(size_str)
                    except ValueError: continue

                    total_parsed_lines += 1
                    if size == 0:
                        ignored_deletions += 1
                        cum_offset += size
                        continue
                    
                    catalog[fp] = {
                        'dat': dat_path,
                        'cat': cat_name,
                        'offset': cum_offset,
                        'size': size
                    }
                    cum_offset += size
        except Exception as e:
            log(f"Warning: Could not read {cat_path}: {e}")
    matched_files = []
    filter_val = args.filter

    if args.is_regex:
        compiled_regex = re.compile(filter_val, re.IGNORECASE)
        for fp, info in catalog.items():
            if compiled_regex.match(fp):
                matched_files.append((fp, info))
    else:
        filter_val = filter_val.replace('\\', '/')
        is_glob = '*' in filter_val or '?' in filter_val
        glob_basename_only = is_glob and '/' not in filter_val

        for fp, info in catalog.items():
            if is_glob:
                target = os.path.basename(fp) if glob_basename_only else fp
                if fnmatch.fnmatch(target, filter_val):
                    matched_files.append((fp, info))
            else:
                if fp == filter_val or fp.startswith(filter_val + '/'):
                    matched_files.append((fp, info))
                
    matched_files.sort(key=lambda x: x[0])
    
    log(f"Parsed {total_parsed_lines} total files (Ignored {ignored_deletions} patch deletions)")
    log(f"Matched {len(matched_files)} files to process.\n")

    if len(matched_files) == 0:
        log("Nothing to extract.")
        sys.exit(0)
    if args.command == 'x':
        os.makedirs(args.dest_dir, exist_ok=True)
        
        extracted = 0
        skipped = 0
        errors = 0
        
        jobs = [(fp, info, args.dest_dir, args.force) for fp, info in matched_files]
        total_jobs = len(jobs)
        
        print_progress(0, total_jobs)
        
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            futures = [executor.submit(extract_worker, job) for job in jobs]
            
            for future in as_completed(futures):
                success, reason = future.result()
                if success:
                    extracted += 1
                elif reason == "skipped":
                    skipped += 1
                else:
                    errors += 1
                
                processed = extracted + skipped + errors
                if processed % max(1, (total_jobs // 100)) == 0 or processed == total_jobs:
                    print_progress(processed, total_jobs)

        print("")
        log(f"\n{C_GREEN}Extracted : {extracted}{C_RESET}")
        if skipped > 0: log(f"Skipped   : {skipped} (already existed)")
        if errors > 0: log(f"{C_RED}Errors    : {errors}{C_RESET}")

    elif args.command == 'ls':
        for fp, info in matched_files:
            print(f"{info['size']:>12}  {info['cat']:<12}  {fp}")
        log(f"\nListed: {len(matched_files)}")

    elapsed = time.perf_counter() - start_time
    if elapsed > 60:
        mins = int(elapsed // 60)
        secs = elapsed % 60
        log(f"Time taken: {mins}m {secs:.2f}s")
    else:
        log(f"Time taken: {elapsed:.2f} seconds")
        
    if len(sys.argv) == 1:
        input("\nPress ENTER to exit...")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExtraction cancelled by user.")
        sys.exit(1)