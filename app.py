import subprocess
import pyric             # pyric errors
import pyric.pyw as pyw  # iw functionality
import time
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from flask import Flask, request, jsonify
from threading import Lock
import atexit

app = Flask(__name__)
CORS(app, resource={r"/*":{"origins":"*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

thread = None
thread_lock = Lock()

def background_task():
    """Background task to emit wireless interface data"""
    while True:
        try:
            with thread_lock:
                data = ifDetail("wlan1")
                socketio.emit('data', data, namespace='/')
            time.sleep(1)
        except Exception as e:
            print(f"Error in background task: {e}")
            socketio.emit('error', {'message': str(e)}, namespace='/')
            break

def cleanup():
    global thread
    if thread is not None:
        # Signal the thread to stop (you'll need to implement this mechanism)
        print("Cleaning up resources...")

atexit.register(cleanup)

@app.route('/')
def hello():
    return "<__< What are you looking at? >__>"

@app.route('/interfaces')
def getWirelessInterfaces():
    interfaces = pyw.winterfaces()
    return {
        "interfaces": interfaces
    }

@app.route('/interfaces/<id>')
def ifDetail(id):
    details = {}
    if pyw.iswireless(id):
        w0 = pyw.getcard(id)
        info = pyw.ifinfo(w0)
        # If this is an AP, list connected clients
        clients = []
        list = subprocess.run(["/usr/sbin/iw", "dev", id, "station", "dump"], stdout=subprocess.PIPE, text=True)
        list_arr = list.stdout.split("Sta")
        # popping off first index because it is a blank space
        list_arr.pop(0)
        proc = "/proc/net/arp"
        index = 0
        for c in list_arr:
            client = {}
            client["id"] = index
            station = subprocess.run(["/usr/bin/grep", "tion "], input=c.strip(), stdout=subprocess.PIPE, text=True)
            mac = subprocess.run(["/usr/bin/awk", "{print $2}"], input=station.stdout, stdout=subprocess.PIPE, text=True)
            client["mac"] = mac.stdout.strip()
            arp = subprocess.run(["/usr/bin/grep", "-e", mac.stdout.strip(), proc], stdout=subprocess.PIPE, text=True)
            ip = subprocess.run(["/usr/bin/awk", "{print $1}"], input=arp.stdout, capture_output=True, text=True)
            client["ip"] = ip.stdout.strip()
            signal = subprocess.run(["/usr/bin/grep", "signal:"], input=c.strip(), stdout=subprocess.PIPE, text=True)
            sig_val = subprocess.run(["/usr/bin/awk", "{print $2}"], input=signal.stdout, capture_output=True, text=True)
            client["signal"] = sig_val.stdout.strip()
            clients.append(client)
            index += 1

        details = {
            "card": w0,
            "mac": pyw.macget(w0),
            "inet": info["inet"],
            "chipset": info["chipset"],
            "manufacturer": info["manufacturer"],
            "clients": clients
        }
    else:
        details = {
            "error": "Could not get interface info"
        }

    return details

@socketio.on("connect")
def connected(auth):
    global thread
    print("client has connected at")
    print(request.remote_addr)
    
    try:
        # Initial data emit
        data = ifDetail('wlan1')
        emit('data', data, broadcast=True)
        
        # Start background thread if it isn't already running
        with thread_lock:
            if thread is None:
                thread = socketio.start_background_task(background_task)
    except Exception as e:
        print(f"Error in connected handler: {e}")
        emit('error', {'message': str(e)}, broadcast=True)

@socketio.on("disconnect")
def disconnected():
    print("user disconnected")
    emit("disconnect", f"user {request.remote_addr} disconnected", broadcast=True)

if __name__ == '__main__':
    try:
        socketio.run(app, port=5000, host='0.0.0.0', debug=True, allow_unsafe_werkzeug=True)
    except OSError as e:
        if e.errno == 98:
            print("Port 5000 is already in use. Please kill any existing processes using this port.")
            print("You can use: sudo lsof -i :5000 to find processes using port 5000")
            print("Then use: kill -9 <PID> to kill the process")
        raise
