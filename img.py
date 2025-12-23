import cv2
import time
import os
import glob

# Folder containing your videos
video_folder = r"C:\carnumberplate-main\images"
output_dir = os.path.join(video_folder, "frames")
os.makedirs(output_dir, exist_ok=True)

# Find all .mp4 videos in the folder
videos = glob.glob(os.path.join(video_folder, "*.mp4"))

maxFrames = 400  # Number of frames per video (you can change this)

print(f"🔍 Found {len(videos)} video(s) in {video_folder}\n")

for video_path in videos:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ Could not open {video_path}")
        continue

    print(f"🎥 Processing: {os.path.basename(video_path)}")

    cpt = 0
    count = 0

    while cpt < maxFrames:
        ret, frame = cap.read()
        if not ret:
            break

        count += 1
        if count % 3 != 0:  # Skip some frames
            continue

        frame = cv2.resize(frame, (1080, 500))
        cv2.imshow("Frame Extraction", frame)

        # Save frames in "frames" folder with video name prefix
        filename = f"{os.path.splitext(os.path.basename(video_path))[0]}_frame_{cpt}.jpg"
        cv2.imwrite(os.path.join(output_dir, filename), frame)

        time.sleep(0.01)
        cpt += 1

        if cv2.waitKey(5) & 0xFF == 27:  # ESC to stop
            break

    cap.release()
    print(f"✅ Done: {os.path.basename(video_path)} - Saved {cpt} frames\n")

cv2.destroyAllWindows()
print("🎯 All videos processed successfully!")
