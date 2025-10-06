"""Convert Pascal VOC XML annotations to YOLO txt format.

Usage:
  python backend/voc_to_yolo.py --images data/training/images --labels data/training/labels --output-classes data/training/classes.txt

This script will scan for .xml files under the labels subfolders (train/val) and create corresponding .txt files
with YOLO format: class x_center y_center width height (normalized).
It will also produce a classes file listing class names (one per line) if not provided.
"""
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import OrderedDict
import sys


def parse_args():
    p = argparse.ArgumentParser(description="Convert VOC XML to YOLO txt format")
    p.add_argument("--images", default="data/training/images", help="root images folder (contains train/ val)")
    p.add_argument("--labels", default="data/training/labels", help="root labels folder containing VOC XMLs (train/ val)")
    p.add_argument("--output-classes", default="data/training/classes.txt", help="path to write classes.txt (one name per line)")
    p.add_argument("--create-empty", action="store_true", help="create empty txt for images without boxes")
    return p.parse_args()


def voc_to_yolo(xml_path: Path, img_size=None):
    """Parse a single VOC xml and return list of yolo lines and image size.
    yolo line: (name, x_center, y_center, width, height) normalized
    """
    tree = ET.parse(str(xml_path))
    root = tree.getroot()
    size = root.find('size')
    if size is not None:
        width_elem = size.find('width')
        height_elem = size.find('height')
        if width_elem is None or width_elem.text is None or height_elem is None or height_elem.text is None:
            raise ValueError(f'Missing width or height in xml: {xml_path}')
        width = int(width_elem.text)
        height = int(height_elem.text)
    else:
        # fallback to provided img_size
        if img_size is None:
            raise ValueError(f'No size in xml and no img_size provided for {xml_path}')
        width, height = img_size

    yolo_lines = []
    for obj in root.findall('object'):
        name_elem = obj.find('name')
        bnd = obj.find('bndbox')
        if name_elem is None or name_elem.text is None:
            raise ValueError(f'Missing object name in xml: {xml_path}')
        if bnd is None:
            raise ValueError(f'Missing bndbox in xml: {xml_path}')
        xmin_elem = bnd.find('xmin')
        ymin_elem = bnd.find('ymin')
        xmax_elem = bnd.find('xmax')
        ymax_elem = bnd.find('ymax')
        if (xmin_elem is None or xmin_elem.text is None or
            ymin_elem is None or ymin_elem.text is None or
            xmax_elem is None or xmax_elem.text is None or
            ymax_elem is None or ymax_elem.text is None):
            raise ValueError(f'Missing bounding box values in xml: {xml_path}')
        name = name_elem.text
        xmin = float(xmin_elem.text)
        ymin = float(ymin_elem.text)
        xmax = float(xmax_elem.text)
        ymax = float(ymax_elem.text)
        # convert to x_center, y_center, w, h (normalized)
        x_center = ((xmin + xmax) / 2.0) / width
        y_center = ((ymin + ymax) / 2.0) / height
        w = (xmax - xmin) / width
        h = (ymax - ymin) / height
        yolo_lines.append((name, x_center, y_center, w, h))
    return yolo_lines, (width, height)


def main():
    args = parse_args()
    images_root = Path(args.images)
    labels_root = Path(args.labels)

    if not labels_root.exists():
        print(f'Labels folder not found: {labels_root}', file=sys.stderr)
        sys.exit(1)

    # gather class names in order of appearance
    class_order = OrderedDict()
    total_xml = 0
    total_converted = 0
    for split in ['train', 'val']:
        xml_dir = labels_root / split
        if not xml_dir.exists():
            continue
        for xml in xml_dir.rglob('*.xml'):
            total_xml += 1
            try:
                yolo_lines, _ = voc_to_yolo(xml)
            except Exception as e:
                print(f'Failed to parse {xml}: {e}', file=sys.stderr)
                continue
            if not yolo_lines:
                # no objects
                if args.create_empty:
                    txt_path = xml.with_suffix('.txt')
                    txt_path.parent.mkdir(parents=True, exist_ok=True)
                    txt_path.write_text('')
                continue
            # map names to indices
            for name, *rest in yolo_lines:
                if name not in class_order:
                    class_order[name] = len(class_order)
            # write txt
            txt_path = xml.with_suffix('.txt')
            txt_path.parent.mkdir(parents=True, exist_ok=True)
            lines = []
            for name, x, y, w, h in yolo_lines:
                idx = class_order[name]
                lines.append(f"{idx} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")
            txt_path.write_text('\n'.join(lines))
            total_converted += 1

    # write classes file if requested
    if args.output_classes:
        outp = Path(args.output_classes)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text('\n'.join(class_order.keys()))

    print(f'Total xml scanned: {total_xml}, converted: {total_converted}, classes: {len(class_order)}')
    if class_order:
        print('Classes (index -> name):')
        for name, idx in class_order.items():
            print(f'{idx} -> {name}')


if __name__ == '__main__':
    main()
