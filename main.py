from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import os
import json
from flask import Flask, send_file
from PIL import Image
import io
import numpy as np
import threading
import time

app = Flask(__name__)
app.config["SECRET_KEY"] = "secret!"
socketio = SocketIO(app)

canvas_file = "canvas_state.txt"
connected_users = 0
reset_password = os.environ.get("password", "admin")

chat_file = "chat_history.txt"

@app.route('/favicon.png')
def favicon():
  return send_file('static/favicon.png', mimetype='image/png')

def save_chat_message(message):
    with open(chat_file, "a") as f:
        f.write(json.dumps(message) + "\n")

def load_chat_history():
    if os.path.exists(chat_file):
        with open(chat_file, "r") as f:
            return [json.loads(line.strip()) for line in f]
    return []

@socketio.on("send_message")
def handle_send_message(json):
    save_chat_message(json)
    emit("receive_message", json, broadcast=True)

@app.route("/get_chat_history")
def get_chat_history():
    return json.dumps(load_chat_history())

def save_canvas_state():
    with open(canvas_file, "w") as f:
        json.dump(canvas_state, f)


def load_canvas_state():
    if os.path.exists(canvas_file):
        with open(canvas_file, "r") as f:
            return json.load(f)
    else:
        return [[255, 255, 255] for _ in range(64 * 64)]


canvas_state = load_canvas_state()

def create_favicon():
    global canvas_state  # Add this line to access the global variable
    while True:
        img_data = np.array(canvas_state).reshape((64, 64, 3)).astype(np.uint8)
        img = Image.fromarray(img_data, 'RGB')
        img.save("static/favicon.png")
        time.sleep(60)  # Update every 60 seconds

favicon_thread = threading.Thread(target=create_favicon)
favicon_thread.start()


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("connect")
def on_connect():
    global connected_users
    connected_users += 1
    emit("canvas_state", {"state": canvas_state})
    emit("user_count", {"count": connected_users}, broadcast=True)


@socketio.on("disconnect")
def on_disconnect():
    global connected_users
    connected_users -= 1
    emit("user_count", {"count": connected_users}, broadcast=True)


@socketio.on("draw_pixel")
def handle_draw_pixel(json):
    idx = json["y"] * 64 + json["x"]
    canvas_state[idx] = json["color"]
    save_canvas_state()
    emit(
        "update_pixel",
        {"x": json["x"], "y": json["y"], "color": json["color"]},
        broadcast=True,
    )

@socketio.on("reset_canvas")
def handle_reset_canvas(json):
    if json.get("password") == reset_password:
        global canvas_state
        canvas_state = [[255, 255, 255] for _ in range(64 * 64)]
        save_canvas_state()
        emit("canvas_state", {"state": canvas_state}, broadcast=True)
        emit(
            "notification",
            {"message": "Canvas reset successfully.", "category": "success"},
            broadcast=False,
        )
    else:
        emit(
            "notification",
            {"message": "Invalid password.", "category": "danger"},
            broadcast=False,
        )

@app.route('/download_canvas')
def download_canvas():
    return send_file(canvas_file, as_attachment=True, download_name='canvas_state.txt')

@socketio.on("load_canvas")
def handle_load_canvas(data):
    if data.get("password") == reset_password:
        try:
            new_canvas_state = json.loads(data["content"])  # data['content'] should be a JSON string

            # Validate the format of new_canvas_state
            if not isinstance(new_canvas_state, list) or len(new_canvas_state) != 64*64:
                raise ValueError("Invalid canvas format")

            for pixel in new_canvas_state:
                if not (isinstance(pixel, list) and len(pixel) == 3):
                    raise ValueError("Invalid pixel format")

            global canvas_state
            canvas_state = new_canvas_state
            save_canvas_state()
            emit("canvas_state", {"state": canvas_state}, broadcast=True)
            emit("notification", {"message": "Canvas loaded successfully.", "category": "success"})
        except Exception as e:
            emit("notification", {"message": f"Invalid canvas format: {str(e)}", "category": "danger"})
    else:
        emit("notification", {"message": "Invalid password.", "category": "danger"})


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
