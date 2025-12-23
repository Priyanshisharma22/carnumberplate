import cv2
import pytesseract
import pandas as pd
import numpy as np
import os
import re
import torch
from datetime import datetime
from ultralytics import YOLO  # ✅ Ultralytics YOLOv8–v12 models

# --------------------------
# CONFIGURATION
# --------------------------
CSV_PATH = "plate_log.csv"
PLATE_SAVE_DIR = "plates_captured"
MODEL_PATH = r"C:/carnumberplate-main/numberplate_training_960_12n2.pt"

# Path to your Tesseract executable
pytesseract.pytesseract.tesseract_cmd = r"C:/Program Files/Tesseract-OCR/tesseract.exe"

# Create folder for saving cropped plates
os.makedirs(PLATE_SAVE_DIR, exist_ok=True)

# --------------------------
# LOAD YOLO MODEL (GPU ENABLED)
# --------------------------
print("[INFO] Loading YOLOv8/YOLOv12 model...")

model = YOLO(MODEL_PATH)

if torch.cuda.is_available():
    model.to('cuda')
    device_name = torch.cuda.get_device_name(0)
    print(f"[INFO] Model loaded on GPU: {device_name}")
else:
    model.to('cpu')
    print("[WARNING] CUDA not available. Using CPU (slower).")

print("[INFO] Model loaded successfully!")

# --------------------------
# CREATE CSV IF NOT EXISTS
# --------------------------
if not os.path.exists(CSV_PATH) or os.stat(CSV_PATH).st_size == 0:
    df = pd.DataFrame(columns=["Plate Number", "Entry Time", "Exit Time", "Location"])
    df.to_csv(CSV_PATH, index=False)
    print("[INFO] Created new CSV file with headers.")


# --------------------------
# HELPER FUNCTIONS
# --------------------------
def normalize_text(text):
    """Clean OCR output and make uppercase."""
    return "".join(ch for ch in text if ch.isalnum()).upper()


def looks_like_plate(text):
    """Filter for realistic number plates."""
    if len(text) < 6 or len(text) > 12:
        return False
    if not re.search(r"[A-Z]", text):
        return False
    if not re.search(r"\d", text):
        return False
    return True


def save_plate_image_and_label(plate_img, plate_number, box, frame_shape):
    """
    Save cropped plate image and corresponding YOLO label file.
    box = (x1, y1, x2, y2)
    """
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_plate = re.sub(r"[^A-Z0-9]", "", plate_number)
    filename_base = f"{safe_plate}_{now}"

    # Save cropped image
    image_path = os.path.join(PLATE_SAVE_DIR, f"{filename_base}.jpg")
    cv2.imwrite(image_path, plate_img)

    # Create YOLO label
    x1, y1, x2, y2 = box
    img_h, img_w = frame_shape[:2]

    # Convert to normalized YOLO format
    x_center = ((x1 + x2) / 2) / img_w
    y_center = ((y1 + y2) / 2) / img_h
    width = (x2 - x1) / img_w
    height = (y2 - y1) / img_h

    label_path = os.path.join(PLATE_SAVE_DIR, f"{filename_base}.txt")
    with open(label_path, "w") as f:
        f.write(f"0 {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")

    print(f"[INFO] Saved: {image_path} + label {label_path}")


def detect_number_plate(frame):
    """Detect number plates using YOLOv12 model and OCR."""
    results = model(frame, verbose=False, device=0 if torch.cuda.is_available() else 'cpu')
    detected_plates = []

    for result in results:
        boxes = result.boxes.xyxy.cpu().numpy().astype(int)  # [x1, y1, x2, y2]
        for (x1, y1, x2, y2) in boxes:
            plate_img = frame[y1:y2, x1:x2]

            # Preprocess for OCR
            gray_plate = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
            gray_plate = cv2.bilateralFilter(gray_plate, 11, 17, 17)
            _, thresh = cv2.threshold(gray_plate, 120, 255, cv2.THRESH_BINARY)

            # OCR with Tesseract
            text = pytesseract.image_to_string(thresh, config='--oem 3 --psm 7')
            text = normalize_text(text)

            if looks_like_plate(text):
                detected_plates.append((text, (x1, y1, x2, y2), plate_img))

    return detected_plates


