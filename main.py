"""
Smart Elevator Overload Detection System - V5
Main entry point
"""
import tkinter as tk
from ui.dashboard import ElevatorDashboard

def main():
    root = tk.Tk()
    root.title("Smart Elevator Overload Detection System")
    root.geometry("1400x850")
    root.minsize(1200, 750)
    root.configure(bg="#1a1a2e")
    
    app = ElevatorDashboard(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.cleanup(), root.destroy()))
    root.mainloop()

if __name__ == "__main__":
    main()
