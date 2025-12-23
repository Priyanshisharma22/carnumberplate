import cv2
import pandas as pd
from ultralytics import YOLO
import numpy as np
import pytesseract
from datetime import datetime
import os
from difflib import SequenceMatcher
import csv
import re


pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

MODEL_PATH = r"C:\carnumberplate-main\runs\freedomown_yolov86\weights\best.pt"
CLASS_FILE = r"C:\carnumberplate-main\coco1.txt"
VIDEO_DIR = r'C:\carnumberplate-main\images'
OUTPUT_FILE = r'C:\carnumberplate-main\car_plate_data.csv'
PROCESSED_DIR = r'C:\carnumberplate-main\processed_videos'

CONF_THRESHOLD = 0.2
EXIT_THRESHOLD = 5.0  

INDIAN_PLATE_PATTERN = re.compile(r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,2}[0-9]{4}$')


def clean_text(raw):
    return ''.join(ch for ch in raw if ch.isalnum()).upper()

def correct_ocr(text):
    mapping = {'O': '0', 'I': '1', 'L': '1', 'Z': '2', 'S': '5', 'B': '8', 'G': '6'}
    return ''.join(mapping.get(c, c) for c in text)

def is_valid_indian_plate(s):
    return bool(INDIAN_PLATE_PATTERN.match(s))

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def find_matching_plate(candidate, plates_info):
    for plate in plates_info.keys():
        if candidate in plate or plate in candidate:
            return plate
    best, best_score = None, 0.0
    for plate in plates_info.keys():
        score = similar(candidate, plate)
        if score > best_score:
            best_score = score
            best = plate
    return best if best_score >= 0.6 else None

# ----------------- SETUP -----------------
os.makedirs(PROCESSED_DIR, exist_ok=True)
model = YOLO(MODEL_PATH)
with open(CLASS_FILE, 'r') as f:
    class_list = [line.strip() for line in f.readlines()]

# Initialize CSV
if not os.path.exists(OUTPUT_FILE) or os.path.getsize(OUTPUT_FILE) == 0:
    with open(OUTPUT_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["NumberPlate", "EntryTime", "ExitTime"])

plates_info = {}

# --
video_files = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(('.mp4', '.avi'))]

for video_file in video_files:
    VIDEO_PATH = os.path.join(VIDEO_DIR, video_file)
    print(f"\nProcessing video: {VIDEO_PATH}")
    cap = cv2.VideoCapture(VIDEO_PATH)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_path = os.path.join(PROCESSED_DIR, f"processed_{video_file}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(out_path, fourcc, fps, (frame_w, frame_h))

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_time = datetime.now()
        current_frame_detected = set()
        displayed_plate = None

        # ----------------- YOLO DETECTION -----------------
        results = model.predict(frame, conf=CONF_THRESHOLD, verbose=False)
        boxes = results[0].boxes

        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cls = int(box.cls[0])
                cls_name = class_list[cls] if cls < len(class_list) else str(cls)

                if cls_name.lower() not in ['license_plate', 'plate']:
                    continue

                crop = frame[y1:y2, x1:x2]
                if crop.size == 0:
                    continue

                if crop.shape[1] < 200:
                    scale = 200 / crop.shape[1]
                    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                gray = cv2.bilateralFilter(gray, 11, 17, 17)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                gray = clahe.apply(gray)
                _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

                custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                raw_text = pytesseract.image_to_string(thresh, config=custom_config)
                text = clean_text(raw_text)
                text = correct_ocr(text)
                if not text:
                    continue

                matched = find_matching_plate(text, plates_info)
                if is_valid_indian_plate(text) and matched is None:
                    canonical = text
                    plates_info[canonical] = {"entry": current_time, "exit": None,
                                              "last_seen": current_time, "saved": False}
                    print(f"[ENTRY] {canonical} at {plates_info[canonical]['entry']}")
                elif matched:
                    canonical = matched
                    plates_info[canonical]["last_seen"] = current_time
                else:
                    continue

                current_frame_detected.add(canonical)
                displayed_plate = canonical

                # ----------------- DRAW RECTANGLE + TEXT -----------------
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(frame, canonical, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

        # ----------------- CHECK EXIT -----------------
        now = datetime.now()
        for plate, info in list(plates_info.items()):
            if plate in current_frame_detected:
                continue
            last_seen = info.get("last_seen", info.get("entry"))
            if info["exit"] is None:
                elapsed = (now - last_seen).total_seconds()
                if elapsed >= EXIT_THRESHOLD:
                    plates_info[plate]["exit"] = now
                    print(f"[EXIT] {plate} at {plates_info[plate]['exit']}")
                    if not plates_info[plate].get("saved", False):
                        with open(OUTPUT_FILE, 'a', newline='') as f:
                            writer = csv.writer(f)
                            writer.writerow([plate, plates_info[plate]['entry'], plates_info[plate]['exit']])
                        plates_info[plate]["saved"] = True

        out.write(frame)

    cap.release()
    out.release()
    print(f"Processed video saved to: {out_path}")

print("\nAll videos processed. Data saved to:", OUTPUT_FILE)
 