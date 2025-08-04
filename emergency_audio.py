#!/usr/bin/env python3
"""
Emergency Audio Player for Queue System
This script plays an alarm sound when called from the browser.
Usage: python emergency_audio.py [queue_number]
"""

import sys
import os
import time
import subprocess
import threading
from pathlib import Path

def play_sound_windows(sound_path, duration=10):
    """Play sound on Windows using winsound"""
    try:
        import winsound
        # Play the sound for specified duration
        end_time = time.time() + duration
        while time.time() < end_time:
            winsound.PlaySound(str(sound_path), winsound.SND_FILENAME)
            time.sleep(0.1)  # Small delay between repeats
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"Windows sound error: {e}")
        return False

def play_sound_pygame(sound_path, duration=10):
    """Play sound using pygame"""
    try:
        import pygame
        pygame.mixer.init()
        sound = pygame.mixer.Sound(str(sound_path))
        
        end_time = time.time() + duration
        while time.time() < end_time:
            sound.play()
            time.sleep(1)  # Play every second
        
        pygame.quit()
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"Pygame sound error: {e}")
        return False

def play_sound_playsound(sound_path, duration=10):
    """Play sound using playsound library"""
    try:
        from playsound import playsound
        end_time = time.time() + duration
        while time.time() < end_time:
            playsound(str(sound_path), block=False)
            time.sleep(2)
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"Playsound error: {e}")
        return False

def play_sound_system(sound_path):
    """Play sound using system command"""
    try:
        if os.name == 'nt':  # Windows
            # Try multiple Windows methods
            try:
                os.system(f'start /min wmplayer "{sound_path}" /close')
            except:
                pass
            
            try:
                # Try PowerShell SoundPlayer
                ps_command = f'powershell -c "(New-Object Media.SoundPlayer \\"{sound_path}\\").PlaySync()"'
                os.system(ps_command)
            except:
                pass
                
            try:
                # Try batch file as ultimate fallback
                batch_path = Path("emergency_audio.bat")
                if batch_path.exists():
                    os.system(f'start /min cmd /c emergency_audio.bat "Queue"')
            except:
                pass
                
        else:  # Linux/Mac
            os.system(f'aplay "{sound_path}" &')
        return True
    except Exception as e:
        print(f"System command error: {e}")
        return False

def show_alert_window(queue_number):
    """Show alert window using tkinter"""
    try:
        import tkinter as tk
        from tkinter import messagebox
        
        root = tk.Tk()
        root.withdraw()  # Hide main window
        root.attributes('-topmost', True)  # Always on top
        
        # Show alert
        messagebox.showwarning(
            "🚨 QUEUE ALERT! 🚨",
            f"Queue Number {queue_number} is being called!\n\nPlease proceed to the office immediately!"
        )
        
        root.destroy()
        return True
    except ImportError:
        return False
    except Exception as e:
        print(f"Alert window error: {e}")
        return False

def main():
    queue_number = sys.argv[1] if len(sys.argv) > 1 else "Unknown"
    
    print(f"🚨 EMERGENCY AUDIO ALERT FOR QUEUE {queue_number}! 🚨")
    
    # Find sound file
    sound_paths = [
        Path("Sounds/alarm.wav"),
        Path("Sounds/alarm.mp3"),
        Path("alarm.wav"),
        Path("alarm.mp3")
    ]
    
    sound_path = None
    for path in sound_paths:
        if path.exists():
            sound_path = path
            break
    
    if not sound_path:
        print("⚠️ No sound file found! Looking for:")
        for path in sound_paths:
            print(f"  - {path}")
        
        # Show alert even without sound
        show_alert_window(queue_number)
        return
    
    print(f"📢 Playing sound: {sound_path}")
    
    # Try different audio methods
    methods = [
        ("Windows Sound", lambda: play_sound_windows(sound_path)),
        ("Pygame", lambda: play_sound_pygame(sound_path)),
        ("Playsound", lambda: play_sound_playsound(sound_path)),
        ("System Command", lambda: play_sound_system(sound_path))
    ]
    
    # Show alert window in background
    threading.Thread(target=lambda: show_alert_window(queue_number), daemon=True).start()
    
    success = False
    for method_name, method in methods:
        print(f"🔊 Trying {method_name}...")
        if method():
            print(f"✅ {method_name} succeeded!")
            success = True
            break
        else:
            print(f"❌ {method_name} failed.")
    
    if not success:
        print("❌ All audio methods failed!")
        # Keep alert window visible
        show_alert_window(queue_number)
    else:
        print("✅ Audio alert completed!")

if __name__ == "__main__":
    main()
