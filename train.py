from ultralytics import YOLO

def main():
    # -----------------------------
    # 1️⃣ Set dataset and model paths
    # -----------------------------
    DATA_YAML = r"C:\carnumberplate-main\freedomown\data.yaml"  # path to your dataset YAML
    MODEL = "yolov8s.pt"  # you can also try yolov8n.pt or yolov8m.pt

    # -----------------------------
    # 2️⃣ Create YOLO model instance
    # -----------------------------
    model = YOLO(MODEL)

    # -----------------------------
    # 3️⃣ Start training
    # -----------------------------
    results = model.train(
        data=DATA_YAML,        # path to data.yaml
        epochs=30,             # number of epochs
        imgsz=640,             # image size
        batch=4,               # batch size
        device=0,              # use GPU
        name="freedomown_yolov8",  # name for run folder
        project=r"C:\carnumberplate-main\runs",  # save directory
        pretrained=True,       # use pretrained weights
        workers=0,             # ⚠️ Important: Set to 0 on Windows to avoid multiprocessing crash
        patience=30,           # early stopping
        verbose=True,
        plots=True
    )

    print("✅ Training complete!")

# ✅ Windows-safe entry point
if __name__ == "__main__":
    main()
