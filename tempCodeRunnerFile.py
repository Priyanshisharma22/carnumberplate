# train_yolov8_licenseplate_gpu_ready.py
import os
import torch
from ultralytics import YOLO

# -----------------------------
# 1️⃣ Check GPU availability
# -----------------------------
print("🔍 Checking GPU availability...")
if torch.cuda.is_available():
    device = "cuda"
    print(f"✅ GPU detected: {torch.cuda.get_device_name(0)}")
else:
    device = "cpu"
    print("⚠️ GPU not detected. Training will use CPU.")

# -----------------------------
# 2️⃣ Setup paths
# -----------------------------
HOME = r"C:\carnumberplate-main"
DATASET_PATH = os.path.join(HOME, "freedomown")
IMAGES_PATH = os.path.join(DATASET_PATH, "images")

# -----------------------------
# 3️⃣ Detect train/val folders
# -----------------------------
def find_folder(possible_names):
    for name in possible_names:
        path = os.path.join(IMAGES_PATH, name)
        if os.path.exists(path):
            return path
    return None

train_folder = find_folder(['train', 'training', 'trainining'])
val_folder = find_folder(['val', 'validation'])

if not train_folder or not val_folder:
    raise FileNotFoundError(f"Training or validation folder not found in {IMAGES_PATH}.\n"
                            f"Detected train: {train_folder}\nDetected val: {val_folder}")

print(f"✅ Training folder: {train_folder}")
print(f"✅ Validation folder: {val_folder}")

# -----------------------------
# 4️⃣ Create data.yaml dynamically
# -----------------------------
DATA_YAML_PATH = os.path.join(DATASET_PATH, "data.yaml")

data_yaml_content = f"""train: {train_folder}
val: {val_folder}

nc: 1
names: ['licenceplate']
"""

with open(DATA_YAML_PATH, "w") as f:
    f.write(data_yaml_content)

print(f"✅ data.yaml created at: {DATA_YAML_PATH}")

# -----------------------------
# 5️⃣ Load YOLOv8 model
# -----------------------------
model = YOLO("yolov8s.pt")  # small model

# -----------------------------
# 6️⃣ Move model to GPU if available
# -----------------------------
if device == "cuda":
    model.to("cuda")
    print("✅ Model moved to GPU")

# -----------------------------
# 7️⃣ Train the model
# -----------------------------
model.train(
    data=DATA_YAML_PATH,
    epochs=30,
    imgsz=800,
    batch=8,
    device=device,
    project=os.path.join(HOME, "runs"),
    name="licenceplate_train_gpu",
)

print("🎯 Training completed successfully!")
