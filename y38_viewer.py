#!/usr/bin/env python3
"""
Minimal browser viewer for AIR-ES / Y38 Wi-Fi otoscopes.
Uses only the Python 3.8 standard library.

Connect the Mac to the otoscope's Wi-Fi first, then run:
    python3 y38_viewer.py

Open http://127.0.0.1:8080 in a browser.
Stop with Ctrl-C.
"""
import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

CAMERA_IP = "192.168.0.10"
CAMERA_PORT = 8032
HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8080

latest_frame = None
frame_lock = threading.Condition()


def make_start_command():
    # AIR-Look/Xylla preview command: 24 bytes, opcode 1 (little-endian).
    packet = bytearray(24)
    packet[0:4] = b"\x99\x99\x01\x00"
    return bytes(packet)


def camera_receiver():
    global latest_frame

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.25)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
    sock.bind(("", 0))
    destination = (CAMERA_IP, CAMERA_PORT)
    command = make_start_command()

    print("UDP video socket local port:", sock.getsockname()[1])
    print("Starting preview at {}:{} ...".format(*destination))
    for _ in range(11):
        sock.sendto(command, destination)

    frame = None
    expected_size = 0
    accumulated = 0
    last_seq = -1
    last_keepalive = time.time()
    packet_count = 0
    frame_count = 0

    while True:
        now = time.time()
        if now - last_keepalive >= 0.8:
            try:
                sock.sendto(command, destination)
            except OSError as exc:
                print("Keepalive send error:", exc)
            last_keepalive = now

        try:
            data, _addr = sock.recvfrom(65535)
        except socket.timeout:
            continue
        except OSError as exc:
            print("UDP receive error:", exc)
            time.sleep(1)
            continue

        packet_count += 1
        if len(data) < 25 or data[0] != 0x66:
            continue

        # 24-byte packet header (little-endian fields).
        fmt = data[2]
        total_size = struct.unpack_from("<I", data, 4)[0]
        chunk_seq = struct.unpack_from("<H", data, 12)[0]
        chunk_len = struct.unpack_from("<H", data, 14)[0]

        if (chunk_len <= 0 or 24 + chunk_len > len(data)
                or total_size <= 0 or total_size > 4 * 1024 * 1024):
            continue
        if fmt != 1:  # 1 = MJPEG; 4 = YUYV (not handled here)
            continue

        new_frame = (
            frame is None or total_size != expected_size
            or chunk_seq < last_seq or chunk_seq == 0
        )
        if new_frame:
            frame = bytearray(total_size)
            expected_size = total_size
            accumulated = 0
            last_seq = -1

        if chunk_seq != last_seq + 1 or accumulated + chunk_len > expected_size:
            frame = None
            expected_size = 0
            accumulated = 0
            last_seq = -1
            continue

        frame[accumulated:accumulated + chunk_len] = data[24:24 + chunk_len]
        accumulated += chunk_len
        last_seq = chunk_seq

        if accumulated == expected_size:
            jpeg = bytes(frame)
            if jpeg.startswith(b"\xff\xd8") and jpeg.endswith(b"\xff\xd9"):
                with frame_lock:
                    latest_frame = jpeg
                    frame_lock.notify_all()
                frame_count += 1
                if frame_count == 1:
                    print("First JPEG received ({} bytes). Open http://{}:{}/".format(
                        len(jpeg), HTTP_HOST, HTTP_PORT))
                if frame_count % 100 == 0:
                    print("{} frames received; {} UDP packets".format(
                        frame_count, packet_count))
            frame = None
            expected_size = 0
            accumulated = 0
            last_seq = -1


class ViewerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            page = """<!doctype html>
<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Y38 Otoscope</title>
<style>
html,body{margin:0;background:#171717;color:#eee;font:16px sans-serif;height:100%}
body{display:flex;flex-direction:column;align-items:center;justify-content:center}
img{max-width:100vw;max-height:88vh;object-fit:contain}
p{margin:8px}
</style></head><body>
<p>Y38 / AIR-ES live view</p><img src="/video" alt="Waiting for camera video...">
</body></html>"""
            body = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/video":
            boundary = b"--frame"
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            last_sent = None
            try:
                while True:
                    with frame_lock:
                        frame_lock.wait_for(
                            lambda: latest_frame is not None and latest_frame is not last_sent,
                            timeout=5.0
                        )
                        jpeg = latest_frame
                    if jpeg is None or jpeg is last_sent:
                        continue
                    last_sent = jpeg
                    self.wfile.write(boundary + b"\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(("Content-Length: %d\r\n\r\n" % len(jpeg)).encode("ascii"))
                    self.wfile.write(jpeg + b"\r\n")
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            return

        self.send_error(404)

    def log_message(self, fmt, *args):
        # Keep the terminal output uncluttered.
        pass


def main():
    receiver = threading.Thread(target=camera_receiver, daemon=True)
    receiver.start()
    server = ThreadingHTTPServer((HTTP_HOST, HTTP_PORT), ViewerHandler)
    print("Viewer page: http://{}:{}/".format(HTTP_HOST, HTTP_PORT))
    print("Make sure the Mac is connected to the camera's AIR-ES Wi-Fi.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping viewer.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
