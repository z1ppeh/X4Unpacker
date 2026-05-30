** X4 Foundations Cat/Dat Unpacker Suite (UNOFFICIAL) **

The X4 Foundations Cat/Dat Unpacker Suite consists of two tools designed to list
and extract assets from the .cat/.dat archive format used by X4: Foundations:

1.  X4unpackerGUI.exe — A graphical application featuring content selection,
    dynamic size calculation, preset filters, and progress tracking.
2.  X4unpackerCLI.exe — A command-line utility with both an interactive setup
    wizard and arguments for automation or batch script workflows.

Both applications automatically ignore catalog signature files (_sig.cat) and
correctly resolve patch overrides across base game and expansion folders.

** GUI Edition (X4unpackerGUI) **

If you prefer a visual interface, double-click X4unpackerGUI.exe. The interface
provides the following features:

  - Directory Detection: Scans standard Steam, GOG, Epic Games installation
    paths, and registry keys to locate the game folder automatically.
  - Content Selector: Lists the Base Game alongside individual DLCs or user
    extensions and allows you to select exactly which packages to extract.
  - Size Estimation: Displays the storage requirements for your selected content
    in real time as you adjust your selection or filter settings.
  - Profile Filters: Includes predefined filter profiles (Standard text files,
    Full Unpack, Full Unpack without Sound) as well as a multi-selection check
    list for specific extensions and raw Regex input.
  - Operations Log & Progress: Features a scrollable execution log, transfer
    speed indicator, progress bar, and an estimated time of completion.
  - Additional Options: Permits thread-count limits, forced overwrites, and
    automatic copying of the content.xml file for active expansions.

** CLI Interactive Wizard (X4unpackerCLI) **

If you run X4unpackerCLI.exe with no arguments, it launches an interactive
text-based wizard in your terminal to guide you through the process
step-by-step.

The wizard will:

  - Auto-detect X4 installations or prompt for a manual directory path.
  - Suggest a default output directory named "X4 unpacked " in the folder where
    the tool is running.
  - Provide selection filters: [1] Standard text files only (xml, xsd, lua, xpl,
    txt) - Recommended [2] ALL files (models, sounds, textures, etc.) [3] Manual
    entry using custom Regex patterns (e.g. ..xml|..lua)
  - Configure the extraction thread count.
  - Prompt for skip or overwrite behavior for pre-existing files.

The wizard operates in "all_folders" mode, scanning the entire game directory
including any extensions.

** CLI Command Line Syntax **

For automated scripting, modding setups, or targeted extractions, you can bypass
the wizard by running X4unpackerCLI.exe with arguments:

X4unpackerCLI.exe [OPTIONS]     [<dest_dir>]

** Positional Arguments **

mode file - Process only the specific .cat file(s) specified in source. folder -
Process .cat files only in the root of the source directory. all_folders -
Search and process .cat files in the source directory and all subdirectories
(including DLCs under extensions/).

source Path to the specific file or directory containing the .cat/.dat archives.

command x - Extract the matched files to dest_dir. ls - List matched files and
their sizes without extracting them (ignores dest_dir).

filter Either a glob mask or a path prefix to filter which files inside the
catalogs are processed.

Glob mask examples (wildcard-based):
  *.xml                  matches all .xml files anywhere
  assets/textures/*.xml  matches .xml files in that specific path

Path prefix example (no wildcard):
  assets/textures        matches everything under that folder

Note: Command line mode uses glob/prefix filtering. For regex support, 
use either the interactive console wizard or the GUI application.

dest_dir The output folder where files will be extracted. (Required for x,
ignored for ls).

** Options **

-t, --threads  The number of worker threads to use during extraction.
(Default: 4). Recommended: 1-2 for mechanical HDDs 4-6 for standard SATA SSDs 8+
for high-speed NVMe drives

-f, --force Forces the unpacker to overwrite files in the destination directory
if they already exist. By default, existing files are skipped to save time if
resuming a previous run.

** Examples **

1.  List Files (Without Extracting) To see all .xml files in the root catalogs
    without writing anything to disk:

    X4unpackerCLI.exe folder "C:\Program Files (x86)\Steam\steamapps\common\X4
    Foundations" ls "*.xml"

2.  Extract Specific Files from a Single Catalog To extract only .lua files
    from 01.cat to a temporary directory:

    X4unpackerCLI.exe file "C:\Program Files (x86)\Steam\steamapps\common\X4
    Foundations\01.cat" x "*.lua" "C:\X4_Unpacked"

3.  Unpack Standard Modding Files (Base Game + DLCs) To extract all .xml files
    from the entire game directory, including extensions, using 8 threads:

    X4unpackerCLI.exe all_folders "C:\Program Files
    (x86)\Steam\steamapps\common\X4 Foundations" x "*.xml" "C:\X4_Unpacked"
    --threads 8

4.  Extract Everything Under a Specific Path To extract all files under the
    assets/units folder:

    X4unpackerCLI.exe all_folders "C:\Program Files
    (x86)\Steam\steamapps\common\X4 Foundations" x "assets/units"
    "C:\X4_Unpacked"

** How Overrides Are Handled **

The utility processes .cat files sequentially. If a file (e.g.,
libraries/material_library.xml) exists in both 01.cat and a later update catalog
like 09.cat, the index pointing to the older file in 01.cat is replaced. When
extracting, only the newest version from 09.cat is written to the output folder.
Zero-byte entries (representing patch deletions) are recognized and skipped
automatically.

** DISCLAIMER **

This utility is not affiliated with, authorized, sponsored, or approved by
Egosoft GmbH. 'X4: Foundations' and 'Egosoft' are trademarks of Egosoft GmbH.
All extracted game assets remain the intellectual property of Egosoft GmbH.

This software is provided 'as is', without warranty of any kind, express or
implied. Use at your own risk. The developer is not responsible for any damage,
data loss, or game instability resulting from the use of this tool or modified
files. Please do not contact Egosoft official support regarding issues arising
from the use of this utility.
