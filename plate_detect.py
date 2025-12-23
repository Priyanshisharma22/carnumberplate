import cv2
import numpy as np
import pytesseract
import imutils
import argparse
import csv
from datetime import datetime

# Uncomment if Tesseract is not in PATH:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def preprocess_image(image):
    image = imutils.resize(image, width=800)
    orig = image.copy()

    # --- HSV white mask ---
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_white = np.array([0, 0, 160])
    upper_white = np.array([180, 60, 255])
    mask_hsv = cv2.inRange(hsv, lower_white, upper_white)

    # --- Grayscale + adaptive threshold fallback ---
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask_gray = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 35, 2
    )

    # Combine both masks
    mask = cv2.bitwise_or(mask_hsv, mask_gray)

    # Morphological cleanup
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)

    return image, mask, orig

def detect_label_contour(mask, image):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best_contour, best_area = None, 0

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < 200:  # lower min area
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = float(w) / h
        if 0.8 <= aspect_ratio <= 5.0:
            if area > best_area:
                best_area = area
                best_contour = cnt

    if best_contour is None:
        return None

    rect = cv2.minAreaRect(best_contour)
    box = cv2.boxPoints(rect)
    box = np.intp(box)
    box = order_points(box)
    return box

def order_points(pts):
    xSorted = pts[np.argsort(pts[:, 0]), :]
    leftMost, rightMost = xSorted[:2, :], xSorted[2:, :]
    leftMost = leftMost[np.argsort(leftMost[:, 1]), :]
    rightMost = rightMost[np.argsort(rightMost[:, 1]), :]
    (tl, bl), (tr, br) = leftMost, rightMost
    return np.array([tl, tr, br, bl], dtype="float32")

def four_point_transform(image, pts):
    (tl, tr, br, bl) = pts
    widthA = np.linalg.norm(br - bl)
    widthB = np.linalg.norm(tr - tl)
    maxWidth = max(int(widthA), int(widthB))
    heightA = np.linalg.norm(tr - br)
    heightB = np.linalg.norm(tl - bl)
    maxHeight = max(int(heightA), int(heightB))

    dst = np.array([[0, 0], [maxWidth - 1, 0],
                    [maxWidth - 1, maxHeight - 1], [0, maxHeight - 1]], dtype="float32")

    M = cv2.getPerspectiveTransform(pts, dst)
    warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
    return warped

def recognize_number(roi):
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    config = "--psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    text = pytesseract.image_to_string(binary, config=config)
    text = ''.join(filter(str.isalnum, text))
    confidence = 0.9 if len(text) > 2 else 0.5
    return text, confidence

def log_result(filename, text, confidence, log_path):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([timestamp, filename, text, confidence])

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", help="Path to the image")
    ap.add_argument("--cam", type=int, help="Camera index")
    ap.add_argument("--log", help="Log results to CSV")
    args = vars(ap.parse_args())

    if args["image"]:
        print(f"🔍 Processing image: {args['image']}")
        image = cv2.imread(args["image"])
        if image is None:
            print("❌ Error: Unable to read image.")
            exit()
    elif args["cam"] is not None:
        print("📷 Starting camera...")
        cap = cv2.VideoCapture(args["cam"])
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            cv2.imshow("Press S to capture", frame)
            if cv2.waitKey(1) & 0xFF == ord('s'):
                image = frame.copy()
                break
        cap.release()
        cv2.destroyAllWindows()
    else:
        print("❌ Please provide an image or camera index.")
        exit()

    processed_image, mask, orig = preprocess_image(image)
    label_box = detect_label_contour(mask, processed_image)

    if label_box is not None:
        cv2.drawContours(processed_image, [label_box.astype(int)], -1, (0, 255, 0), 2)
        warped = four_point_transform(orig, label_box)
        text, confidence = recognize_number(warped)

        print(f"✅ White label detected.")
        print(f"🧾 Recognized text: {text}")
        print(f"📊 Confidence: {confidence:.2f}")

        if args["log"]:
            log_result(args["image"], text, confidence, args["log"])

        cv2.imshow("Mask", mask)
        cv2.imshow("Detected Label", processed_image)
        cv2.imshow("Warped Label", warped)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    else:
        print("⚠️ No white label detected — try increasing light or angle.")
