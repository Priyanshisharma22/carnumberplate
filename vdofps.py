import cv2
import os

# -----------------------------
# 1️⃣ Setup paths
# -----------------------------
video_dir = r"C:\carnumberplate-main\images"   # Folder containing videos
output_base = r"C:\carnumberplate-main\frames"  # Folder to save extracted frames
os.makedirs(output_base, exist_ok=True)

# -----------------------------
# 2️⃣ Get all video files
# -----------------------------
video_files = [f for f in os.listdir(video_dir) if f.lower().endswith(('.mp4', '.avi', '.mov'))]

# -----------------------------
# 3️⃣ Process each video
# -----------------------------
for video_file in video_files:
    video_path = os.path.join(video_dir, video_file)
    cap = cv2.VideoCapture(video_path)

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        fps = 30  # Default if FPS not detected

    # Extract 5 frames per second
    frame_interval = max(1, int(fps / 5))

    count = 0
    saved_count = 0

    print(f"\nProcessing: {video_file} (FPS: {fps:.2f})")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if count % frame_interval == 0:
            frame_name = os.path.join(output_base, f"{os.path.splitext(video_file)[0]}_frame_{saved_count:04d}.jpg")
            cv2.imwrite(frame_name, frame)
            saved_count += 1

        count += 1

    cap.release()
    print(f"✅ {saved_count} frames saved from {video_file} in {output_base}")

print("\n🎉 Frame extraction complete for all videos!")
