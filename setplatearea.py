import cv2
import numpy as np
import os
from tkinter import filedialog, Tk

class PointSelector:
    def __init__(self):
        self.points = []
        self.image_path = None
        self.image = None
        self.window_name = "Select Points"
        
    def select_image(self):
        """Open file dialog to select an image"""
        root = Tk()
        root.withdraw()  # Hide the main window
        file_path = filedialog.askopenfilename(
            title="Select an image",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")]
        )
        root.destroy()
        
        if not file_path:
            print("No image selected.")
            return False
            
        self.image_path = file_path
        self.image = cv2.imread(file_path)
        if self.image is None:
            print(f"Error: Could not load image {file_path}")
            return False
            
        return True
    
    def mouse_callback(self, event, x, y, flags, param):
        """Mouse callback function to capture points"""
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(self.points) < 4:
                self.points.append((x, y))
                print(f"Point {len(self.points)} captured at ({x}, {y})")
                
                # Draw the point on the image
                cv2.circle(self.image, (x, y), 5, (0, 255, 0), -1)
                
                # Draw lines between consecutive points
                if len(self.points) > 1:
                    cv2.line(self.image, self.points[-2], self.points[-1], (0, 255, 0), 2)
                
                # Show current point number
                cv2.putText(self.image, f"Point {len(self.points)}", 
                           (x + 10, y + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                
                # Update display
                cv2.imshow(self.window_name, self.image)
            
            elif len(self.points) == 4:
                print("All 4 points have been selected.")
    
    def run(self):
        """Main execution loop"""
        if not self.select_image():
            return
            
        # Create window and set mouse callback
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)
        
        # Display the image
        cv2.imshow(self.window_name, self.image)
        
        print("Click on the image to select 4 points in order:")
        print("1. Top-left corner")
        print("2. Top-right corner")
        print("3. Bottom-left corner")
        print("4. Bottom-right corner")
        print("Press 'q' or 'ESC' when done.")
        
        while True:
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # ESC key
                break
            elif len(self.points) == 4:
                break
        
        cv2.destroyAllWindows()
        
        # Save the points to a text file
        if len(self.points) == 4:
            base_name = os.path.splitext(os.path.basename(self.image_path))[0]
            txt_file = f"{base_name}.txt"
            
            with open(txt_file, 'w') as f:
                for point in self.points:
                    f.write(f"{point[0]},{point[1]}\n")
            
            print(f"Points saved to {txt_file}")
            print("Points:")
            for i, point in enumerate(self.points):
                print(f"Point {i+1}: {point[0]}, {point[1]}")
        else:
            print("Not enough points selected. No file created.")

if __name__ == "__main__":
    selector = PointSelector()
    selector.run()