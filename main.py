"""
GPS Navigation System for the Visually Impaired

This system combines QR code detection, GPS tracking, and text-to-speech to help
visually impaired users navigate indoor environments. It uses a Raspberry Pi with
camera module and GPS module to:
1. Detect QR codes placed at key locations
2. Track user's GPS coordinates
3. Provide voice guidance for navigation
4. Offer a web interface for monitoring

Key Components:
- Flask web server for monitoring interface
- PiCamera2 for QR code detection
- pyttsx3 for text-to-speech
- networkx for pathfinding
- GPS module integration
- Speech recognition for hands-free input
"""

# Import required libraries
import threading
import time
import cv2
import pyttsx3
import networkx as nx
import speech_recognition as sr
import serial
import pynmea2
from picamera2 import Picamera2
from flask import Flask, Response, jsonify, render_template
from flask_cors import CORS  

###############################################################################
#                                FLASK SETUP                                  #
###############################################################################
"""
Flask server setup for web monitoring interface.
Provides routes for:
- Main webpage
- Live video feed
- GPS data updates
- Real-time log streaming via Server-Sent Events (SSE)
"""

app = Flask(__name__)
CORS(app)  

picam2 = None  # Global reference to PiCamera2

# Global dictionary to store GPS data
gps_data = {
    "latitude": None,
    "longitude": None,
    "altitude": None,
    "status": "Waiting for GPS fix..."
}

# ----------------------- SSE LOGS SETUP (for real-time logs) ----------------
log_messages = []        # list of strings to store log lines
last_sse_index = 0       # keep track of last-sent index for SSE

def add_log(message):
    """
    Helper to add a log line to log_messages and print to console.
    Maintains a historical record of all system events and messages.
    
    Args:
        message (str): The log message to record
    """
    print(message)
    log_messages.append(message)

# Route for the main webpage (requires templates/index.html)
@app.route('/')
def index():
    return render_template('index.html')

# Route for live video feed
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

# API route for GPS data (returns JSON)
@app.route('/gps')
def get_gps_data():
    return jsonify(gps_data)

# SSE logs endpoint
@app.route('/logs')
def sse_logs():
    return Response(stream_logs(), mimetype='text/event-stream')

def stream_logs():
    """
    Stream log messages to the web interface using Server-Sent Events (SSE).
    """
    global last_sse_index
    while True:
        if last_sse_index < len(log_messages):
            for i in range(last_sse_index, len(log_messages)):
                yield f"data: {log_messages[i]}\n\n"
            last_sse_index = len(log_messages)
        time.sleep(1)

def generate_frames():
    """ 
    Continuously capture frames from PiCamera2 and encode as JPEG for web streaming.
    Uses Motion JPEG (MJPEG) format for real-time video feed.
    
    Yields:
        bytes: JPEG encoded frame with proper multipart HTTP headers
    """
    while True:
        frame = picam2.capture_array()
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

def run_flask_app():
    """ 
    Run the Flask server in a separate thread.
    Binds to all network interfaces (0.0.0.0) for remote access.
    Uses port 5000 by default.
    """
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

###############################################################################
#                            GPS FUNCTIONALITY                                #
###############################################################################
"""
GPS module integration handling.
Reads NMEA sentences from a serial GPS module and parses them for position data.
Updates global gps_data dictionary with current coordinates and status.
"""

def read_gps():
    """ 
    Continuously read and parse GPS NMEA sentences in a background thread.
    
    Handles two main NMEA sentence types:
    - GNRMC (Recommended Minimum Navigation Information)
    - GNGGA (Global Positioning System Fix Data)
    
    Updates global gps_data with:
    - Latitude
    - Longitude
    - Altitude (when available)
    - Connection status
    """
    port = "/dev/ttyS0"
    baud_rate = 9600

    try:
        ser = serial.Serial(port, baud_rate, timeout=1)
        add_log(f"Connected to {port} at {baud_rate} baud for GPS.")
    except Exception as e:
        add_log(f"Error connecting to serial port: {e}")
        return

    while True:
        try:
            line = ser.readline().decode('ascii', errors='replace').strip()
            if line.startswith("$GNRMC") or line.startswith("$GNGGA"):
                try:
                    msg = pynmea2.parse(line)
                    if hasattr(msg, 'latitude') and hasattr(msg, 'longitude'):
                        gps_data["latitude"] = msg.latitude
                        gps_data["longitude"] = msg.longitude
                    if hasattr(msg, 'altitude'):
                        gps_data["altitude"] = msg.altitude
                    gps_data["status"] = "GPS Fix Acquired ✅"
                except pynmea2.ParseError:
                    gps_data["status"] = "GPS Parsing Error ❌"
        except Exception as e:
            gps_data["status"] = f"Error: {e}"

