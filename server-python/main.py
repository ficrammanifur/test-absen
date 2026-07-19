# main.py - ESP32 RFID & Face Recognition System
# HANYA menggunakan webcam eksternal (Logitech C270)

import cv2
import numpy as np
import face_recognition
import paho.mqtt.client as mqtt
import json
import time
import os
import threading
from datetime import datetime
import pickle
import uuid
import re
from collections import Counter

# Import config
from config import *

# ==========================================
# 1. WEBCAM DETECTOR (HANYA EKSTERNAL)
# ==========================================

def detect_external_webcam():
    """
    Deteksi webcam eksternal (Logitech C270)
    Returns: index webcam atau None
    """
    print("\n🔍 Mencari webcam eksternal Logitech C270...")
    
    # Coba index yang biasanya digunakan Logitech C270
    # Biasanya index 1 atau 2
    possible_indexes = [1, 2, 3, 0]
    
    for i in possible_indexes:
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    # Coba deteksi apakah ini Logitech
                    # Cara sederhana: coba baca beberapa frame
                    print(f"   ✅ Webcam ditemukan di index {i}")
                    
                    # Coba dapatkan nama dari v4l2
                    try:
                        import subprocess
                        result = subprocess.run(
                            ['v4l2-ctl', '--device=/dev/video{}'.format(i), '--all'],
                            capture_output=True, text=True, timeout=2
                        )
                        for line in result.stdout.split('\n'):
                            if 'Logitech' in line or 'C270' in line:
                                print(f"   🟢 LOGITECH C270 ditemukan di index {i}!")
                                cap.release()
                                return i
                    except:
                        pass
                    
                    # Jika tidak bisa deteksi nama, tapi ini webcam eksternal
                    # Asumsikan ini Logitech jika bukan index 0 (internal)
                    if i != 0:
                        print(f"   ✅ Webcam eksternal di index {i}")
                        cap.release()
                        return i
                    
                cap.release()
        except:
            pass
    
    print("   ❌ Tidak ada webcam eksternal yang ditemukan!")
    return None

# ==========================================
# 2. FACE ENCODING LOADER / TRAINER
# ==========================================

