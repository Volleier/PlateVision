import os, sys
from PIL import Image

root = r"data/training"
img_sets = {
    "train": os.path.join(root, "images", "train"),
    "val":   os.path.join(root, "images", "val"),
}
label_dirs = {
    "train": os.path.join(root, "labels", "train"),
    "val":   os.path.join(root, "labels", "val"),
}

bad_images = []
missing_labels = []

def check_image(path):
    try:
        with Image.open(path) as im:
            im.verify()
        return True
    except Exception as e:
        return str(e)

for split, img_dir in img_sets.items():
    if not os.path.isdir(img_dir):
        print(f"Missing image dir: {img_dir}")
        sys.exit(1)
    for fn in os.listdir(img_dir):
        if not fn.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        img_path = os.path.join(img_dir, fn)
        r = check_image(img_path)
        if r is not True:
            bad_images.append((img_path, r))
        lbl_name = os.path.splitext(fn)[0] + ".txt"
        lbl_path = os.path.join(label_dirs[split], lbl_name)
        if not os.path.isfile(lbl_path):
            missing_labels.append((img_path, lbl_path))

print("Summary:")
print(f"  checked splits: {list(img_sets.keys())}")
print(f"  bad images: {len(bad_images)}")
print(f"  missing labels: {len(missing_labels)}")
if bad_images:
    print("\nBad images (path, error):")
    for p,e in bad_images[:50]:
        print(p, "->", e)
if missing_labels:
    print("\nMissing label files (image, expected label):")
    for p,l in missing_labels[:50]:
        print(p, "->", l)

if bad_images or missing_labels:
    sys.exit(1)
else:
    print("No obvious data errors detected.")
    sys.exit(0)