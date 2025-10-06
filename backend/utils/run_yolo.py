# python
import os

# Temporarily allow duplicate OpenMP libraries (not recommended for long-term use), must be set before any imports
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Optional: Limit the number of threads to avoid issues caused by excessive parallelism
os.environ["OMP_NUM_THREADS"] = "1"

import torch
from ultralytics import YOLO

print("CUDA available:", torch.cuda.is_available())
print("GPU count:", torch.cuda.device_count())
if torch.cuda.is_available():
    print("GPU name:", torch.cuda.get_device_name(0))


# Load model (local .pt file)
model = YOLO("backend/static/models/best.pt")

# New: View model class mapping
try:
    names = model.names  # ultralytics usually exposes names (dict or list)
except Exception:
    names = None
print("Model class names:", names)

# Find possible plate class indices (name contains 'plate' or 'license')
plate_idxs = []
if isinstance(names, dict):
    plate_idxs = [i for i, n in names.items() if isinstance(n, str) and ('plate' in n.lower() or 'license' in n.lower())]
elif isinstance(names, (list, tuple)):
    plate_idxs = [i for i, n in enumerate(names) if isinstance(n, str) and ('plate' in n.lower() or 'license' in n.lower())]

print("Detected plate class indices:", plate_idxs)

# Unified device configuration ("cpu" or 0)
device = 0 if torch.cuda.is_available() else "cpu"

# If plate class indices are found, use the classes parameter to detect only plates
if plate_idxs:
    results = model.predict(source="data/test_images", device=device, save=True, classes=plate_idxs, conf=0.25)
else:
    # No plate class found, the model may not be trained for plates; need to change weights or retrain
    print("No plate class found in model.names — the model likely isn't trained for plates.")
    results = model.predict(source="data/test_images", device=device, save=True, conf=0.25)

for r in results:
    print(r.path)
    if hasattr(r, 'boxes') and r.boxes is not None:
        print(r.boxes.xyxy, r.boxes.conf)