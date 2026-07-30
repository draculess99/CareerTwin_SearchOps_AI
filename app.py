import subprocess
import sys
import time
import os
import atexit

def main():
    print("Starting CareerTwin SearchOps AI...")
    
    # Get the directory of the current script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Start the backend Flask API
    backend_script = os.path.join(base_dir, 'backend', 'app.py')
    print("Starting backend Flask API...")
    backend_process = subprocess.Popen([sys.executable, backend_script], cwd=base_dir)
    
    # Give the backend a moment to start up
    time.sleep(3)
    
    # Start the frontend Streamlit app
    frontend_script = os.path.join(base_dir, 'frontend', 'streamlit_app.py')
    print("Starting frontend Streamlit app...")
    # This will automatically open your default web browser
    frontend_process = subprocess.Popen([sys.executable, "-m", "streamlit", "run", frontend_script], cwd=base_dir)
    
    # Register cleanup function to shut down child processes when app.py exits
    def cleanup():
        print("Shutting down child processes...")
        backend_process.terminate()
        frontend_process.terminate()
        
    atexit.register(cleanup)
    
    try:
        # Keep the main script running to keep child processes alive
        frontend_process.wait()
    except KeyboardInterrupt:
        print("\nApplication stopped by user.")

if __name__ == "__main__":
    main()
