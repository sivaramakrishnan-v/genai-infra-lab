import os

def print_tree(start_path, prefix=""):
    items = sorted(os.listdir(start_path))
    pointers = {
        "tee": "├── ",
        "last": "└── ",
        "pipe": "│   ",
        "space": "    ",
    }

    for index, item in enumerate(items):
        path = os.path.join(start_path, item)
        is_last = index == len(items) - 1

        pointer = pointers["last"] if is_last else pointers["tee"]
        print(prefix + pointer + item)

        if os.path.isdir(path):
            extension = pointers["space"] if is_last else pointers["pipe"]
            print_tree(path, prefix + extension)

# Run it
if __name__ == "__main__":
    print_tree(".")
