import os

frames_base = r"C:\carnumberplate-main\frames"

# Iterate over each video folder
for video_folder in os.listdir(frames_base):
    folder_path = os.path.join(frames_base, video_folder)
    if not os.path.isdir(folder_path):
        continue

    # List all images in the folder
    image_files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

    for image_file in image_files:
        image_name = os.path.splitext(image_file)[0]
        txt_file = image_name + ".txt"
        txt_path = os.path.join(folder_path, txt_file)

        # Delete image if corresponding txt file does not exist
        if not os.path.exists(txt_path):
            os.remove(os.path.join(folder_path, image_file))
            print(f"Deleted {image_file} in {video_folder} because {txt_file} does not exist.")
