from flask import Flask, render_template, Response, request, jsonify
from multiprocessing import Process, Queue, Value, Manager, freeze_support
import time
import requests
import torch
import queue
import cv2
import numpy as np
import urllib.request
from ultralytics import YOLO
import base64
import os
from werkzeug.utils import secure_filename
import threading

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Set device for torch
device = 'cuda' if torch.cuda.is_available() else 'cpu'
print(f"Using device: {device}")

# Global variables
CAMERAS = {}
ESP_IPS = {}
frame_queues = {}
result_queues = {}
processes = {}
running_flag = None
vehicle_counts = None
vehicle_fps = None
current_base_url = "http://192.168.137"
current_subnets = {
    "A": "252",
    "B": "253",
    "C": "254",
    "D": "255"
}

def camera_process(road, url, frame_queue, result_queue, running_flag, input_type='ip'):
    print(f"Camera process started for road {road}")
    try:
        model = YOLO("yolov8n.pt")
        # model = YOLO("numberplate_training_960_12n2.pt")
        model.to(device)
    except Exception as e:
        print(f"Error loading YOLO model for road {road}: {e}")
        return

    start_time = time.time()
    frame_count = 0
    cap = None

    if input_type == 'video':
        cap = cv2.VideoCapture(url)
        if not cap.isOpened():
            print(f"Error: Could not open video file {url}")
            return

    while running_flag.value:
        try:
            frame = None
            if input_type == 'ip':
                img_resp = urllib.request.urlopen(url)
                imgnp = np.array(bytearray(img_resp.read()), dtype=np.uint8)
                frame = cv2.imdecode(imgnp, -1)
            elif input_type == 'video':
                ret, frame = cap.read()
                if not ret:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ret, frame = cap.read()
                    if not ret:
                        time.sleep(1)
                        continue

            if frame is not None:
                car_count = 0
                frame_with_boxes = frame.copy()
                try:
                    results = model(frame, stream=True)
                    for r in results:
                        boxes = r.boxes.cpu().numpy()
                        for box in boxes:
                            try:
                                cls = int(box.cls[0]) if hasattr(box.cls, '__len__') else int(box.cls)
                                if cls in [2,6,7,8]:
                                    car_count += 1
                                    xyxy = box.xyxy
                                    if len(xyxy.shape) > 1:
                                        xyxy = xyxy[0]
                                    x1,y1,x2,y2 = map(int, xyxy)
                                    cv2.rectangle(frame_with_boxes, (x1,y1),(x2,y2),(0,255,0),2)
                                    cv2.putText(frame_with_boxes,'car',(x1,y1-10),cv2.FONT_HERSHEY_SIMPLEX,0.9,(0,255,0),2)
                            except:
                                continue
                except:
                    frame_with_boxes = frame.copy()
                    car_count = 0

                cv2.putText(frame_with_boxes, f"Total Vehicles: {car_count}", (10,30), cv2.FONT_HERSHEY_SIMPLEX,1,(0,255,0),2)

                frame_count += 1
                fps = 0.0
                if time.time() - start_time >= 1.0:
                    fps = frame_count / (time.time() - start_time)
                    frame_count = 0
                    start_time = time.time()

                result_queue.put({
                    'road': road,
                    'frame': frame_with_boxes,
                    'vehicle_count': car_count,
                    'fps': fps,
                    'update_shared': True
                })

        except Exception as e:
            print(f"Error in camera process {road}: {str(e)}")
            time.sleep(1)

def result_consumer():
    """Update shared dicts from result_queues"""
    global result_queues, vehicle_counts, vehicle_fps, running_flag
    while running_flag.value:
        for road, q in result_queues.items():
            try:
                result = q.get(timeout=0.5)
                if result.get('update_shared', False):
                    vehicle_counts[road] = result['vehicle_count']
                    vehicle_fps[road] = result['fps']
            except queue.Empty:
                continue

def timer_process(vehicle_counts, running_flag):
    while running_flag.value:
        for road in CAMERAS.keys():
            if not running_flag.value:
                break
            vehicle_count = vehicle_counts.get(road,0)
            trigger_green_light(road, vehicle_count)
            green_time = max(vehicle_count*4,10)
            time.sleep(green_time+5.5)

