# Smart Elevator Overload Detection System - V5

## Quick Start
```bash
cd smart_elevator_pro
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install PyTorch (CPU) first:
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Then install everything else:
pip install -r requirements.txt

# Run:
python main.py
```

## Features
- Multi-object YOLO detection (person, phone, bottle, bag, etc.)
- Hardware mode (ESP32 serial: `W:<value>`)
- Simulation & Demo modes
- SQLite database logging
- Real-time weight graph
- Industrial dark theme UI

## ESP32 Format
Send: `W:7.50` (weight in kg, 9600 baud)
Receive: `OVERLOAD` (when limit exceeded)
