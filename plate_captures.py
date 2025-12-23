import cv2
import pytesseract
import pandas as pd
import numpy as np
import os
import re
from datetime import datetime

# --------------------------
# CONFIGURATION
# --------------------------
CSV_PATH = "plate_log.csv"
pytesseract.pytesseract.tesseract_cmd = r"C:/Program Files/Tesseract-OCR/tesseract.exe"

# Load Haar cascade for number plate detection
cascade_path = cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"
plate_cascade = cv2.CascadeClassifier(cascade_path)

if plate_cascade.empty():
    print("[ERROR] Haar cascade not found! Check your OpenCV installation.")
    exit()

# Create CSV if not exists or empty
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
    """
    Heuristic filter for valid number plates:
    At least 6–10 characters, mixture of letters and digits.
    """
    if len(text) < 6 or len(text) > 12:
        return False
    if not re.search(r"[A-Z]", text):
        return False
    if not re.search(r"\d", text):
        return False
    return True


def detect_number_plate(frame):
    """Detect number plates using Haar Cascade and OCR validation."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    plates = plate_cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 20)
    )

    detected_plates = []
    for (x, y, w, h) in plates:
        # Crop region of interest
        plate_img = frame[y:y + h, x:x + w]

        # Convert for OCR
        gray_plate = cv2.cvtColor(plate_img, cv2.COLOR_BGR2GRAY)
        gray_plate = cv2.bilateralFilter(gray_plate, 11, 17, 17)
        _, thresh = cv2.threshold(gray_plate, 120, 255, cv2.THRESH_BINARY)

        # Run OCR
        text = pytesseract.image_to_string(thresh, config='--oem 3 --psm 7')
        text = normalize_text(text)

        # Only accept boxes with realistic plate-like text
        if looks_like_plate(text):
            detected_plates.append((text, (x, y, w, h)))

    return detected_plates


def log_or_update_csv(plate_number, location="Camera-1"):
    """Log new plate immediately or update its exit time if it exists."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    plate_number = plate_number.upper()

    if not looks_like_plate(plate_number):
        return  # skip invalid readings

    # Ensure CSV exists and has headers
    if not os.path.exists(CSV_PATH) or os.stat(CSV_PATH).st_size == 0:
        df = pd.DataFrame(columns=["Plate Number", "Entry Time", "Exit Time", "Location"])
        df.to_csv(CSV_PATH, index=False)
    else:
        try:
            df = pd.read_csv(CSV_PATH)
        except pd.errors.EmptyDataError:
            df = pd.DataFrame(columns=["Plate Number", "Entry Time", "Exit Time", "Location"])
            df.to_csv(CSV_PATH, index=False)

    # Add or update record
    if plate_number not in df["Plate Number"].values:
        # New plate → add a new row
        new_row = pd.DataFrame([{
            "Plate Number": plate_number,
            "Entry Time": now,
            "Exit Time": now,
            "Location": location
        }])
        df = pd.concat([df, new_row], ignore_index=True)
        print(f"[INFO] New Entry logged: {plate_number} at {now}")
    else:
        # Existing plate → update exit time
        df.loc[df["Plate Number"] == plate_number, "Exit Time"] = now
        print(f"[INFO] Exit time updated: {plate_number} at {now}")

    # Save CSV back to disk
    df.to_csv(CSV_PATH, index=False)


# --------------------------
# MAIN PROGRAM
# --------------------------
if __name__ == "__main__":
    print("\n[INFO] Choose mode:")
    print("1️⃣  Live Camera")
    print("2️⃣  Video File")
    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":
        cap = cv2.VideoCapture(0)
        location = "LiveCam"
    elif choice == "2":
        path = input("Enter video path: ").strip()
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print("[ERROR] Could not open video.")
            exit()
        location = os.path.basename(path).split(".")[0]
    else:
        print("[ERROR] Invalid choice.")
        exit()

    print("\n[INFO] Detecting plates... Press 'q' to quit.\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        detected_plates = detect_number_plate(frame)

        for plate_text, (x, y, w, h) in detected_plates:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
            cv2.putText(frame, plate_text, (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
            log_or_update_csv(plate_text, location)

        cv2.imshow("Vehicle Number Plate Detection", cv2.resize(frame, (1280, 720)))
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
