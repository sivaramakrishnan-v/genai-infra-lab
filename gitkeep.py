import os


def add_gitkeep_to_empty_dirs(root: str):
    """
    Traverse all subdirectories starting at 'root'.
    If a directory is empty or contains ONLY other directories,
    add a .gitkeep file so Git will track it.
    """

    for current_path, dirs, files in os.walk(root):
        # Skip the root folder itself if you don't want .gitkeep there
        if current_path == root:
            continue

        # Check if directory contains any non-gitkeep files
        real_files = [f for f in files if f != ".gitkeep"]

        # If no real files AND no subfolders → empty folder
        if not real_files and not dirs:
            gitkeep_path = os.path.join(current_path, ".gitkeep")

            if not os.path.exists(gitkeep_path):
                with open(gitkeep_path, "w") as f:
                    f.write("")  # create empty gitkeep
                print(f"[added] {gitkeep_path}")
            else:
                print(f"[exists] {gitkeep_path}")

        else:
            print(f"[skip]  {current_path} (contains files/subdirs)")


if __name__ == "__main__":
    root_dir = os.path.abspath(".")
    print(f"\n🔍 Scanning: {root_dir}")
    add_gitkeep_to_empty_dirs(root_dir)
    print("\n✨ Completed.\n")
