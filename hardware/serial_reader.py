"""
Serial Communication Module — ESP32/Arduino support
Format: W:<float_value>
"""
import threading
import time

SERIAL_AVAILABLE = False
try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    print("[SERIAL] pyserial not installed")

class SerialReader:
    def __init__(self, callback=None, log_callback=None):
        self.callback = callback          # Called with parsed weight float
        self.log_callback = log_callback  # Called with log messages
        self.connection = None
        self.running = False
        self.thread = None
        self.port = None
        self.baud = 9600
        self.last_weight = 0.0
        self.connected = False

    def get_ports(self):
        if not SERIAL_AVAILABLE:
            return []
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    def connect(self, port, baud=9600):
        if not SERIAL_AVAILABLE:
            self._log("pyserial not installed")
            return False
        try:
            self.port = port
            self.baud = baud
            self.connection = serial.Serial(port, baud, timeout=1)
            self._log(f"Connecting to {port} at {baud} baud...")
            time.sleep(2)  # Allow ESP32 to reset
            self.connected = True
            self.running = True
            self.thread = threading.Thread(target=self._read_loop, daemon=True)
            self.thread.start()
            self._log(f"Hardware connected on {port}")
            return True
        except Exception as e:
            self._log(f"Connection failed: {e}")
            self.connected = False
            return False

    def _read_loop(self):
        while self.running and self.connection:
            try:
                if self.connection.in_waiting > 0:
                    raw = self.connection.readline().decode('utf-8', errors='ignore').strip()
                    if raw:
                        self._log(f"[RAW] {raw}")
                        if raw.startswith("W:"):
                            try:
                                val = float(raw[2:])
                                self.last_weight = val
                                self._log(f"[PARSED] Weight = {val:.2f} kg")
                                if self.callback:
                                    self.callback(val)
                            except ValueError:
                                self._log(f"[WARN] Bad value: {raw}")
                else:
                    time.sleep(0.05)
            except Exception as e:
                self._log(f"[ERROR] Read error: {e}")
                self.connected = False
                self.running = False
                break
        self._log("Serial reading stopped")
        self.connected = False

    def send(self, message):
        if self.connection and self.connected:
            try:
                self.connection.write(f"{message}\n".encode())
                self._log(f"[SENT] {message}")
            except Exception as e:
                self._log(f"[SEND ERROR] {e}")

    def disconnect(self):
        self.running = False
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
        self.connected = False
        self._log("Hardware disconnected")

    def _log(self, msg):
        print(f"[SERIAL] {msg}")
        if self.log_callback:
            self.log_callback(msg)
