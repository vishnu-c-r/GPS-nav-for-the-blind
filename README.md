# GPS Navigation System for the Visually Impaired

A Raspberry Pi-based navigation system that combines QR code detection, GPS tracking, and text-to-speech to help visually impaired users navigate indoor environments.

## Features

- QR code-based indoor navigation
- Real-time GPS tracking
- Voice guidance using text-to-speech
- Web interface for monitoring
- Live camera feed
- Real-time GPS data display
- Automatic service discovery using mDNS
- Voice command recognition
- Intelligent pathfinding between locations

## Hardware Requirements

- Raspberry Pi (3 or newer recommended)
- Pi Camera Module
- GPS Module (Serial connection)
- Speaker/Headphones
- Microphone
- Internet connection for web interface

## Software Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- Flask
- Flask-CORS
- opencv-python
- pyttsx3
- networkx
- speech_recognition
- serial
- pynmea2
- picamera2
- zeroconf
- netifaces

## Installation

1. Clone the repository:
```bash
git clone https://github.com/vishnu-c-r/GPS-nav-for-the-blind.git
cd GPS-nav-for-the-blind
```

2. Install dependencies:(install in virtual environment)
```bash
pip install -r requirements.txt
```

3. Configure hardware:
   - Connect the Pi Camera Module
   - Connect GPS module to serial port (/dev/ttyS0)
   - Connect speakers/headphones
   - Configure microphone

## Usage(run in virtual environment)

1. Start the system (requires root for port 80):
```bash
sudo python3 main.py
```
Or without root (uses port 5000):
```bash
python3 main.py
```

2. Access the web interface:
   - Local network: `http://<raspberry-pi-ip>`
   - The system advertises itself via mDNS as `<hostname>.local`

3. Navigation Process:
   - Scan starting location QR code
   - Speak destination code when prompted
   - Follow voice guidance between QR codes
   - Monitor progress through web interface

## QR Code System

The system uses two types of QR codes:
- A-series (A1-A15): Major landmarks and rooms
- B-series (B1-B14): Intermediate navigation points

## Project Structure

```
GPS-nav-for-the-blind/
├── main.py           # Main application code
├── README.md         # This file
├── requirements.txt  # Python dependencies
└── templates/        # Web interface templates
    └── index.html   # Main monitoring page
```

## User Interface Repository

The user interface for this project is maintained in a separate repository:
- Repository: [assistiveNav](https://github.com/niha1n/assistiveNav)

Please refer to the UI repository for:
- Web interface implementation details
- UI-specific setup instructions
- Frontend development guidelines
- UI-related issues and contributions

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Thanks to all contributors and testers
- Special thanks to the visually impaired community for feedback and suggestions

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.