def trigger_green_light(road, vehicle_count):
    try:
        green_time = max(vehicle_count*4,10)
        esp_ip = ESP_IPS.get(road)
        if esp_ip:
            response = requests.get(f"{esp_ip}/{green_time}")
            if response.status_code != 200:
                print(f"Road {road}: Failed to trigger green light")
    except Exception as e:
        print(f"Road {road}: Error triggering green light - {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({"status":"running","mode":"server"})

@app.route('/debug_counts')
def debug_counts():
    return jsonify({
        "running_flag": running_flag.value if running_flag else None,
        "vehicle_counts": dict(vehicle_counts) if vehicle_counts else {},
        "vehicle_fps": dict(vehicle_fps) if vehicle_fps else {},
        "processes": list(processes.keys()) if processes else [],
        "frame_queues": list(frame_queues.keys()) if frame_queues else [],
        "result_queues": list(result_queues.keys()) if result_queues else []
    })

@app.route('/vehicle_count')
def vehicle_count():
    if not running_flag or not running_flag.value:
        return jsonify({})
    counts = {}
    for road in ['A','B','C','D']:
        counts[road] = {
            'count': vehicle_counts.get(road,0),
            'fps': vehicle_fps.get(road,0.0)
        }
    return jsonify(counts)

@app.route('/upload_videos',methods=['POST'])
def upload_videos():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    for key in request.files:
        file = request.files[key]
        if file and file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return jsonify({"status":"success"}),200

@app.route('/stop_monitoring')
def stop_monitoring():
    global running_flag, processes, vehicle_counts, vehicle_fps
    if running_flag and running_flag.value:
        running_flag.value = False
        for process in processes.values():
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
        processes.clear()
        if vehicle_counts: vehicle_counts.clear()
        if vehicle_fps: vehicle_fps.clear()
        return jsonify({"status":"Monitoring stopped"}),200
    return jsonify({"status":"Monitoring not running"}),200

def generate_frames():
    global result_queues
    while running_flag and running_flag.value:
        for road, result_queue in result_queues.items():
            try:
                result = result_queue.get(timeout=1)
                ret, buffer = cv2.imencode('.jpg', result['frame'])
                if ret:
                    frame_bytes = buffer.tobytes()
                    encoded_frame = base64.b64encode(frame_bytes).decode('utf-8')
                    yield f"data: {{\"road\":\"{result['road']}\",\"frame\":\"{encoded_frame}\",\"vehicle_count\":{result['vehicle_count']},\"fps\":{result['fps']}}}\n\n"
            except queue.Empty:
                continue

@app.route('/stream_camera_data')
def stream_camera_data():
    return Response(generate_frames(), mimetype='text/event-stream')

@app.route('/video_feed/<road>')
def video_feed(road):
    if road not in CAMERAS:
        return "Camera not found",404
    def gen():
        while running_flag and running_flag.value:
            if road in result_queues:
                try:
                    result = result_queues[road].get(timeout=1)
                    ret, buffer = cv2.imencode('.jpg', result['frame'])
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'+frame_bytes+b'\r\n')
                except queue.Empty:
                    continue
    return Response(gen(),mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/cam')
def cam():
    start_monitoring_internal('cam')
    return render_template('index.html', mode='cam')

@app.route('/demo')
def demo():
    start_monitoring_internal('demo')
    return render_template('index.html', mode='demo')

def start_monitoring_internal(mode):
    global running_flag, frame_queues, result_queues, processes, vehicle_counts, vehicle_fps, CAMERAS, ESP_IPS, current_base_url, current_subnets

    CAMERAS.clear()
    ESP_IPS.clear()
    if mode=='cam':
        for road,subnet in current_subnets.items():
            CAMERAS[road] = f"{current_base_url}.{subnet}/cam.jpg"
            ESP_IPS[road] = f"{current_base_url}.{subnet}"
    elif mode=='demo':
        video_dir = os.path.join(os.getcwd(),'testvid')
        if not os.path.exists(video_dir):
            video_dir = 'testvid'
        video_files = [f for f in os.listdir(video_dir) if f.endswith('.mp4')] if os.path.exists(video_dir) else []
        roads = ['A','B','C','D']
        for i, road in enumerate(roads):
            CAMERAS[road] = os.path.join(video_dir, video_files[i]) if i<len(video_files) else None

    if running_flag is None:
        manager = Manager()
        running_flag = manager.Value('b', False)
        vehicle_counts = manager.dict()
        vehicle_fps = manager.dict()

    if not running_flag.value:
        running_flag.value = True
        frame_queues.clear()
        result_queues.clear()
        processes.clear()
        vehicle_counts.clear()
        vehicle_fps.clear()

        for road in CAMERAS.keys():
            vehicle_counts[road]=0
            vehicle_fps[road]=0.0

        for road, url in CAMERAS.items():
            if url is None: continue
            frame_queue = Queue(maxsize=2)
            result_queue = Queue(maxsize=2)
            frame_queues[road] = frame_queue
            result_queues[road] = result_queue
            input_type = 'video' if mode=='demo' else 'ip'
            p = Process(target=camera_process,args=(road,url,frame_queue,result_queue,running_flag,input_type))
            p.start()
            processes[road]=p

        # Start consumer thread
        consumer_thread = threading.Thread(target=result_consumer, daemon=True)
        consumer_thread.start()

        if mode=='cam':
            timer_p = Process(target=timer_process,args=(vehicle_counts,running_flag))
            timer_p.start()
            processes['timer']=timer_p

@app.route('/update_config',methods=['POST'])
def update_config():
    global current_base_url, current_subnets
    data = request.get_json()
    if 'base_url' in data: current_base_url = data['base_url']
    if 'subnets' in data: current_subnets.update(data['subnets'])
    if running_flag and running_flag.value:
        stop_monitoring()
        start_monitoring_internal('cam')
    return jsonify({"status":"Configuration updated"}),200

if __name__=='__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    freeze_support()
    app.run(debug=True,threaded=True)