###############################################################################
#                           QR NAVIGATION & TTS                               #
###############################################################################
"""
Core navigation functionality combining QR code detection and voice guidance.
Includes text-to-speech, QR detection, and pathfinding between locations.
"""

def initialize_tts():
    """ 
    Initialize the text-to-speech engine with optimized parameters.
    
    Configures:
    - Speech rate (150 words per minute)
    - Volume level (80%)
    - Optional voice selection
    
    Returns:
        pyttsx3.Engine: Configured TTS engine instance
    """
    engine = pyttsx3.init()
    # Example custom TTS settings:
    engine.setProperty('rate', 150)    # Speed (default ~200)
    engine.setProperty('volume', 0.8)  # Volume [0.0, 1.0]
    
    # If you want a specific voice, you can uncomment & pick from the list:
    # voices = engine.getProperty('voices')
    # for i, v in enumerate(voices):
    #     add_log(f"Voice {i}: {v.name} ({v.id})")
    # engine.setProperty('voice', voices[1].id)  # e.g. pick second voice if available
    
    return engine

def speak(engine, message):
    """ 
    Speak a message using TTS and log it.
    
    Args:
        engine (pyttsx3.Engine): TTS engine instance
        message (str): Message to speak
    """
    add_log(f"[TTS] {message}")
    engine.say(message)
    engine.runAndWait()

def define_qr_locations():
    """ 
    Define the mapping of QR codes to physical locations.
    
    Structure:
    - A* codes: Major landmarks and rooms
    - B* codes: Intermediate navigation points
    
    Returns:
        dict: Mapping of QR codes to location names
    """
    return {
        "A1": "Room 515",
        "A2": "MTech Lab 514",
        "A3": "Staff Room Door 1",
        "A4": "Staff Room Door 3",
        "A5": "Room 511",
        "A6": "Washroom",
        "A7": "Stairs",
        "A8": "Room 510",
        "A9": "Micro Lab 508",
        "A10": "Circuits Lab 506",
        "A11": "EC Core Staff Room",
        "A12": "Lift",
        "A13": "Sdpk",
        "A14": "Room 503",
        "A15": "Stairs EB",
        "B1": "Intermediate Code 1",
        "B2": "Intermediate Code 2",
        "B3": "Intermediate Code 3",
        "B4": "Intermediate Code 4",
        "B5": "Intermediate Code 5",
        "B6": "Intermediate Code 6",
        "B7": "Intermediate Code 7",
        "B8": "Intermediate Code 8",
        "B9": "Intermediate Code 9",
        "B10": "Intermediate Code 10",
        "B11": "Intermediate Code 11",
        "B12": "Intermediate Code 12",
        "B13": "Intermediate Code 13",
        "B14": "Intermediate Code 14"
    }

def build_graph(qr_data):
    """ 
    Build a directed graph representing the navigation network.
    
    Creates a bidirectional graph where:
    - Nodes are QR code locations
    - Edges represent walkable paths between locations
    
    Args:
        qr_data (dict): Dictionary of QR codes and their location names
        
    Returns:
        networkx.DiGraph: Directed graph for pathfinding
    """
    G = nx.DiGraph()
    G.add_nodes_from(qr_data.keys())
    edges = [
        ("A1", "A2"), ("A2", "B1"), ("B1", "A3"), ("A3", "B2"), ("B2", "B3"),
        ("B3", "B4"), ("B4", "B5"), ("B5", "A4"), ("A4", "A5"), ("A5", "B6"),
        ("B6", "A6"), ("A6", "A7"), ("A7", "A8"), ("A8", "A9"), ("A9", "B7"),
        ("B7", "A10"), ("A10", "B8"), ("B8", "B9"), ("B9", "A11"), ("A11", "B10"),
        ("B10", "B11"), ("B11", "B12"), ("B12", "A13"), ("A13", "A14"), ("A14", "B13"),
        ("B13", "A15"), ("A15", "B14"), ("B14", "A1"), ("A11", "A12")
    ]
    # Make edges bidirectional
    edges += [(v, u) for (u, v) in edges]
    G.add_edges_from(edges)
    return G

def detect_qr_code(frame):
    """ 
    Detect and decode QR codes in a camera frame.
    
    Args:
        frame: numpy.ndarray: Camera frame image
        
    Returns:
        str or None: Decoded QR code data if found, None otherwise
    """
    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(frame)
    if data:
        return data.strip()
    return None