class FaceDatabase:
    def __init__(self):
        self.known_face_encodings = []
        self.known_face_names = []
        self.encodings_file = ENCODINGS_FILE
        
        if os.path.exists(self.encodings_file):
            self.load_encodings()
        else:
            print("⚠️  No face data. Training...")
            self.train_from_directory()
    
    def train_from_directory(self):
        """Training dengan multiple faces per orang"""
        print("\n" + "=" * 50)
        print("📸 TRAINING FACE RECOGNITION (Multiple Faces)")
        print("=" * 50)
        
        if not os.path.exists(KNOWN_FACES_DIR):
            os.makedirs(KNOWN_FACES_DIR)
            print(f"📁 Folder '{KNOWN_FACES_DIR}' created!")
            print("📸 Tambahkan gambar dengan format: nama.jpg, nama1.jpg, nama2.jpg, dst")
            return
        
        files = [f for f in os.listdir(KNOWN_FACES_DIR) 
                if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        
        if len(files) == 0:
            print(f"⚠️  No images in '{KNOWN_FACES_DIR}'")
            print("📸 Tambahkan gambar dengan format: nama.jpg, nama1.jpg, nama2.jpg, dst")
            return
        
        print(f"📸 Found {len(files)} images...\n")
        
        # Group by name (remove number suffix)
        name_groups = {}
        for filename in files:
            name = os.path.splitext(filename)[0]
            base_name = re.sub(r'\d+$', '', name)
            if base_name not in name_groups:
                name_groups[base_name] = []
            name_groups[base_name].append(filename)
        
        total_encodings = 0
        
        for base_name, file_list in name_groups.items():
            print(f"\n👤 Processing: {base_name} ({len(file_list)} images)")
            encodings_for_person = []
            
            for filename in file_list:
                image_path = os.path.join(KNOWN_FACES_DIR, filename)
                print(f"   🔄 {filename}...", end=" ")
                
                try:
                    image = face_recognition.load_image_file(image_path)
                    encodings = face_recognition.face_encodings(image)
                    
                    if len(encodings) > 0:
                        encodings_for_person.append(encodings[0])
                        print("✅")
                    else:
                        print("❌ (no face)")
                except Exception as e:
                    print(f"❌ ERROR: {e}")
            
            if encodings_for_person:
                for encoding in encodings_for_person:
                    self.known_face_encodings.append(encoding)
                    self.known_face_names.append(base_name)
                    total_encodings += 1
                print(f"   ✅ Added {len(encodings_for_person)} encoding(s) for {base_name}")
            else:
                print(f"   ❌ No valid encodings for {base_name}")
        
        if total_encodings > 0:
            self.save_encodings()
            unique_names = list(set(self.known_face_names))
            print(f"\n✅ Training complete! {total_encodings} encodings saved.")
            print(f"📋 People: {', '.join(unique_names)}")
        else:
            print("\n❌ No faces were successfully encoded!")
    
    def save_encodings(self):
        data = {
            'encodings': self.known_face_encodings,
            'names': self.known_face_names,
            'timestamp': datetime.now().isoformat()
        }
        with open(self.encodings_file, 'wb') as f:
            pickle.dump(data, f)
        print(f"💾 Encodings saved to {self.encodings_file}")
    
    def load_encodings(self):
        try:
            with open(self.encodings_file, 'rb') as f:
                data = pickle.load(f)
                self.known_face_encodings = data['encodings']
                self.known_face_names = data['names']
            print(f"✅ Loaded {len(self.known_face_names)} face encodings")
            unique_names = list(set(self.known_face_names))
            print(f"📋 People: {', '.join(unique_names)}")
        except Exception as e:
            print(f"❌ Error loading: {e}")

# ==========================================
# 3. MQTT HANDLER
# ==========================================

class MQTTHandler:
    def __init__(self, on_rfid_callback):
        self.client_id = f"Python_Backend_{uuid.uuid4().hex[:8]}"
        self.client = mqtt.Client(client_id=self.client_id)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.on_rfid_callback = on_rfid_callback
        self.connected = False
        self.is_processing = False
    
    def connect(self):
        try:
            print(f"📡 Connecting to MQTT: {MQTT_BROKER}:{MQTT_PORT}")
            self.client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            print(f"❌ MQTT connection failed: {e}")
            return False
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("✅ Connected to MQTT Broker!")
            self.connected = True
            client.subscribe(MQTT_TOPIC_RFID)
            print(f"📡 Subscribed to: {MQTT_TOPIC_RFID}")
        else:
            print(f"❌ MQTT connection failed, rc={rc}")
    
    def on_disconnect(self, client, userdata, rc):
        print("⚠️  MQTT Disconnected")
        self.connected = False
    
    def on_message(self, client, userdata, msg):
        try:
            payload = msg.payload.decode('utf-8')
            if DEBUG_MODE:
                print(f"\n📨 Received: {payload}")
            
            data = json.loads(payload)
            uid = data.get('uid', '')
            
            if uid and not self.is_processing:
                self.is_processing = True
                self.on_rfid_callback(uid)
            elif uid and self.is_processing:
                print("⏳ Sistem sedang memproses kartu sebelumnya...")
        except Exception as e:
            print(f"❌ Error: {e}")
            self.is_processing = False
    
    def publish_result(self, status, name=""):
        payload = {
            'status': status,
            'name': name,
            'timestamp': datetime.now().isoformat()
        }
        result = self.client.publish(MQTT_TOPIC_RESULT, json.dumps(payload))
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"📤 Published: {status} - {name}")
        else:
            print(f"❌ Failed to publish, error: {result.rc}")
        
        self.is_processing = False
    
    def reset_processing(self):
        self.is_processing = False

