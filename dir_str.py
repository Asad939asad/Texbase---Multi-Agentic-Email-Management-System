from pathlib import Path

def print_directory_tree(start_path, allowed_extensions=('.py', '.tsx', '.db')):
    """
    Prints a directory tree structure for a single path, filtered by extensions.
    """
    start_path = Path(start_path).resolve()
    
    # Check if the folder actually exists before trying to scan it
    if not start_path.exists() or not start_path.is_dir():
        print(f"❌ Error: Directory not found or is not a folder -> {start_path}")
        return

    # Helper function to check if a directory contains any relevant files
    def has_relevant_files(dir_path):
        for ext in allowed_extensions:
            try:
                next(dir_path.rglob(f"*{ext}"))
                return True
            except StopIteration:
                continue
        return False

    def _print_tree(current_path, prefix=""):
        entries = [e for e in current_path.iterdir() if not e.name.startswith('.')]
        entries.sort(key=lambda x: (x.is_file(), x.name.lower()))
        
        valid_entries = []
        for entry in entries:
            if entry.is_dir():
                if has_relevant_files(entry):
                    valid_entries.append(entry)
            elif entry.is_file() and entry.suffix in allowed_extensions:
                valid_entries.append(entry)
                
        for i, entry in enumerate(valid_entries):
            is_last = (i == len(valid_entries) - 1)
            connector = "└── " if is_last else "├── "
            
            print(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            
            if entry.is_dir():
                extension_prefix = "    " if is_last else "│   "
                _print_tree(entry, prefix=prefix + extension_prefix)

    print(f"📁 {start_path.name}/")
    _print_tree(start_path)


def process_multiple_folders(folder_list, allowed_extensions=('.py', '.tsx', '.db')):
    """
    Loops through a list of folders and prints the tree for each one.
    """
    for folder in folder_list:
        print(f"\n{'=' * 60}")
        print(f"🌲 Tree Structure for: {folder}")
        print(f"{'=' * 60}")
        print_directory_tree(folder, allowed_extensions)


if __name__ == "__main__":
    # 🎯 Provide your list of folder paths here
    # You can use absolute paths (C:/... or /Users/...) or relative paths (./...)
    folders_to_scan = [
        "AgenticControl",                  # Scans the current directory
        "backend", # Example of a relative path
        "frontend",  # Example of an absolute path (Windows)
        "Excel_Generator"
    ]
    
    process_multiple_folders(folders_to_scan)