import os
import subprocess
import sys


def add_gitkeep_to_empty_dirs(root):
    for current_path, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        if current_path == root:
            continue
        real_files = [f for f in files if f != ".gitkeep"]
        if not real_files and not dirs:
            keep_file = os.path.join(current_path, ".gitkeep")
            if not os.path.exists(keep_file):
                with open(keep_file, "w") as f:
                    f.write("")
                print(f"[gitkeep] added: {keep_file}")
            else:
                print(f"[gitkeep] exists: {keep_file}")


def ensure_init_files(root):
    for current_path, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        if "__init__.py" not in files and any(d for d in dirs):
            init_file = os.path.join(current_path, "__init__.py")
            with open(init_file, "w") as f:
                f.write("")
            print(f"[init] created: {init_file}")


def run_black():
    try:
        subprocess.run(["black", "."], check=True)
        print("[format] Applied black formatting")
    except Exception:
        print("[warn] black not installed")


def main():
    root = os.path.abspath(".")
    print(f"\n🔧 Running hygiene checks for: {root}\n")

    add_gitkeep_to_empty_dirs(root)
    ensure_init_files(root)
    run_black()

    print("\n✨ Hygiene check complete.\n")


if __name__ == "__main__":
    main()