def log_or_update_csv(plate_number, location="Camera-1"):
    """Log plate in CSV or update its exit time."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    plate_number = plate_number.upper()

    if not looks_like_plate(plate_number):
        return

    if not os.path.exists(CSV_PATH) or os.stat(CSV_PATH).st_size == 0:
        df = pd.DataFrame(columns=["Plate Number", "Entry Time", "Exit Time", "Location"])
        df.to_csv(CSV_PATH, index=False)
    else:
        try:
            df = pd.read_csv(CSV_PATH)
        except pd.errors.EmptyDataError:
            df = pd.DataFrame(columns=["Plate Number", "Entry Time", "Exit Time", "Location"])
            df.to_csv(CSV_PATH, index=False)

    if plate_number not in df["Plate Number"].values:
        new_row = pd.DataFrame([{
            "Plate Number": plate_number,
            "Entry Time": now,
            "Exit Time": now,
            "Location": location
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        print(f"[INFO] New Entry logged: {plate_number} at {now}")
    else:
        df.loc[df["Plate Number"] == plate_number, "Exit Time"] = now
        print(f"[INFO] Exit time updated: {plate_number} at {now}")

    df.to_csv(CSV_PATH, index=False)


# --------------------------
# MAIN PROGRAM
# --------------------------
if __name__ == "__main__":
    print("\n[INFO] Choose mode:")
    print("1️⃣  Live Camera")
    print("2️⃣  Video File")
    print("3️⃣  Image File")
    choice = input("Enter choice (1, 2, or 3): ").strip()

    # ------------------ MODE 1: LIVE CAMERA ------------------
    if choice == "1":
        cap = cv2.VideoCapture(0)
        location = "LiveCam"

        print("\n[INFO] Detecting plates... Press 'q' to quit.\n")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            detected_plates = detect_number_plate(frame)
            for plate_text, box, plate_img in detected_plates:
                x1, y1, x2, y2 = box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                cv2.putText(frame, plate_text, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

                log_or_update_csv(plate_text, location)
                save_plate_image_and_label(plate_img, plate_text, box, frame.shape)

            cv2.imshow("Vehicle Number Plate Detection", cv2.resize(frame, (1280, 720)))
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    # ------------------ MODE 2: VIDEO FILE ------------------
    elif choice == "2":
        path = input("Enter video path: ").strip()
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print("[ERROR] Could not open video.")
            exit()
        location = os.path.basename(path).split(".")[0]

        print("\n[INFO] Detecting plates... Press 'q' to quit.\n")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            detected_plates = detect_number_plate(frame)
            for plate_text, box, plate_img in detected_plates:
                x1, y1, x2, y2 = box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                cv2.putText(frame, plate_text, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

                log_or_update_csv(plate_text, location)
                save_plate_image_and_label(plate_img, plate_text, box, frame.shape)

            cv2.imshow("Vehicle Number Plate Detection", cv2.resize(frame, (1280, 720)))
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

    # ------------------ MODE 3: IMAGE FILE ------------------
    elif choice == "3":
        image_path = input("Enter image path: ").strip()
        if not os.path.exists(image_path):
            print("[ERROR] Image not found.")
            exit()

        frame = cv2.imread(image_path)
        if frame is None:
            print("[ERROR] Could not load image.")
            exit()

        detected_plates = detect_number_plate(frame)
        location = os.path.basename(image_path).split(".")[0]

        if not detected_plates:
            print("[INFO] No number plate detected in the image.")
        else:
            for plate_text, box, plate_img in detected_plates:
                x1, y1, x2, y2 = box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                cv2.putText(frame, plate_text, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

                log_or_update_csv(plate_text, location)
                save_plate_image_and_label(plate_img, plate_text, box, frame.shape)

            cv2.imshow("Detected Number Plate", cv2.resize(frame, (1280, 720)))
            cv2.waitKey(0)
            cv2.destroyAllWindows()

    else:
        print("[ERROR] Invalid choice.")
