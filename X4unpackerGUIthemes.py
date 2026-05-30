"""
X4 Foundations Cat/Dat Unpacker - GUI Edition
Combines high-speed multithreaded binary extraction with a responsive Tkinter GUI.

Disclaimer:
This utility is an unofficial, community-created tool. It is not affiliated with,
authorized, sponsored, or otherwise approved by Egosoft GmbH. "X4: Foundations"
and "Egosoft" are trademarks of Egosoft GmbH. 
This software is provided "as is", without warranty of any kind. Use at your own risk. 
The developers are not responsible for any damage or data loss.
"""

import os
import sys
import glob
import time
import fnmatch
import re
import subprocess
import threading
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import queue
import xml.etree.ElementTree as ET
import webbrowser

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
try:
    from ttkthemes import ThemedTk
    HAS_TTKTHEMES = True
except ImportError:
    HAS_TTKTHEMES = False


class AutoScrollbar(ttk.Scrollbar):
    """A Scrollbar that automatically hides itself when not needed."""
    def set(self, lo, hi):
        if float(lo) <= 0.0 and float(hi) >= 1.0:
            self.grid_forget()
        else:
            self.grid(row=0, column=1, sticky="ns")
        super().set(lo, hi)


class ToolTip:
    """Provides a safe, native-looking tooltip overlay on hover."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrirect = getattr(tw, "wm_overrideredirect", None)
        if tw.wm_overrirect:
            tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(
            tw, 
            text=self.text, 
            justify=tk.LEFT,
            background="#FFFFE1", 
            foreground="#000000",
            relief=tk.SOLID, 
            borderwidth=1,
            font=("Segoe UI", "9")
        )
        label.pack(ipadx=6, ipady=4)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()


class X4UnpackerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("X4 Foundations Cat/Dat Unpacker (Unofficial)")
        self.root.geometry("1280x850")
        self.root.minimum_size = (1150, 750)
        self.queue = queue.Queue()
        self.is_running = False
        self.cancel_event = threading.Event()
        
        self.parsed_catalogs = {}
        self.filtered_dlc_sizes = {}
        self.dlc_size_labels = {}
        self.setup_styles()
        self.create_widgets()
        self.update_theme_backgrounds()
        threading.Thread(target=self.async_detect_installations, daemon=True).start()
        self.root.after(100, self.process_queue)

    def setup_styles(self):
        style = ttk.Style()
        if not HAS_TTKTHEMES:
            if "vista" in style.theme_names():
                style.theme_use("vista")
            elif "clam" in style.theme_names():
                style.theme_use("clam")
            
        style.configure("TLabel", font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI", 9))
        style.configure("Status.TLabel", font=("Segoe UI", 9, "italic"))
        style.configure("Green.Horizontal.TProgressbar", background="#28a745")

    def create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        self.paned_window = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(self.paned_window, width=768)
        left_frame.pack_propagate(False)

        right_frame = ttk.Frame(self.paned_window, width=512)
        right_frame.pack_propagate(False)
        self.paned_window.add(left_frame, weight=1)
        self.paned_window.add(right_frame, weight=1)
        control_group = ttk.Frame(left_frame, padding=(0, 10, 0, 0))
        control_group.pack(side=tk.BOTTOM, fill=tk.X)
        control_row1 = ttk.Frame(control_group)
        control_row1.pack(fill=tk.X, expand=True)

        self.btn_start = tk.Button(
            control_row1, 
            text="Start Extraction", 
            command=self.start_extraction,
            font=("Segoe UI", 10, "bold"),
            bg="#0078D7",
            fg="white",
            activebackground="#005A9E",
            activeforeground="white",
            relief=tk.RAISED,
            bd=1,
            padx=15,
            pady=6,
            cursor="hand2"
        )
        self.btn_start.pack(side=tk.LEFT)

        self.progress_bar = ttk.Progressbar(control_row1, mode="determinate")
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0), ipady=4)
        control_row2 = ttk.Frame(control_group)
        control_row2.pack(fill=tk.X, expand=True, pady=(6, 0))

        self.lbl_stats = ttk.Label(
            control_row2, 
            text="Status: Ready to extract.", 
            font=("Segoe UI", 9, "bold"), 
            foreground="#444444"
        )
        self.lbl_stats.pack(side=tk.LEFT)
        divider = ttk.Separator(left_frame, orient=tk.HORIZONTAL)
        divider.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        canvas_container = ttk.Frame(left_frame)
        canvas_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        canvas_container.rowconfigure(0, weight=1)
        canvas_container.columnconfigure(0, weight=1)

        self.left_canvas = tk.Canvas(canvas_container, borderwidth=0, highlightthickness=0)
        self.left_scrollbar = AutoScrollbar(canvas_container, orient="vertical", command=self.left_canvas.yview)
        
        self.scrollable_left_content = ttk.Frame(self.left_canvas)
        self.scrollable_left_content.bind(
            "<Configure>",
            lambda e: self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
        )
        
        self.left_canvas_window = self.left_canvas.create_window((0, 0), window=self.scrollable_left_content, anchor="nw")
        self.left_canvas.bind(
            "<Configure>",
            lambda e: self.left_canvas.itemconfig(self.left_canvas_window, width=e.width)
        )
        
        self.left_canvas.configure(yscrollcommand=self.left_scrollbar.set)
        self.left_canvas.grid(row=0, column=0, sticky="nsew")
        self.left_scrollbar.grid(row=0, column=1, sticky="ns")
        def _on_left_mousewheel(event):
            if event.num == 4 or event.delta > 0:
                self.left_canvas.yview_scroll(-1, "units")
            elif event.num == 5 or event.delta < 0:
                self.left_canvas.yview_scroll(1, "units")

        self.left_canvas.bind("<Enter>", lambda _: self.left_canvas.bind_all("<MouseWheel>", _on_left_mousewheel))
        self.left_canvas.bind("<Leave>", lambda _: self.left_canvas.unbind_all("<MouseWheel>"))
        self.left_canvas.bind("<Enter>", lambda _: self.left_canvas.bind_all("<Button-4>", _on_left_mousewheel), add="+")
        self.left_canvas.bind("<Enter>", lambda _: self.left_canvas.bind_all("<Button-5>", _on_left_mousewheel), add="+")
        source_group = ttk.LabelFrame(self.scrollable_left_content, text=" X4 Foundations Installation Folder ", padding="10")
        source_group.pack(fill=tk.X, pady=(0, 10))

        row_src_input = ttk.Frame(source_group)
        row_src_input.pack(fill=tk.X, expand=True)

        self.combo_source = ttk.Combobox(row_src_input, font=("Segoe UI", 9))
        self.combo_source.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.combo_source.bind("<<ComboboxSelected>>", self.on_source_selected)
        self.combo_source.bind("<KeyRelease>", self.on_source_selected)

        btn_browse_src = ttk.Button(row_src_input, text="Browse...", command=self.browse_source_dir)
        btn_browse_src.pack(side=tk.RIGHT)

        row_src_status = ttk.Frame(source_group)
        row_src_status.pack(fill=tk.X, expand=True, pady=(5, 0))

        self.lbl_version = tk.Label(
            row_src_status, 
            text="Status: Detecting X4 installations...", 
            font=("Segoe UI", 12, "bold"), 
            fg="#7B2CBF",
            anchor=tk.W
        )
        self.lbl_version.pack(fill=tk.X, anchor=tk.W)
        dest_group = ttk.LabelFrame(self.scrollable_left_content, text=" Output Directory ", padding="10")
        dest_group.pack(fill=tk.X, pady=(0, 10))

        self.ent_dest = ttk.Entry(dest_group, font=("Segoe UI", 9))
        self.ent_dest.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        btn_browse_dst = ttk.Button(dest_group, text="Browse...", command=self.browse_dest_dir)
        btn_browse_dst.pack(side=tk.RIGHT)
        self.dlc_group = ttk.LabelFrame(self.scrollable_left_content, text=" Content to Unpack ", padding="10")
        self.dlc_group.pack(fill=tk.X, pady=(0, 10))
        
        self.dlc_container = ttk.Frame(self.dlc_group)
        self.dlc_container.pack(fill=tk.X, expand=True)
        self.dlc_bottom_bar = ttk.Frame(self.dlc_group)
        self.dlc_bottom_bar.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 0))
        
        self.lbl_total_size = tk.Label(
            self.dlc_bottom_bar, 
            text="Content Selected Size: ~0 B", 
            font=("Segoe UI", 9, "bold"), 
            fg="#333333"
        )
        self.lbl_total_size.pack(side=tk.RIGHT, padx=10)
        
        self.dlc_vars = {}
        filter_group = ttk.LabelFrame(self.scrollable_left_content, text=" File Filtering ", padding="10")
        filter_group.pack(fill=tk.X, pady=(0, 10))
        filter_grid_frame = ttk.Frame(filter_group)
        filter_grid_frame.pack(fill=tk.X, anchor=tk.W)
        filter_grid_frame.columnconfigure(0, weight=1)
        filter_grid_frame.columnconfigure(1, weight=1)

        self.filter_var = tk.IntVar(value=1)
        
        rb1 = ttk.Radiobutton(filter_grid_frame, text="Standard text files (xml, xsd, lua, xpl, txt)", variable=self.filter_var, value=1, command=self.toggle_regex_state)
        rb2 = ttk.Radiobutton(filter_grid_frame, text="Full Unpack", variable=self.filter_var, value=2, command=self.toggle_regex_state)
        rb3 = ttk.Radiobutton(filter_grid_frame, text="Full unpack - No Sound", variable=self.filter_var, value=3, command=self.toggle_regex_state)
        self.radio_custom = ttk.Radiobutton(filter_grid_frame, text="Custom selection", variable=self.filter_var, value=4, command=self.toggle_regex_state)

        rb1.grid(row=0, column=0, sticky=tk.W, pady=3, padx=(0, 5))
        rb2.grid(row=0, column=1, sticky=tk.W, pady=3, padx=5)
        rb3.grid(row=1, column=0, sticky=tk.W, pady=3, padx=(0, 5))
        self.radio_custom.grid(row=1, column=1, sticky=tk.W, pady=3, padx=5)
        self.cb_frame = ttk.LabelFrame(filter_group, text=" Custom Extension Selector ", padding="5")
        
        self.extensions_list = [
            '.abc', '.amw', '.ani', '.bgf', '.bgp', '.bsg', '.css', '.dae',
            '.dds', '.dtd', '.glsl', '.gz', '.h', '.html', '.jcs', '.jpg',
            '.js', '.lua', '.ogg', '.peb', '.pk', '.psb', '.txt', '.wav',
            '.xac', '.xmf', '.xml', '.xpl', '.xpm', '.xsd', '.xsl', '.xsm',
            '.xwma'
        ]
        
        self.ext_vars = {}
        self.checkbox_widgets = []
        cols_count = 6
        for col_idx in range(cols_count):
            self.cb_frame.columnconfigure(col_idx, weight=1)
            
        for idx, ext in enumerate(self.extensions_list):
            var = tk.BooleanVar(value=False)
            self.ext_vars[ext] = var
            cb = ttk.Checkbutton(self.cb_frame, text=ext, variable=var, command=self.update_regex_from_checkboxes)
            row = idx // cols_count
            col = idx % cols_count
            cb.grid(row=row, column=col, sticky=tk.W, padx=2, pady=1)
            self.checkbox_widgets.append(cb)

        self.ent_regex = ttk.Entry(filter_group, font=("Segoe UI", 9))
        self.ent_regex.insert(0, r".*\.xml|.*\.xsd|.*\.lua|.*\.xpl|.*\.txt")
        self.ent_regex.pack(fill=tk.X, pady=(5, 0))
        self.ent_regex.config(state=tk.DISABLED)
        self.ent_regex.bind("<KeyRelease>", lambda e: self.recalculate_sizes())
        regex_help_text = (
            "Regex Format Information:\n"
            "Matches internal file paths using Python regular expressions.\n\n"
            "Format: .*\\.(ext1|ext2)$\n"
            "Example: .*\\.(js|pk|xac|xml)$\n\n"
            "• Use '|' to separate file types.\n"
            "• Use '$' to search at the end of file names.\n"
            "• Use '.*' to match everything."
        )
        ToolTip(self.radio_custom, regex_help_text)
        ToolTip(self.ent_regex, regex_help_text)
        settings_group = ttk.LabelFrame(self.scrollable_left_content, text=" Extraction Settings ", padding="10")
        settings_group.pack(fill=tk.X, pady=(0, 10))
        thread_frame = ttk.Frame(settings_group)
        thread_frame.pack(fill=tk.X, pady=(2, 0))
        
        max_threads = os.cpu_count() or 4
        self.lbl_thread_count = tk.Label(
            thread_frame, 
            text=f"Thread count (Max {max_threads} cores):",
            font=("Segoe UI", 9)
        )
        self.lbl_thread_count.pack(side=tk.LEFT)
        
        self.spin_threads = ttk.Spinbox(thread_frame, from_=1, to=128, width=5)
        self.spin_threads.set(str(max(1, max_threads // 2)))
        self.spin_threads.pack(side=tk.RIGHT)
        self.spin_threads.bind("<FocusOut>", lambda e: self.clamp_threads())
        self.lbl_recommend = tk.Label(
            settings_group, 
            text="Recommended: HDD: 1-2 | SSD: 4-6 | NVMe: 8+", 
            font=("Segoe UI", 8, "italic"), 
            foreground="#555555"
        )
        self.lbl_recommend.pack(anchor=tk.W, pady=(2, 10))
        self.overwrite_var = tk.BooleanVar(value=False)
        self.cb_overwrite = ttk.Checkbutton(settings_group, text="Force overwrite existing files", variable=self.overwrite_var)
        self.cb_overwrite.pack(anchor=tk.W)
        self.copy_content_var = tk.BooleanVar(value=True)
        self.cb_copy_content = ttk.Checkbutton(settings_group, text="Copy content.xml for selected DLCs/extensions", variable=self.copy_content_var)
        self.cb_copy_content.pack(anchor=tk.W, pady=(5, 5))
        theme_frame = ttk.Frame(settings_group)
        theme_frame.pack(fill=tk.X, pady=(5, 0))
        self.lbl_gui_theme = tk.Label(
            theme_frame, 
            text="GUI Theme:",
            font=("Segoe UI", 9)
        )
        self.lbl_gui_theme.pack(side=tk.LEFT)
        style = ttk.Style()
        built_in_themes = list(style.theme_names())
        
        if HAS_TTKTHEMES:
            available_themes = sorted(list(set(self.root.get_themes() + built_in_themes)))
            current_theme = self.root.current_theme
        else:
            available_themes = sorted(built_in_themes)
            current_theme = style.theme_use()
            
        self.combo_theme = ttk.Combobox(theme_frame, values=available_themes, state="readonly", width=18)
        self.combo_theme.set(current_theme)
        self.combo_theme.pack(side=tk.RIGHT)
        self.combo_theme.bind("<<ComboboxSelected>>", self.on_theme_changed)
        self.set_checkboxes_state(tk.DISABLED)
        log_group = ttk.LabelFrame(right_frame, text=" Process Logs ", padding="5")
        log_group.pack(fill=tk.BOTH, expand=True)

        self.log_widget = scrolledtext.ScrolledText(log_group, font=("Consolas", 9), state=tk.DISABLED, bg="#fcfcfc")
        self.log_widget.pack(fill=tk.BOTH, expand=True)
        log_controls = ttk.Frame(log_group)
        log_controls.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 0))

        self.autoscroll_var = tk.BooleanVar(value=True)
        self.cb_autoscroll = ttk.Checkbutton(log_controls, text="Auto-scroll logs", variable=self.autoscroll_var)
        self.cb_autoscroll.pack(side=tk.LEFT)
        self.btn_about = ttk.Button(log_controls, text="About", command=self.show_about_dialog)
        self.btn_about.pack(side=tk.RIGHT)
    def update_theme_backgrounds(self):
        """Finds the current theme's Frame background color and applies it to non-ttk canvas/labels."""
        style = ttk.Style()
        bg_color = style.lookup("TFrame", "background")
        if not bg_color:
            bg_color = "#f0f0f0"  # Safe standard fallback color
        if hasattr(self, 'left_canvas') and self.left_canvas:
            self.left_canvas.configure(background=bg_color)
        labels_to_sync = [
            'lbl_version',
            'lbl_total_size',
            'lbl_thread_count',
            'lbl_recommend',
            'lbl_gui_theme'
        ]
        for attr in labels_to_sync:
            if hasattr(self, attr):
                widget = getattr(self, attr)
                if widget:
                    widget.configure(background=bg_color)
        if hasattr(self, 'dlc_size_labels'):
            for label_widget in self.dlc_size_labels.values():
                label_widget.configure(background=bg_color)

    def on_theme_changed(self, event=None):
        chosen_theme = self.combo_theme.get()
        try:
            if HAS_TTKTHEMES:
                self.root.set_theme(chosen_theme)
            else:
                style = ttk.Style()
                style.theme_use(chosen_theme)
            style = ttk.Style()
            style.configure("Status.TLabel", font=("Segoe UI", 9, "italic"))
            style.configure("Green.Horizontal.TProgressbar", background="#28a745")
            self.update_theme_backgrounds()
        except Exception as e:
            self.log(f"Warning: Failed to set theme {chosen_theme}: {e}")
    def async_detect_installations(self):
        candidates = set()
        default_paths = [
            r"C:\Program Files (x86)\Steam\steamapps\common\X4 Foundations",
            r"C:\Program Files\Steam\steamapps\common\X4 Foundations",
            r"C:\Program Files (x86)\GOG Galaxy\Games\X4 Foundations",
            r"C:\Program Files\GOG Galaxy\Games\X4 Foundations",
            r"C:\Program Files\Epic Games\X4Foundations",
            r"C:\Program Files (x86)\Epic Games\X4Foundations",
        ]
        
        for p in default_paths:
            if os.path.exists(p):
                candidates.add(os.path.normpath(p))

        if os.name == 'nt':
            try:
                creation_flags = subprocess.CREATE_NO_WINDOW
                
                target_key = r"HKEY_CLASSES_ROOT\Local Settings\Software\Microsoft\Windows"
                path_regex = re.compile(r'([a-zA-Z]:\\[^:*?"<>|]*?(?i:x4.*?\.exe))')
                command = ['reg', 'query', target_key, '/f', 'X4', '/s', '/d']
                
                process = subprocess.Popen(
                    command, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True, 
                    encoding='utf-8', 
                    errors='ignore',
                    creationflags=creation_flags
                )
                stdout, _ = process.communicate()
                for line in stdout.splitlines():
                    match = path_regex.search(line)
                    if match:
                        base_dir = os.path.dirname(match.group(1).strip())
                        candidates.add(os.path.normpath(base_dir))
            except Exception:
                pass

        valid_locations = [d for d in candidates if self.is_valid_x4_dir(d)]
        valid_locations = sorted(valid_locations)

        self.queue.put(("detection_done", valid_locations))

    def classify_directory(self, directory):
        """Classify if directory is a full X4 install, a raw Cat/Dat folder, or invalid."""
        if not directory or not os.path.exists(directory) or not os.path.isdir(directory):
            return "invalid"
        
        has_cats = False
        try:
            if any(f.endswith('.cat') for f in os.listdir(directory)):
                has_cats = True
            else:
                ext_dir = os.path.join(directory, 'extensions')
                if os.path.isdir(ext_dir):
                    for root, dirs, files in os.walk(ext_dir):
                        if any(f.endswith('.cat') for f in files):
                            has_cats = True
                            break
        except Exception:
            pass

        if not has_cats:
            return "invalid"

        try:
            for f in os.listdir(directory):
                f_lower = f.lower()
                if f_lower.startswith('x4') and f_lower.endswith('.exe'):
                    return "x4_game"
        except Exception:
            pass

        return "cat_only"

    def is_valid_x4_dir(self, directory):
        return self.classify_directory(directory) in ("x4_game", "cat_only")

    def get_game_version(self, x4_dir):
        if not x4_dir:
            return "Unknown"
        ver_path = os.path.join(x4_dir, "version.dat")
        if os.path.exists(ver_path):
            try:
                with open(ver_path, 'r') as f:
                    ver_raw = int(f.read().strip())
                    major = ver_raw // 100
                    minor = ver_raw % 100
                    return f"{major}.{minor:02d}"
            except Exception:
                pass
        return "Unknown"

    def format_dlc_name(self, folder_name):
        """Format fallback DLC names. Strips 'ego_dlc_', converts underscores, and titles."""
        if folder_name.lower().startswith("ego_dlc_"):
            display = folder_name[8:]
        else:
            display = folder_name
        return display.replace("_", " ").title()

    def get_extension_display_name(self, folder_path, folder_name):
        """Reads extension display name from content.xml if possible, falling back to folder styling."""
        content_xml_path = os.path.join(folder_path, "content.xml")
        if os.path.exists(content_xml_path):
            try:
                tree = ET.parse(content_xml_path)
                root = tree.getroot()
                if root.tag == "content":
                    name_attr = root.get("name")
                    if name_attr:
                        return name_attr.strip()
            except Exception:
                pass
        return self.format_dlc_name(folder_name)

    def format_size(self, size_bytes):
        """Format bytes into readable MB/GB units."""
        if size_bytes <= 0:
            return "0 B"
        units = ["B", "KB", "MB", "GB", "TB"]
        idx = 0
        size = float(size_bytes)
        while size >= 1024.0 and idx < len(units) - 1:
            size /= 1024.0
            idx += 1
        return f"{size:.1f} {units[idx]}"

    def parse_all_catalogs(self, source_dir):
        """Quickly parses header indexes from catalog archives without loading binary payloads."""
        catalogs = {}
        if not source_dir or not os.path.exists(source_dir):
            return catalogs
            
        for root, dirs, files in os.walk(source_dir):
            for f in files:
                if f.endswith('.cat') and not f.endswith('_sig.cat'):
                    full_cat_path = os.path.join(root, f)
                    rel_dir = os.path.relpath(root, source_dir).replace('\\', '/')
                    
                    if rel_dir == '.':
                        group_key = "base_game"
                    else:
                        parts = rel_dir.split('/')
                        if len(parts) >= 2 and parts[0] == "extensions":
                            group_key = f"extensions/{parts[1]}"
                        else:
                            group_key = "unknown"
                    
                    if group_key not in catalogs:
                        catalogs[group_key] = []
                    
                    try:
                        with open(full_cat_path, 'r', encoding='utf-8', errors='replace') as cat_file:
                            for line in cat_file:
                                line = line.strip()
                                if not line:
                                    continue
                                parts = line.split()
                                if len(parts) < 4:
                                    continue
                                
                                size_str = parts[-3]
                                fp = " ".join(parts[:-3]).replace('\\', '/').lower()
                                while fp.startswith('./'): fp = fp[2:]
                                while fp.startswith('/'): fp = fp[1:]

                                if rel_dir and rel_dir != '.':
                                    fp = f"{rel_dir}/{fp}"
                                    
                                try:
                                    size = int(size_str)
                                    if size > 0:
                                        catalogs[group_key].append((fp, size))
                                except ValueError:
                                    continue
                    except Exception:
                        pass
        return catalogs

    def recalculate_sizes(self):
        """Filters cached catalog metadata on the main thread and updates all size labels instantly."""
        pattern = self.ent_regex.get().strip()
        try:
            compiled_regex = re.compile(pattern, re.IGNORECASE)
        except Exception:
            compiled_regex = re.compile(".*")  # Fallback to match everything on error

        self.filtered_dlc_sizes = {}
        for group_key, file_list in self.parsed_catalogs.items():
            filtered_sum = 0
            for fp, size in file_list:
                if compiled_regex.match(fp):
                    filtered_sum += size
            self.filtered_dlc_sizes[group_key] = filtered_sum
        for group_key, label_widget in self.dlc_size_labels.items():
            size_bytes = self.filtered_dlc_sizes.get(group_key, 0)
            label_widget.config(text=f"({self.format_size(size_bytes)})")
        total_bytes = 0
        for identifier, var in self.dlc_vars.items():
            if var.get():
                total_bytes += self.filtered_dlc_sizes.get(identifier, 0)
        self.lbl_total_size.config(text=f"Content Selected Size: ~ {self.format_size(total_bytes)}")

    def update_dlc_selection(self, source_dir):
        """Scans source folder for basegame cat files and extensions, generating checkboxes dynamically."""
        for widget in self.dlc_container.winfo_children():
            widget.destroy()
        self.dlc_vars = {}
        self.dlc_size_labels = {}
        self.parsed_catalogs = self.parse_all_catalogs(source_dir)

        classification = self.classify_directory(source_dir)
        if classification not in ("x4_game", "cat_only"):
            self.lbl_total_size.config(text="Content Selected Size: ~ 0 B")
            return

        ego_dlcs = []
        other_dlcs = []

        ext_dir = os.path.join(source_dir, "extensions")
        if os.path.isdir(ext_dir):
            for folder in os.listdir(ext_dir):
                full_path = os.path.join(ext_dir, folder)
                if os.path.isdir(full_path):
                    has_cat = False
                    for r, d, files in os.walk(full_path):
                        if any(f.endswith('.cat') for f in files):
                            has_cat = True
                            break
                    if has_cat:
                        display_name = self.get_extension_display_name(full_path, folder)
                        if folder.lower().startswith("ego_dlc_"):
                            ego_dlcs.append((folder, display_name))
                        else:
                            other_dlcs.append((folder, display_name))

        ego_dlcs.sort(key=lambda s: s[1].lower())
        other_dlcs.sort(key=lambda s: s[1].lower())

        options = []

        has_base_cat = False
        if os.path.exists(source_dir):
            for f in os.listdir(source_dir):
                if f.endswith('.cat') and not f.endswith('_sig.cat'):
                    has_base_cat = True
                    break
        if has_base_cat:
            if classification == "x4_game":
                display_label = "Base Game"
            else:
                folder_name = os.path.basename(os.path.normpath(source_dir))
                if not folder_name:
                    display_label = source_dir
                else:
                    display_label = folder_name
            
            options.append(("base_game", display_label))

        for folder, dname in ego_dlcs:
            options.append((f"extensions/{folder}", dname))

        for folder, dname in other_dlcs:
            options.append((f"extensions/{folder}", dname))
        style = ttk.Style()
        bg_color = style.lookup("TFrame", "background") or "#f0f0f0"
        cols = 3
        for idx, (identifier, display_name) in enumerate(options):
            var = tk.BooleanVar(value=True)
            self.dlc_vars[identifier] = var
            var.trace_add("write", lambda *args: self.recalculate_sizes())
            
            cb = ttk.Checkbutton(self.dlc_container, text=display_name, variable=var)
            lbl_size = tk.Label(self.dlc_container, text="", font=("Segoe UI", 8), fg="#555555", background=bg_color)
            self.dlc_size_labels[identifier] = lbl_size
            
            row = idx // cols
            col_group = idx % cols
            
            cb.grid(row=row, column=col_group * 2, sticky=tk.W, padx=(10, 2), pady=4)
            lbl_size.grid(row=row, column=col_group * 2 + 1, sticky=tk.W, padx=(0, 10), pady=4)
            
        self.recalculate_sizes()

    def clamp_threads(self):
        """Restricts thread configuration input values to valid physical limits."""
        max_threads = os.cpu_count() or 4
        try:
            val = int(self.spin_threads.get())
        except ValueError:
            val = min(4, max_threads)
            
        if val < 1:
            val = 1
        elif val > max_threads:
            val = max_threads
            
        self.spin_threads.set(str(val))

    def show_success_dialog(self, elapsed_time, dest_path):
        """Displays custom success modal window with optional OS explorer shortcut."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Extraction Complete")
        dialog.geometry("400x150")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        p_x = self.root.winfo_rootx()
        p_y = self.root.winfo_rooty()
        p_w = self.root.winfo_width()
        p_h = self.root.winfo_height()
        
        x = p_x + (p_w - 400) // 2
        y = p_y + (p_h - 150) // 2
        dialog.geometry(f"400x150+{x}+{y}")
        
        content_frame = ttk.Frame(dialog, padding="15")
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        msg_label = ttk.Label(
            content_frame, 
            text=f"Extraction completed successfully.\n\nTime taken: {elapsed_time}", 
            font=("Segoe UI", 9),
            justify=tk.CENTER
        )
        msg_label.pack(pady=(10, 15))
        
        btn_frame = ttk.Frame(content_frame)
        btn_frame.pack(fill=tk.X)
        
        def on_ok():
            dialog.destroy()
            
        def on_open():
            dialog.destroy()
            try:
                if sys.platform == 'win32':
                    os.startfile(dest_path)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['open', dest_path])
                else:
                    subprocess.Popen(['xdg-open', dest_path])
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open destination folder:\n{e}")
                
        btn_ok = ttk.Button(btn_frame, text="OK", command=on_ok, width=12)
        btn_ok.pack(side=tk.LEFT, padx=(40, 10), expand=True)
        
        btn_open = ttk.Button(btn_frame, text="Open Folder", command=on_open, width=15)
        btn_open.pack(side=tk.RIGHT, padx=(10, 40), expand=True)

    def show_about_dialog(self):
        """Displays custom about dialog containing general info, disclaimer, and clickable links."""
        dialog = tk.Toplevel(self.root)
        dialog.title("About & Disclaimer")
        dialog.geometry("580x380")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()
        p_x = self.root.winfo_rootx()
        p_y = self.root.winfo_rooty()
        p_w = self.root.winfo_width()
        p_h = self.root.winfo_height()
        
        x = p_x + (p_w - 580) // 2
        y = p_y + (p_h - 380) // 2
        dialog.geometry(f"580x380+{x}+{y}")

        content_frame = ttk.Frame(dialog, padding="15")
        content_frame.pack(fill=tk.BOTH, expand=True)

        description_text = (
            "This utility is not affiliated with, authorized, sponsored, or approved "
            "by Egosoft GmbH. 'X4: Foundations' and 'Egosoft' are trademarks of "
            "Egosoft GmbH. All extracted game assets remain the intellectual property "
            "of Egosoft GmbH.\n\n"
            "This software is provided 'as is', without warranty of any kind, express "
            "or implied. Use at your own risk. The developer is not responsible for "
            "any damage, data loss, or game instability resulting from the use of "
            "this tool or modified files. Please do not contact Egosoft official "
            "support regarding issues arising from the use of this utility"
        )

        lbl_desc = ttk.Label(content_frame, text=description_text, justify=tk.LEFT, wraplength=550)
        lbl_desc.pack(anchor=tk.W, pady=(0, 5))
        links_frame = ttk.Frame(content_frame)
        links_frame.pack(fill=tk.X, anchor=tk.W, pady=5)

        def create_link_row(parent, label_text, url):
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, anchor=tk.W, pady=2)
            
            lbl_title = ttk.Label(row, text=label_text, font=("Segoe UI", 9, "bold"), width=18, anchor=tk.W)
            lbl_title.pack(side=tk.LEFT)
            
            lbl_url = tk.Label(
                row, 
                text=url, 
                fg="#005A9E", 
                cursor="hand2", 
                font=("Segoe UI", 9, "underline"),
                justify=tk.LEFT
            )
            lbl_url.pack(side=tk.LEFT)
            lbl_url.bind("<Button-1>", lambda e: webbrowser.open_new_tab(url))
        create_link_row(links_frame, "Egosoft Discord:", "https://discord.com/invite/J8u6Kdc")
        create_link_row(links_frame, "z1p Nexus X4 mods:", "https://www.nexusmods.com/profile/z1ppeh/mods?gameId=2659")
        create_link_row(links_frame, "z1p Steam X4 mods:", "https://steamcommunity.com/id/z1ppeh/myworkshopfiles/?appid=392160")
        lbl_note = ttk.Label(
            content_frame, 
            text="For questions or feedback, you can message user @z1ppeh on the Egosoft Discord.", 
            font=("Segoe UI", 9, "italic"),
            foreground="#555555"
        )
        lbl_note.pack(anchor=tk.W, pady=(8, 10))

        btn_ok = ttk.Button(content_frame, text="OK", command=dialog.destroy, width=10)
        btn_ok.pack(anchor=tk.E, side=tk.BOTTOM, pady=(5, 0))
    def on_source_selected(self, event=None):
        source_dir = self.combo_source.get().strip()
        classification = self.classify_directory(source_dir)

        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        if classification == "x4_game":
            ver = self.get_game_version(source_dir)
            self.lbl_version.config(text=f"Valid X4 Directory Detected (v{ver})", fg="#7B2CBF")
            
            suggested_out = os.path.join(base_dir, f"X4 unpacked {ver}")
            self.ent_dest.delete(0, tk.END)
            self.ent_dest.insert(0, suggested_out)
            self.update_dlc_selection(source_dir)

        elif classification == "cat_only":
            self.lbl_version.config(text="Cat/Dat Folder Detected", fg="#0078D7")
            
            suggested_out = os.path.join(base_dir, "Cat_Dat unpacked")
            self.ent_dest.delete(0, tk.END)
            self.ent_dest.insert(0, suggested_out)
            self.update_dlc_selection(source_dir)

        else:
            self.lbl_version.config(text="Status: Path does not appear to contain an X4 installation or Cat/Dat files.", fg="#D9534F")
            for widget in self.dlc_container.winfo_children():
                widget.destroy()
            self.dlc_vars = {}

    def browse_source_dir(self):
        dir_selected = filedialog.askdirectory(title="Select X4 Foundations Installation Directory")
        if dir_selected:
            self.combo_source.delete(0, tk.END)
            self.combo_source.insert(0, os.path.normpath(dir_selected))
            self.on_source_selected()

    def browse_dest_dir(self):
        dir_selected = filedialog.askdirectory(title="Select Output Directory")
        if dir_selected:
            self.ent_dest.delete(0, tk.END)
            self.ent_dest.insert(0, os.path.normpath(dir_selected))

    def set_checkboxes_state(self, state):
        for cb in self.checkbox_widgets:
            cb.config(state=state)

    def set_dlc_checkboxes_state(self, state):
        for child in self.dlc_container.winfo_children():
            try:
                child.config(state=state)
            except Exception:
                pass

    def update_regex_from_checkboxes(self):
        if self.filter_var.get() != 4:
            return
        selected = [ext for ext, var in self.ext_vars.items() if var.get()]
        
        self.ent_regex.config(state=tk.NORMAL)
        self.ent_regex.delete(0, tk.END)
        if not selected:
            self.ent_regex.insert(0, "")
        else:
            ext_names = [ext.lstrip('.') for ext in selected]
            regex_str = rf".*\.({'|'.join(ext_names)})$"
            self.ent_regex.insert(0, regex_str)
        self.recalculate_sizes()

    def toggle_regex_state(self):
        choice = self.filter_var.get()
        self.ent_regex.config(state=tk.NORMAL)
        self.ent_regex.delete(0, tk.END)
        
        if choice == 1:
            self.cb_frame.pack_forget()  # Collapse Custom Selection frame
            self.ent_regex.insert(0, r".*\.xml|.*\.xsd|.*\.lua|.*\.xpl|.*\.txt")
            self.ent_regex.config(state=tk.DISABLED)
            self.set_checkboxes_state(tk.DISABLED)
        elif choice == 2:
            self.cb_frame.pack_forget()  # Collapse Custom Selection frame
            self.ent_regex.insert(0, r".*")
            self.ent_regex.config(state=tk.DISABLED)
            self.set_checkboxes_state(tk.DISABLED)
        elif choice == 3:
            self.cb_frame.pack_forget()  # Collapse Custom Selection frame
            self.ent_regex.insert(0, r"^(?!.*\.(wav|ogg|xwma)$).*$")
            self.ent_regex.config(state=tk.DISABLED)
            self.set_checkboxes_state(tk.DISABLED)
        elif choice == 4:
            self.cb_frame.pack(fill=tk.X, pady=(5, 5), after=self.radio_custom.master)
            self.set_checkboxes_state(tk.NORMAL)
            self.update_regex_from_checkboxes()
            self.ent_regex.focus()
            
        self.recalculate_sizes()
    def log(self, text):
        self.log_widget.config(state=tk.NORMAL)
        self.log_widget.insert(tk.END, text + "\n")
        if self.autoscroll_var.get():
            self.log_widget.see(tk.END)
        self.log_widget.config(state=tk.DISABLED)
    def process_queue(self):
        try:
            while True:
                msg, data = self.get_from_queue_non_blocking()
                if not msg:
                    break
                
                if msg == "detection_done":
                    if data:
                        self.combo_source['values'] = data
                        self.combo_source.set(data[0])
                        self.on_source_selected()
                    else:
                        self.lbl_version.config(text="Status: No default installations auto-detected. Please browse manually.", fg="#D9534F")
                
                elif msg == "log":
                    self.log(data)
                
                elif msg == "progress_init":
                    self.progress_bar["maximum"] = data
                    self.progress_bar["value"] = 0
                    self.lbl_stats.config(text="Extraction starting...")
                
                elif msg == "progress_update":
                    processed, pct, speed, eta = data
                    self.progress_bar["value"] = processed
                    
                    if eta > 60:
                        eta_str = f"{int(eta // 60)}m {int(eta % 60)}s"
                    else:
                        eta_str = f"{eta:.1f}s"
                    
                    stats_text = (
                        f"Extracting: {processed}/{self.progress_bar['maximum']} ({pct:.1f}%) | "
                        f"Speed: {speed:.1f} files/sec | "
                        f"ETA: {eta_str}"
                    )
                    self.lbl_stats.config(text=stats_text)
                
                elif msg == "error":
                    messagebox.showerror("Error", data)
                    self.reset_ui_state()
                    
                elif msg == "done":
                    if data == "Cancelled":
                        messagebox.showwarning("Cancelled", "Extraction was cancelled.")
                        self.lbl_stats.config(text="Extraction cancelled by user.")
                    else:
                        self.progress_bar["value"] = self.progress_bar["maximum"]
                        self.show_success_dialog(data, self.ent_dest.get().strip())
                    self.reset_ui_state()
        finally:
            self.root.after(100, self.process_queue)

    def get_from_queue_non_blocking(self):
        try:
            return self.queue.get_nowait()
        except queue.Empty:
            return None, None

    def reset_ui_state(self):
        self.is_running = False
        self.btn_start.config(
            state=tk.NORMAL, 
            text="Start Extraction", 
            command=self.start_extraction,
            bg="#0078D7", 
            activebackground="#005A9E",
            fg="white"
        )
        self.combo_source.config(state=tk.NORMAL)
        self.ent_dest.config(state=tk.NORMAL)
        self.spin_threads.config(state=tk.NORMAL)
        self.cb_overwrite.config(state=tk.NORMAL)
        self.cb_copy_content.config(state=tk.NORMAL)
        self.set_dlc_checkboxes_state(tk.NORMAL)
        self.progress_bar.configure(style="Horizontal.TProgressbar")
        
        if self.filter_var.get() == 4:
            self.set_checkboxes_state(tk.NORMAL)
        else:
            self.set_checkboxes_state(tk.DISABLED)
    def start_extraction(self):
        if self.is_running:
            return
        
        source = self.combo_source.get().strip()
        dest = self.ent_dest.get().strip()
        regex_filter = self.ent_regex.get().strip()
        self.clamp_threads()
        try:
            threads = int(self.spin_threads.get())
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid thread count.")
            return

        if not self.is_valid_x4_dir(source):
            messagebox.showerror("Error", "The specified source path does not contain valid X4 files or Cat/Dat archives.")
            return

        if not dest:
            messagebox.showerror("Error", "Please select or type an output directory.")
            return

        active_content = {identifier for identifier, var in self.dlc_vars.items() if var.get()}
        if not active_content:
            messagebox.showerror("Error", "Please select at least one content item (Base Game or DLC) to unpack.")
            return

        filter_choice = self.filter_var.get()
        filter_names = {
            1: "Standard text files (xml, xsd, lua, xpl, txt)",
            2: "Full Unpack",
            3: "Full unpack - No Sound",
            4: "Custom selection"
        }
        filter_name = filter_names.get(filter_choice, "Unknown profile")

        self.is_running = True
        self.cancel_event.clear()
        self.progress_bar.configure(style="Green.Horizontal.TProgressbar")
        
        self.btn_start.config(
            text="Cancel Extraction", 
            command=self.cancel_extraction,
            bg="#D9534F",
            activebackground="#C9302C",
            fg="white"
        )
        self.combo_source.config(state=tk.DISABLED)
        self.ent_dest.config(state=tk.DISABLED)
        self.spin_threads.config(state=tk.DISABLED)
        self.cb_overwrite.config(state=tk.DISABLED)
        self.cb_copy_content.config(state=tk.DISABLED)
        self.set_checkboxes_state(tk.DISABLED)
        self.set_dlc_checkboxes_state(tk.DISABLED)
        self.progress_bar["value"] = 0

        threading.Thread(
            target=self.run_unpacking_thread,
            args=(source, dest, regex_filter, threads, self.overwrite_var.get(), self.copy_content_var.get(), filter_name, active_content),
            daemon=True
        ).start()

    def cancel_extraction(self):
        self.cancel_event.set()
        self.btn_start.config(state=tk.DISABLED, text="Cancelling...", bg="#CCCCCC", fg="#666666")

    def run_unpacking_thread(self, source, dest, regex_filter, threads, force_overwrite, copy_content_xml, filter_name, active_content):
        self.queue.put(("log", "\nExtraction Starting..."))
        self.queue.put(("log", f"Filter Profile: {filter_name}"))
        self.queue.put(("log", f"Target Folder:  {dest}"))
        self.queue.put(("log", "Starting catalog analysis..."))
        start_time = time.perf_counter()

        if self.cancel_event.is_set():
            self.queue.put(("log", "Extraction aborted by user."))
            self.queue.put(("done", "Cancelled"))
            return

        cat_files = []
        for root, dirs, files in os.walk(source):
            for f in files:
                if f.endswith('.cat') and not f.endswith('_sig.cat'):
                    full_cat_path = os.path.join(root, f)
                    rel_dir = os.path.relpath(root, source).replace('\\', '/')
                    
                    if rel_dir == '.':
                        group_key = "base_game"
                    else:
                        parts = rel_dir.split('/')
                        if len(parts) >= 2 and parts[0] == "extensions":
                            group_key = f"extensions/{parts[1]}"
                        else:
                            group_key = "unknown"
                            
                    if group_key in active_content:
                        cat_files.append(full_cat_path)

        if not cat_files:
            self.queue.put(("error", "Could not locate any game .cat archives to extract for the selected content."))
            return

        base_path = source.replace('\\', '/').rstrip('/')
        base_depth = base_path.count('/')
        cat_files.sort(key=lambda f: (f.replace('\\', '/').rstrip('/').count('/') - base_depth, f))

        catalog = {}
        ignored_deletions = 0
        total_parsed = 0

        self.queue.put(("log", f"Parsing {len(cat_files)} archive file headers..."))

        for cat_path in cat_files:
            if self.cancel_event.is_set():
                self.queue.put(("log", "Extraction aborted by user."))
                self.queue.put(("done", "Cancelled"))
                return
                
            dat_path = cat_path[:-4] + '.dat'
            cat_name = os.path.basename(cat_path)
            cum_offset = 0

            rel_dir = os.path.relpath(os.path.dirname(cat_path), source).replace('\\', '/')
            if rel_dir == '.':
                rel_dir = ""

            try:
                with open(cat_path, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        parts = line.split()
                        if len(parts) < 4:
                            continue

                        size_str = parts[-3]
                        fp = " ".join(parts[:-3]).replace('\\', '/').lower()
                        while fp.startswith('./'): fp = fp[2:]
                        while fp.startswith('/'): fp = fp[1:]

                        if rel_dir:
                            fp = f"{rel_dir}/{fp}"

                        try:
                            size = int(size_str)
                        except ValueError:
                            continue

                        total_parsed += 1

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
                self.queue.put(("log", f"Warning: Access issue on {cat_name}: {e}"))

        matched_files = []
        try:
            compiled_regex = re.compile(regex_filter, re.IGNORECASE)
            for fp, info in catalog.items():
                if compiled_regex.match(fp):
                    matched_files.append((fp, info))
        except Exception as e:
            self.queue.put(("error", f"Invalid Regular Expression pattern:\n{e}"))
            return

        matched_files.sort(key=lambda x: x[0])

        self.queue.put(("log", f"Headers Parsed: {total_parsed} (Skipped {ignored_deletions} patch deletions)"))
        self.queue.put(("log", f"Target match list size: {len(matched_files)} files to extract."))

        if not matched_files:
            self.queue.put(("log", "No target files matched selection criteria. Stopping."))
            self.queue.put(("done", "0.0 seconds"))
            return

        os.makedirs(dest, exist_ok=True)
        jobs = [(fp, info, dest, force_overwrite, self.cancel_event) for fp, info in matched_files]
        total_jobs = len(jobs)

        self.queue.put(("progress_init", total_jobs))
        self.queue.put(("log", f"Extracting files using {threads} parallel worker processes..."))

        extracted = 0
        skipped = 0
        errors = 0
        cancelled = False

        extraction_start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures = [executor.submit(self.extract_worker, job) for job in jobs]

            for future in as_completed(futures):
                if self.cancel_event.is_set():
                    cancelled = True
                    break
                    
                success, reason = future.result()
                if success:
                    extracted += 1
                elif reason == "skipped":
                    skipped += 1
                elif reason == "cancelled":
                    pass
                else:
                    errors += 1

                processed = extracted + skipped + errors
                if processed % max(1, (total_jobs // 100)) == 0 or processed == total_jobs:
                    elapsed = time.perf_counter() - extraction_start
                    speed = processed / elapsed if elapsed > 0 else 0
                    remaining_jobs = total_jobs - processed
                    box_eta = remaining_jobs / speed if speed > 0 else 0
                    
                    pct = (processed / total_jobs) * 100
                    
                    self.queue.put(("progress_update", (processed, pct, speed, box_eta)))

        if cancelled:
            self.queue.put(("log", "\nJob aborted by user."))
            self.queue.put(("done", "Cancelled"))
            return

        if copy_content_xml and not cancelled:
            self.queue.put(("log", "Copying content.xml files for selected extensions..."))
            copied_xml_count = 0
            for identifier in active_content:
                if identifier.startswith("extensions/"):
                    src_xml = os.path.join(source, identifier, "content.xml")
                    if os.path.exists(src_xml):
                        dest_xml = os.path.normpath(os.path.join(dest, identifier, "content.xml"))
                        if not os.path.exists(dest_xml) or force_overwrite:
                            try:
                                os.makedirs(os.path.dirname(dest_xml), exist_ok=True)
                                shutil.copy2(src_xml, dest_xml)
                                copied_xml_count += 1
                            except Exception as e:
                                self.queue.put(("log", f"Warning: Failed to copy {src_xml} to {dest_xml}: {e}"))
            if copied_xml_count > 0:
                self.queue.put(("log", f"Copied {copied_xml_count} content.xml file(s) to output directories."))

        elapsed = time.perf_counter() - start_time
        if elapsed > 60:
            time_str = f"{int(elapsed // 60)}m {elapsed % 60:.2f}s"
        else:
            time_str = f"{elapsed:.2f} seconds"

        self.queue.put(("log", f"\nJob Completed in {time_str}."))
        self.queue.put(("log", f"Successful Extractions: {extracted}"))
        self.queue.put(("log", f"Unchanged Files Skipped: {skipped}"))
        self.queue.put(("log", f"Encountered Errors: {errors}"))

        self.queue.put(("done", time_str))

    @staticmethod
    def extract_worker(job):
        fp, info, dest_dir, force, cancel_event = job
        if cancel_event.is_set():
            return False, "cancelled"
            
        size = info['size']
        out_path = os.path.normpath(os.path.join(dest_dir, fp))

        if os.path.exists(out_path) and not force:
            return False, "skipped"

        try:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(info['dat'], 'rb') as d_file:
                d_file.seek(info['offset'])
                data = d_file.read(size)

            with open(out_path, 'wb') as out_file:
                out_file.write(data)
            return True, "success"
        except Exception as e:
            return False, f"error: {e}"


if __name__ == '__main__':
    if HAS_TTKTHEMES:
        root = ThemedTk(theme="smog")
    else:
        root = tk.Tk()
        
    app = X4UnpackerGUI(root)
    root.mainloop()