# ==========================================
# 4. FACE RECOGNITION ENGINE (WEBCAM EKSTERNAL)
# ==========================================

class FaceRecognitionEngine:
    def __init__(self, face_db, mqtt_handler):
        self.face_db = face_db
        self.mqtt = mqtt_handler
        self.recognition_active = False
        self.cap = None
        self.camera_index = None
        self.show_preview = True
        
        self.fps = 0
        self.frame_count = 0
        self.fps_timer = time.time()
        
        self.connect_camera()
    
    def connect_camera(self):
        """Connect ke webcam eksternal Logitech C270"""
        print("\n📷 Mencari webcam eksternal...")
        
        # Deteksi webcam eksternal
        cam_index = detect_external_webcam()
        
        if cam_index is None:
            print("❌ Webcam eksternal tidak ditemukan!")
            print("💡 Pastikan Logitech C270 terhubung")
            return False
        
        self.camera_index = cam_index
        
        # Connect ke webcam
        try:
            print(f"\n📷 Menghubungkan ke webcam index {self.camera_index}...")
            self.cap = cv2.VideoCapture(self.camera_index)
            
            if not self.cap.isOpened():
                print(f"❌ Gagal membuka webcam {self.camera_index}!")
                return False
            
            # Set resolusi dan FPS
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Test read
            ret, frame = self.cap.read()
            if ret:
                actual_fps = self.cap.get(cv2.CAP_PROP_FPS)
                width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                
                print(f"✅ Webcam eksternal terhubung!")
                print(f"   Resolution: {int(width)}x{int(height)}")
                print(f"   FPS: {actual_fps:.1f}")
                print(f"   Camera Index: {self.camera_index}")
                return True
            else:
                print("⚠️  Webcam terbuka tapi tidak ada frame")
                return False
                
        except Exception as e:
            print(f"❌ Camera error: {e}")
            return False
    
    def capture_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                self.frame_count += 1
                current_time = time.time()
                if current_time - self.fps_timer >= 1.0:
                    self.fps = self.frame_count
                    self.frame_count = 0
                    self.fps_timer = current_time
                return frame
        return None
    
    def get_fps(self):
        return self.fps
    
    def draw_face_boxes(self, frame, face_locations, face_names, status, fps):
        for (top, right, bottom, left), name in zip(face_locations, face_names):
            if status == "SUCCESS":
                color = (0, 255, 0)
            elif status == "FAILED":
                color = (0, 0, 255)
            else:
                color = (255, 255, 0)
            
            cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            
            label = f"{name} ({status})" if status else name
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
            cv2.rectangle(frame, (left, top - label_size[1] - 10), 
                         (left + label_size[0], top), color, -1)
            
            cv2.putText(frame, label, (left, top - 5), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        cv2.putText(frame, f"FPS: {fps}", (frame.shape[1] - 100, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    def recognize_face(self, uid):
        if uid not in USER_DATABASE:
            print(f"❌ UID {uid} not registered")
            self.mqtt.publish_result('FAILED', 'KARTU_TIDAK_TERDAFTAR')
            self.mqtt.reset_processing()
            return
        
        if len(self.face_db.known_face_encodings) == 0:
            print("❌ No face encodings available")
            self.mqtt.publish_result('FAILED', 'TIDAK_ADA_DATA_WAJAH')
            self.mqtt.reset_processing()
            return
        
        name = USER_DATABASE[uid]
        print(f"\n🔍 Starting face recognition for: {name}")
        print(f"⏱️  Timeout: {FACE_RECOGNITION_TIMEOUT}s")
        print(f"📷 Lihat ke webcam eksternal (Logitech C270)!")
        print("💡 Press 'q' to stop recognition")
        
        self.recognition_active = True
        start_time = time.time()
        recognized = False
        frame_count = 0
        matched_name = ""
        status = "PROCESSING"
        
        cv2.namedWindow("Face Recognition", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Face Recognition", 640, 480)
        
        frame_skip = 2
        process_frame_count = 0
        
        while time.time() - start_time < FACE_RECOGNITION_TIMEOUT:
            if not self.recognition_active:
                break
            
            frame = self.capture_frame()
            
            if frame is None:
                time.sleep(0.01)
                continue
            
            frame_count += 1
            display_frame = frame.copy()
            
            process_frame_count += 1
            if process_frame_count % frame_skip == 0:
                try:
                    small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                    rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                    
                    face_locations = face_recognition.face_locations(rgb_frame)
                    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
                    
                    face_locations = [(top*2, right*2, bottom*2, left*2) 
                                     for (top, right, bottom, left) in face_locations]
                    
                    face_names = []
                    detection_status = "PROCESSING"
                    
                    if len(face_encodings) > 0:
                        if DEBUG_MODE and frame_count % 10 == 0:
                            print(f"👤 {len(face_encodings)} face(s) detected")
                        
                        for face_encoding in face_encodings:
                            matches = face_recognition.compare_faces(
                                self.face_db.known_face_encodings,
                                face_encoding,
                                tolerance=FACE_MATCH_TOLERANCE
                            )
                            
                            if True in matches:
                                matched_indices = [i for i, match in enumerate(matches) if match]
                                matched_names_list = [self.face_db.known_face_names[i] for i in matched_indices]
                                most_common = Counter(matched_names_list).most_common(1)[0][0]
                                
                                if most_common.lower() == name.lower():
                                    print(f"✅ Face matched: {most_common}")
                                    recognized = True
                                    matched_name = most_common
                                    detection_status = "SUCCESS"
                                    face_names.append(f"{most_common} ✅")
                                else:
                                    print(f"⚠️  Wrong face: {most_common} (expected {name})")
                                    detection_status = "FAILED"
                                    face_names.append(f"{most_common} ❌")
                            else:
                                detection_status = "UNKNOWN"
                                face_names.append("Unknown ❌")
                    else:
                        if frame_count % 20 == 0:
                            print(f"👀 No face detected")
                        detection_status = "NO_FACE"
                    
                    if face_locations and face_names:
                        status = detection_status
                        self.draw_face_boxes(display_frame, face_locations, face_names, status, self.fps)
                    else:
                        cv2.putText(display_frame, "No face detected", (10, 30), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        cv2.putText(display_frame, f"FPS: {self.fps}", (display_frame.shape[1] - 100, 30), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
                    cv2.putText(display_frame, f"User: {name}", (10, 60), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(display_frame, f"Status: {status}", (10, 90), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                               (0, 255, 0) if status == "SUCCESS" else (0, 0, 255), 2)
                    cv2.putText(display_frame, f"Frame: {frame_count}", (10, 120), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                    
                    remaining = int(FACE_RECOGNITION_TIMEOUT - (time.time() - start_time))
                    cv2.putText(display_frame, f"Time: {remaining}s", (10, 150), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                    
                except Exception as e:
                    if DEBUG_MODE:
                        print(f"⚠️  Recognition error: {e}")
            else:
                cv2.putText(display_frame, f"FPS: {self.fps}", (display_frame.shape[1] - 100, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(display_frame, f"User: {name}", (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(display_frame, f"Status: {status}", (10, 90), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, 
                           (0, 255, 0) if status == "SUCCESS" else (0, 0, 255), 2)
                cv2.putText(display_frame, f"Frame: {frame_count}", (10, 120), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
                
                remaining = int(FACE_RECOGNITION_TIMEOUT - (time.time() - start_time))
                cv2.putText(display_frame, f"Time: {remaining}s", (10, 150), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            
            cv2.imshow("Face Recognition", display_frame)
            
            if recognized:
                break
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:
                print("⚠️  Recognition cancelled by user")
                self.recognition_active = False
                break
            
            time.sleep(0.005)
        
        cv2.destroyWindow("Face Recognition")
        
        if recognized:
            self.mqtt.publish_result('SUCCESS', matched_name)
            print(f"\n✅ Access GRANTED for: {matched_name}")
        else:
            print(f"\n❌ Face recognition failed for {name}")
            self.mqtt.publish_result('FAILED', 'WAJAH_TIDAK_COCOK')
        
        self.recognition_active = False
        self.mqtt.reset_processing()
    
    def release(self):
        if self.cap:
            self.cap.release()
            cv2.destroyAllWindows()
            print("📷 Webcam released")

# ==========================================
# 5. MAIN SYSTEM
# ==========================================

class RFIDAccessSystem:
    def __init__(self):
        print("\n" + "=" * 60)
        print("🏢 ESP32 RFID & Face Recognition System")
        print("=" * 60)
        
        print("\n📋 KONFIGURASI:")
        print(f"   Laptop IP: {LAPTOP_IP}")
        print(f"   ESP32-S3 IP: {ESP32_S3_IP}")
        print(f"   MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
        print(f"   Webcam: Logitech C270 (Eksternal)")
        print(f"   Users: {', '.join(USER_DATABASE.values())}")
        print("=" * 60)
        
        print("\n📸 Loading face database...")
        self.face_db = FaceDatabase()
        
        if len(self.face_db.known_face_names) == 0:
            print("\n⚠️  No faces in database!")
            print(f"📸 Please add images to: {os.path.abspath(KNOWN_FACES_DIR)}")
            print("📝 Format: nama.jpg, nama1.jpg, nama2.jpg, dst")
            return
        
        print("\n📡 Initializing MQTT...")
        self.mqtt = MQTTHandler(self.on_rfid_received)
        self.mqtt.connect()
        
        print("\n📷 Initializing webcam...")
        self.face_engine = FaceRecognitionEngine(self.face_db, self.mqtt)
        
        if not self.face_engine.cap:
            print("\n⚠️  Webcam not available! Face recognition will fail.")
        
        self.running = True
        
        print("\n" + "=" * 60)
        print("✅ SYSTEM READY!")
        print("💡 Tempelkan kartu RFID ke ESP32-S3")
        print("📷 Lihat ke webcam Logitech C270! (Window akan muncul)")
        print("🔄 Press Ctrl+C to stop")
        print("=" * 60 + "\n")
    
    def on_rfid_received(self, uid):
        print(f"\n{'='*50}")
        print(f"🔑 RFID: {uid}")
        
        if uid in USER_DATABASE:
            name = USER_DATABASE[uid]
            print(f"👤 User: {name}")
            
            thread = threading.Thread(
                target=self.face_engine.recognize_face,
                args=(uid,),
                daemon=True
            )
            thread.start()
        else:
            print(f"❌ UID tidak terdaftar!")
            self.mqtt.publish_result('FAILED', 'KARTU_TIDAK_TERDAFTAR')
            self.mqtt.reset_processing()
    
    def run(self):
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down...")
            self.shutdown()
    
    def shutdown(self):
        self.running = False
        if self.face_engine:
            self.face_engine.release()
        if self.mqtt.client:
            self.mqtt.client.loop_stop()
            self.mqtt.client.disconnect()
        print("✅ System stopped")

# ==========================================
# 6. ENTRY POINT
# ==========================================

if __name__ == "__main__":
    if not os.path.exists(KNOWN_FACES_DIR):
        os.makedirs(KNOWN_FACES_DIR)
        print(f"📁 Folder '{KNOWN_FACES_DIR}' dibuat!")
        print(f"📸 Tambahkan gambar wajah ke: {os.path.abspath(KNOWN_FACES_DIR)}")
        print("📝 Format: nama.jpg, nama1.jpg, nama2.jpg, dst")
        print("🔄 Jalankan ulang setelah menambahkan gambar\n")
        exit(0)
    
    system = RFIDAccessSystem()
    system.run()