def compute_route(graph, start, end):
    """ 
    Compute the shortest path between two QR locations.
    
    Uses Dijkstra's algorithm via networkx for pathfinding.
    
    Args:
        graph (networkx.DiGraph): Navigation graph
        start (str): Starting QR code
        end (str): Destination QR code
        
    Returns:
        list or None: List of QR codes forming the path, or None if no path exists
    """
    try:
        return nx.shortest_path(graph, source=start, target=end)
    except nx.NetworkXNoPath:
        return None

def get_destination_voice(engine):
    """ 
    Listen for and process voice input for destination selection.
    
    Features:
    - Automatic noise level adjustment
    - 5-second timeout for input
    - Google Speech Recognition API integration
    
    Args:
        engine: TTS engine for user prompts
        
    Returns:
        str or None: Recognized destination code or None if recognition failed
    """
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()
    speak(engine, "Please say your destination code after the beep.")
    add_log("Listening for destination code...")

    with microphone as source:
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
    try:
        command = recognizer.recognize_google(audio)
        add_log(f"Recognized (voice): {command}")
        return command.strip().upper()
    except sr.UnknownValueError:
        speak(engine, "Sorry, I did not understand. Please try again.")
    except sr.RequestError:
        speak(engine, "Could not request results; please check your network connection.")
    return None

###############################################################################
#                                    MAIN                                     #
###############################################################################
"""
Main program flow coordinating all system components:
1. Hardware initialization (camera, GPS)
2. Web server startup
3. Navigation session handling
4. User interaction via voice and QR codes
"""

def main():
    """
    Main program execution flow.
    
    Sequence:
    1. Initialize camera and configure video
    2. Start Flask web server thread
    3. Start GPS monitoring thread
    4. Initialize TTS and navigation system
    5. Guide user through navigation process
    6. Clean up resources on completion
    """
    global picam2

    # 1. Initialize PiCamera2 for live video
    picam2 = Picamera2()
    config = picam2.create_video_configuration(
        main={"size": (640, 480), "format": "RGB888"},
        controls={"FrameDurationLimits": (33333, 33333)}
    )
    picam2.configure(config)
    picam2.start()
    time.sleep(1)
    add_log("[System] Camera initialized.")

    # 2. Start the Flask server in a background thread
    flask_thread = threading.Thread(target=run_flask_app, daemon=True)
    flask_thread.start()
    add_log("[System] Flask server started on port 5000.")

    # 3. Start the GPS reading thread
    gps_thread = threading.Thread(target=read_gps, daemon=True)
    gps_thread.start()
    add_log("[System] GPS reading thread started.")

    # 4. Initialize TTS and navigation data
    engine = initialize_tts()
    qr_data = define_qr_locations()
    nav_graph = build_graph(qr_data)

    # 5. Prompt user to scan the starting QR code
    speak(engine, "Please scan the starting QR code.")
    current_location = None
    while current_location is None:
        frame = picam2.capture_array()
        code = detect_qr_code(frame)
        if code and code in qr_data:
            current_location = code
            speak(engine, f"Starting location detected: {qr_data[code]}")

    # 6. Get destination via voice command
    destination = None
    while destination not in qr_data:
        spoken_code = get_destination_voice(engine)
        if spoken_code and spoken_code in qr_data:
            destination = spoken_code
        else:
            speak(engine, "Invalid destination code. Please try again.")

    # 7. Compute route
    route = compute_route(nav_graph, current_location, destination)
    if not route:
        speak(engine, "No path found to the destination. Exiting navigation.")
        add_log("[System] No path found, navigation ended.")
        return

    speak(engine, f"Route found: {', '.join(route)}")
    add_log(f"[Navigation] Route: {route}")
    route_index = 0

    # 8. Navigation loop
    while True:
        frame = picam2.capture_array()
        code = detect_qr_code(frame)
        if code and code in qr_data:
            if code == route[route_index]:
                speak(engine, f"You are at {qr_data[code]}.")
                if route_index == len(route) - 1:
                    speak(engine, "You have reached your destination. Navigation complete.")
                    add_log("[System] Destination reached.")
                    break
                else:
                    route_index += 1
                    next_code = route[route_index]
                    speak(engine, f"Next, please take 10 steps forward to {qr_data[next_code]}.")
            else:
                speak(engine, "This is not the expected QR code. Please keep scanning.")
        time.sleep(0.2)

    # 9. Cleanup
    picam2.stop()
    add_log("[System] Navigation ended. Camera stopped.")

if __name__ == "__main__":
    main()
