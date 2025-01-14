import subprocess
import pyric             # pyric errors
import pyric.pyw as pyw  # iw functionality
import time
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from flask import Flask, request, jsonify

app = Flask(__name__)
CORS(app, resource={r"/*":{"origins":"*"}})
socketio = SocketIO(app, cors_allowed_origins="*")

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
        else:
            clients.append("No clients found")

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
def connected():
	print("client has connected at")
	print(request.remote_addr)
	emit('data', ifDetail('wlan1'), broadcast=True)
	while True:
		time.sleep(1)
		emit('data', ifDetail('wlan1'), broadcast=True)

@socketio.on("disconnect")
def disconnected():
	print("user disconnected")
	emit("disconnect", f"user {request.remote_addr} disconnected", broadcast=True)

if __name__ == '__main__':
	socketio.run(app, port=5000, host='0.0.0.0', debug=True)
	#app.run(host='0.0.0.0', port=5000)
