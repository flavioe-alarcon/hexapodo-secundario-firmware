"""
========================================================================================
Visor Integrado de Video UVC, Telemetría de Gases MiCS-5524 y Control de Luz LED (WS2812)
Tesis de Ingeniería Mecatrónica - UTEC 2026
Autores: Aleskyjubinsl Alcarraz, Flavio Alarcón, Alfredo Erazo
Asesor: Dante Inga Narváez

Arquitectura Híbrida de Máximo Rendimiento:
  - Video UVC MJPEG (TCP en Puerto 81): http://192.168.4.1:81/stream
  - Sensor de Gas (UDP Datagramas 20 Hz): Puerto UDP 5005
  - Control de Luz LED RGB WS2812 (HTTP TCP Puerto 80): http://192.168.4.1:80/light
  - Control de Calibración R0 (HTTP TCP Puerto 80): http://192.168.4.1:80/calibrate
========================================================================================
"""

import sys
import os
import time
import json
import socket
import threading
import datetime
import urllib.request
import cv2
import numpy as np

DEFAULT_HOST = "192.168.4.1"
GAS_UDP_PORT = 5005

# Compatibilidad UTF-8 en consolas Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def safe_print(text):
    try:
        print(text, flush=True)
    except Exception:
        try:
            print(text.encode('ascii', errors='replace').decode('ascii'), flush=True)
        except Exception:
            pass


class VideoStreamReceiver:
    """Hilo receptor de video MJPEG sobre TCP con parser robusto por Content-Length"""
    def __init__(self, stream_url):
        self.stream_url = stream_url
        self.running = False
        self.connected = False
        self.latest_frame = None
        self.fps = 0.0
        self.kb_sec = 0.0
        self.total_frames = 0
        self.is_standby = True
        self.lock = threading.Lock()
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _worker(self):
        bytes_buffer = bytearray()
        fps_counter = 0
        fps_timer = time.time()
        bytes_this_sec = 0

        while self.running:
            try:
                safe_print(f"[VIDEO-TCP] Conectando a stream UVC en {self.stream_url}...")
                req = urllib.request.Request(self.stream_url, headers={'User-Agent': 'ESP32Visor-Python'})
                stream = urllib.request.urlopen(req, timeout=4.0)
                self.connected = True
                safe_print(f"[VIDEO-TCP] Stream MJPEG CONECTADO exitosamente en {self.stream_url}")

                while self.running:
                    chunk = stream.read(4096)
                    if not chunk:
                        break

                    bytes_this_sec += len(chunk)
                    bytes_buffer.extend(chunk)

                    # Parser robusto por Content-Length anunciado en encabezado HTTP
                    while True:
                        cl_pos = bytes_buffer.find(b'Content-Length: ')
                        if cl_pos != -1:
                            hdr_end = bytes_buffer.find(b'\r\n\r\n', cl_pos)
                            if hdr_end != -1:
                                cl_str = bytes_buffer[cl_pos + 16 : hdr_end].decode('ascii', errors='ignore').strip()
                                try:
                                    frame_len = int(cl_str)
                                    start_jpeg = hdr_end + 4
                                    if len(bytes_buffer) >= start_jpeg + frame_len:
                                        jpg = bytes_buffer[start_jpeg : start_jpeg + frame_len]
                                        bytes_buffer = bytes_buffer[start_jpeg + frame_len :]

                                        img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                                        if img is not None:
                                            is_std = bool(img.shape[0] < 30)
                                            with self.lock:
                                                self.latest_frame = img
                                                self.is_standby = is_std
                                                if not is_std:
                                                    self.total_frames += 1

                                            if not is_std:
                                                fps_counter += 1
                                                now = time.time()
                                                if now - fps_timer >= 1.0:
                                                    elapsed = now - fps_timer
                                                    self.fps = fps_counter / elapsed
                                                    self.kb_sec = (bytes_this_sec / 1024.0) / elapsed
                                                    fps_counter = 0
                                                    bytes_this_sec = 0
                                                    fps_timer = now
                                            else:
                                                self.fps = 0.0
                                                self.kb_sec = 0.0
                                        continue
                                except ValueError:
                                    bytes_buffer = bytes_buffer[hdr_end + 4 :]
                                    continue

                        # Fallback por delimitadores SOI (0xFFD8) y EOI (0xFFD9)
                        a = bytes_buffer.find(b'\xff\xd8')
                        b = bytes_buffer.find(b'\xff\xd9', a + 2) if a != -1 else -1
                        if a != -1 and b != -1 and b > a:
                            if b + 4 <= len(bytes_buffer) and (bytes_buffer[b+2:b+4] == b'\r\n' or b'--' in bytes_buffer[b+2:b+6]):
                                jpg = bytes_buffer[a : b + 2]
                                bytes_buffer = bytes_buffer[b + 2 :]
                                img = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                                if img is not None:
                                    is_std = bool(img.shape[0] < 30)
                                    with self.lock:
                                        self.latest_frame = img
                                        self.is_standby = is_std
                                        if not is_std:
                                            self.total_frames += 1
                                    fps_counter += 1
                                    now = time.time()
                                    if now - fps_timer >= 1.0:
                                        elapsed = now - fps_timer
                                        self.fps = fps_counter / elapsed
                                        self.kb_sec = (bytes_this_sec / 1024.0) / elapsed
                                        fps_counter = 0
                                        bytes_this_sec = 0
                                        fps_timer = now
                                continue
                        break

            except Exception as e:
                self.connected = False
                safe_print(f"[VIDEO-TCP] Advertencia: Conexion perdida con {self.stream_url}: {e}")
                time.sleep(1.0)


class GasTelemetryReceiverUDP:
    """Hilo receptor de telemetría de gas mediante datagramas UDP broadcast a 20 Hz"""
    def __init__(self, port=5005):
        self.port = port
        self.running = False
        self.lock = threading.Lock()
        self.latest_data = {
            "v_raw": 0.5,
            "v_med": 0.5,
            "v_ema": 0.5,
            "rs": 7500.0,
            "r0": 7500.0,
            "ratio": 1.0,
            "gas_pct": 0.0,
            "calib": False,
            "seq": 0,
            "rate_hz": 0.0,
            "last_seen": 0.0
        }
        self.history_ema = []
        self.records_to_export = []
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _worker(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", self.port))
            sock.settimeout(1.0)
            safe_print(f"[GAS-UDP] Socket UDP en escucha activa en puerto {self.port}")
        except Exception as e:
            safe_print(f"[GAS-UDP] Error fatal al enlazar puerto UDP {self.port}: {e}")
            return

        pkt_counter = 0
        rate_timer = time.time()

        while self.running:
            try:
                data, addr = sock.recvfrom(2048)
                if not data:
                    continue
                try:
                    js = json.loads(data.decode('utf-8'))
                except Exception:
                    continue

                now = time.time()
                pkt_counter += 1
                if now - rate_timer >= 1.0:
                    hz = pkt_counter / (now - rate_timer)
                    pkt_counter = 0
                    rate_timer = now
                else:
                    hz = self.latest_data.get("rate_hz", 20.0)

                with self.lock:
                    self.latest_data = {
                        "v_raw": js.get("v_raw", 0.0),
                        "v_med": js.get("v_med", 0.0),
                        "v_ema": js.get("v_ema", 0.0),
                        "rs": js.get("rs", 7500.0),
                        "r0": js.get("r0", 7500.0),
                        "ratio": js.get("ratio", 1.0),
                        "gas_pct": js.get("gas_pct", 0.0),
                        "calib": js.get("calib", False),
                        "seq": js.get("seq", 0),
                        "rate_hz": hz,
                        "last_seen": now
                    }
                    self.history_ema.append(self.latest_data["v_ema"])
                    if len(self.history_ema) > 120:
                        self.history_ema.pop(0)

                    self.records_to_export.append({
                        "t": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                        "v_raw": self.latest_data["v_raw"],
                        "v_med": self.latest_data["v_med"],
                        "v_ema": self.latest_data["v_ema"],
                        "rs": self.latest_data["rs"],
                        "r0": self.latest_data["r0"],
                        "ratio": self.latest_data["ratio"],
                        "gas_pct": self.latest_data["gas_pct"],
                        "seq": self.latest_data["seq"]
                    })
                    if len(self.records_to_export) > 5000:
                        self.records_to_export.pop(0)

            except socket.timeout:
                continue
            except Exception as e:
                safe_print(f"[GAS-UDP] Error en lectura UDP: {e}")
                time.sleep(0.5)

        sock.close()


class LightController:
    """Controlador de la luz LED WS2812 mediante HTTP GET/POST en puerto 80"""
    def __init__(self, host_ip):
        self.host_ip = host_ip
        self.light_url = f"http://{host_ip}:80/light"
        self.is_on = False
        self.last_msg = ""
        self.msg_timestamp = 0.0
        self.lock = threading.Lock()

    def toggle(self):
        threading.Thread(target=self._send_toggle, daemon=True).start()

    def set_state(self, turn_on: bool):
        threading.Thread(target=self._send_state, args=(turn_on,), daemon=True).start()

    def _send_toggle(self):
        target = f"{self.light_url}?state=toggle"
        try:
            req = urllib.request.Request(target, headers={'User-Agent': 'ESP32Visor-Python', 'Connection': 'close'})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = resp.read().decode('utf-8')
                js = json.loads(data)
                with self.lock:
                    self.is_on = js.get("light", not self.is_on)
                    estado = "ENCENDIDA" if self.is_on else "APAGADA"
                    self.last_msg = f"LUZ {estado}"
                    self.msg_timestamp = time.time()
                safe_print(f"[LUZ-HTTP] Luz alternada exitosamente: {estado}")
        except Exception as e:
            safe_print(f"[LUZ-HTTP] Error alternando luz en {target}: {e}")

    def _send_state(self, turn_on: bool):
        val = "1" if turn_on else "0"
        target = f"{self.light_url}?state={val}"
        try:
            req = urllib.request.Request(target, headers={'User-Agent': 'ESP32Visor-Python', 'Connection': 'close'})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = resp.read().decode('utf-8')
                js = json.loads(data)
                with self.lock:
                    self.is_on = js.get("light", turn_on)
                    estado = "ENCENDIDA" if self.is_on else "APAGADA"
                    self.last_msg = f"LUZ {estado}"
                    self.msg_timestamp = time.time()
                safe_print(f"[LUZ-HTTP] Luz configurada exitosamente: {estado}")
        except Exception as e:
            safe_print(f"[LUZ-HTTP] Error configurando luz: {e}")


def draw_hud(canvas, video_rx, gas_rx, light_ctrl, calib_message_time):
    """Renderiza la interfaz HUD completa con video, telemetría, osciloscopio y control de luz"""
    h_total, w_total = canvas.shape[:2]
    canvas.fill(15)  # Fondo oscuro

    # -------------------------------------------------------------
    # 1. PANEL DE VIDEO (Izquierda)
    # -------------------------------------------------------------
    vid_w = 640
    vid_h = 480
    vid_x = 20
    vid_y = 60

    with video_rx.lock:
        frame = video_rx.latest_frame
        is_std = video_rx.is_standby
        connected = video_rx.connected
        fps = video_rx.fps
        kbps = video_rx.kb_sec

    if connected and frame is not None and not is_std:
        resized_frame = cv2.resize(frame, (vid_w, vid_h), interpolation=cv2.INTER_AREA)
        canvas[vid_y : vid_y + vid_h, vid_x : vid_x + vid_w] = resized_frame

        # Overlay de métricas de video
        cv2.putText(canvas, f"FPS: {fps:.1f}", (vid_x + 15, vid_y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2, cv2.LINE_AA)
        cv2.putText(canvas, f"Flujo: {kbps:.1f} KB/s", (vid_x + 15, vid_y + 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 255, 200), 1, cv2.LINE_AA)
        cv2.putText(canvas, f"{frame.shape[1]}x{frame.shape[0]} MJPEG", (vid_x + 15, vid_y + 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
    else:
        # Estado de espera / Hot-Plug
        cv2.rectangle(canvas, (vid_x, vid_y), (vid_x + vid_w, vid_y + vid_h), (25, 25, 30), -1)
        if not connected:
            txt_status = "BUSCANDO TRANSMISION DE VIDEO..."
            txt_sub = "Verifica conexion Wi-Fi al SSID 'ESP32S3-CAM'"
            box_col = (50, 100, 255)
        else:
            txt_status = "ESPERANDO DETECCION DE CAMARA UVC..."
            txt_sub = "Hot-Plug Activo · Conecte la camara al USB Host nativo"
            box_col = (0, 165, 255)

        cv2.rectangle(canvas, (vid_x, vid_y), (vid_x + vid_w, vid_y + vid_h), box_col, 2)
        cv2.putText(canvas, txt_status, (vid_x + 50, vid_y + vid_h // 2 - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.68, box_col, 2, cv2.LINE_AA)
        cv2.putText(canvas, txt_sub, (vid_x + 60, vid_y + vid_h // 2 + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 180, 180), 1, cv2.LINE_AA)

    cv2.rectangle(canvas, (vid_x, vid_y), (vid_x + vid_w, vid_y + vid_h), (100, 100, 100), 1)

    # -------------------------------------------------------------
    # 2. PANEL DE TELEMETRÍA AMBIENTAL Y OSCILOSCOPIO (Derecha)
    # -------------------------------------------------------------
    with gas_rx.lock:
        d = dict(gas_rx.latest_data)
        hist_ema = list(gas_rx.history_ema)

    px = vid_x + vid_w + 20
    cy = 60

    # Tarjeta 1: Nivel de Concentración y Alarma
    gas_pct = d["gas_pct"]
    ratio = d["ratio"]
    v_ema = d["v_ema"]
    v_raw = d["v_raw"]
    v_med = d["v_med"]
    rs = d["rs"]
    r0 = d["r0"]
    is_calib = d["calib"]
    rate_hz = d["rate_hz"]

    if gas_pct > 60.0:
        bar_col = (0, 0, 255)        # Rojo BGR
        alarm_txt = "PELIGRO: ALTA TOXICIDAD"
    elif gas_pct > 30.0:
        bar_col = (0, 165, 255)      # Naranja BGR
        alarm_txt = "PRECAUCION: GAS PRESENTE"
    else:
        bar_col = (0, 255, 0)        # Verde BGR
        alarm_txt = "NORMAL: AIRE LIMPIO"

    cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 80), (15, 23, 42), -1)
    cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 80), (51, 65, 85), 1)

    cv2.putText(canvas, "CONCENTRACION:", (px + 15, cy + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (148, 163, 184), 1, cv2.LINE_AA)
    if is_calib:
        cv2.putText(canvas, "CALIBRANDO...", (px + 140, cy + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, (11, 158, 245), 2, cv2.LINE_AA)
    else:
        cv2.putText(canvas, f"{gas_pct:.1f} %", (px + 140, cy + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, bar_col, 2, cv2.LINE_AA)

    cv2.putText(canvas, f"[{alarm_txt}]", (px + 265, cy + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, bar_col, 1, cv2.LINE_AA)

    # Barra gráfica de gas
    bar_x = px + 15
    bar_y = cy + 44
    bar_w = (w_total - 15) - bar_x - 15
    bar_h = 24
    cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (30, 41, 59), -1)
    cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (71, 85, 105), 1)
    fill_w = int((gas_pct / 100.0) * bar_w) if not is_calib else int(bar_w * 0.5)
    if fill_w > 0:
        cv2.rectangle(canvas, (bar_x + 1, bar_y + 1), (bar_x + fill_w - 1, bar_y + bar_h - 1), bar_col, -1)

    # Tarjeta 2: Voltajes y Resistencias
    cy = 155
    cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 105), (15, 23, 42), -1)
    cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 105), (51, 65, 85), 1)

    cv2.putText(canvas, f"Voltaje EMA : {v_ema:.3f} V", (px + 15, cy + 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (240, 240, 240), 2, cv2.LINE_AA)
    cv2.putText(canvas, f"Raw: {v_raw:.3f}V | Mediana: {v_med:.3f}V", (px + 15, cy + 48),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (148, 163, 184), 1, cv2.LINE_AA)

    cv2.putText(canvas, f"Rs: {rs/1000.0:.2f} kOhm | R0: {r0/1000.0:.2f} kOhm", (px + 15, cy + 74),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (56, 189, 248), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"Ratio R0 / Rs: {ratio:.3f}", (px + 15, cy + 96),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 215, 0), 2, cv2.LINE_AA)

    # Tarjeta 3: Osciloscopio en Vivo
    cy = 275
    cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 195), (10, 15, 25), -1)
    cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 195), (51, 65, 85), 1)
    cv2.putText(canvas, "OSCILOSCOPIO VOLTAJE Vout (0.0 V - 3.14 V)", (px + 15, cy + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (148, 163, 184), 1, cv2.LINE_AA)

    plot_x = px + 40
    plot_y = cy + 32
    plot_w = (w_total - 15) - plot_x - 15
    plot_h = 145

    for v_ref in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
        y_line = int(plot_y + plot_h - (v_ref / 3.14) * plot_h)
        cv2.line(canvas, (plot_x, y_line), (plot_x + plot_w, y_line), (35, 45, 60), 1)
        cv2.putText(canvas, f"{v_ref:.1f}V", (px + 5, y_line + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (100, 116, 139), 1)

    if len(hist_ema) > 1:
        pts = []
        step_x = plot_w / 120.0
        for i, val in enumerate(hist_ema):
            val_clamped = max(0.0, min(3.14, val))
            px_pt = int(plot_x + i * step_x)
            py_pt = int(plot_y + plot_h - (val_clamped / 3.14) * plot_h)
            pts.append((px_pt, py_pt))
        for i in range(len(pts) - 1):
            cv2.line(canvas, pts[i], pts[i+1], (56, 189, 248), 2)

    # Mini badge de telemetría de tasa
    cv2.putText(canvas, f"UDP Gas: {rate_hz:.1f} Hz", (w_total - 160, cy + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (100, 180, 255), 1, cv2.LINE_AA)

    # Tarjeta 4: Estado de la Luz de Inspección
    cy_light = 485
    cv2.rectangle(canvas, (px, cy_light), (w_total - 15, cy_light + 55), (15, 23, 42), -1)
    cv2.rectangle(canvas, (px, cy_light), (w_total - 15, cy_light + 55), (51, 65, 85), 1)

    with light_ctrl.lock:
        light_on = light_ctrl.is_on
        last_light_msg = light_ctrl.last_msg
        light_msg_t = light_ctrl.msg_timestamp

    if light_on:
        badge_bg = (0, 215, 255)    # Amarillo brillante en BGR
        badge_txt_col = (0, 0, 0)
        badge_txt = "[ LUZ: ENCENDIDA ] (100% Blanco)"
    else:
        badge_bg = (40, 50, 65)     # Gris apagado
        badge_txt_col = (180, 190, 200)
        badge_txt = "[ LUZ: APAGADA ]"

    cv2.rectangle(canvas, (px + 15, cy_light + 12), (px + 280, cy_light + 44), badge_bg, -1)
    cv2.putText(canvas, badge_txt, (px + 25, cy_light + 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, badge_txt_col, 2, cv2.LINE_AA)
    cv2.putText(canvas, "Pulsa [L] para alternar", (px + 295, cy_light + 33),
                cv2.FONT_HERSHEY_SIMPLEX, 0.48, (148, 163, 184), 1, cv2.LINE_AA)

    # -------------------------------------------------------------
    # 3. BARRA SUPERIOR E INFERIOR
    # -------------------------------------------------------------
    cv2.rectangle(canvas, (0, 0), (w_total, 48), (15, 23, 42), -1)
    cv2.line(canvas, (0, 48), (w_total, 48), (56, 189, 248), 1)
    cv2.putText(canvas, "ESP32-S3 · SISTEMA INTEGRADO V8: VISION UVC + GAS + CONTROL DE LUZ", (20, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.68, (255, 255, 255), 2, cv2.LINE_AA)

    # Indicador de luz superior
    if light_on:
        cv2.putText(canvas, "● LUZ ON", (w_total - 140, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 255), 2, cv2.LINE_AA)
    else:
        cv2.putText(canvas, "○ LUZ OFF", (w_total - 140, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (120, 120, 120), 1, cv2.LINE_AA)

    cv2.rectangle(canvas, (0, h_total - 42), (w_total, h_total), (15, 23, 42), -1)
    cv2.line(canvas, (0, h_total - 42), (w_total, h_total - 42), (51, 65, 85), 1)

    footer_txt = "[L] Alternar Luz ON/OFF   |   [C] Calibrar R0   |   [S] Captura Pantalla   |   [E] Exportar CSV   |   [Q] Salir"
    cv2.putText(canvas, footer_txt, (25, h_total - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, (203, 213, 225), 1, cv2.LINE_AA)

    if is_calib:
        cv2.putText(canvas, ">> CALIBRANDO R0 EN AIRE LIMPIO... <<", (px + 40, h_total - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (11, 158, 245), 2, cv2.LINE_AA)
    elif time.time() - calib_message_time < 3.0:
        cv2.putText(canvas, ">> R0 CALIBRADO EXITOSAMENTE <<", (px + 50, h_total - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (34, 197, 94), 2, cv2.LINE_AA)
    elif time.time() - light_msg_t < 2.5:
        cv2.putText(canvas, f">> {last_light_msg} <<", (px + 70, h_total - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 255, 255), 2, cv2.LINE_AA)


def send_calibration_request(calib_url):
    try:
        req = urllib.request.Request(
            calib_url,
            headers={'User-Agent': 'ESP32Visor-Python', 'Connection': 'close'}
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            safe_print(f"[CALIB-TCP] Solicitud de calibracion enviada a {calib_url}: {resp.status}")
    except Exception as e:
        safe_print(f"[CALIB-TCP] Error al calibrar: {e}")


def export_csv(records):
    if not records:
        safe_print("[EXPORT] No hay registros para exportar.")
        return
    filename = f"telemetria_camara_gas_{int(time.time())}.csv"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write("Timestamp,V_Raw,V_Mediana,V_EMA,Rs_Ohm,R0_Ohm,Ratio,Gas_Pct,Seq\n")
            for r in records:
                f.write(f"{r['t']},{r['v_raw']:.3f},{r['v_med']:.3f},{r['v_ema']:.3f},{r['rs']:.1f},{r['r0']:.1f},{r['ratio']:.3f},{r['gas_pct']:.1f},{r.get('seq', 0)}\n")
        safe_print(f"[+] Archivo CSV exportado con exito: {filename}")
    except Exception as e:
        safe_print(f"[-] Error exportando CSV: {e}")


def main():
    arg_target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOST

    clean_host = arg_target.replace("http://", "").replace("https://", "").split("/")[0]
    if ":" in clean_host:
        host_ip = clean_host.split(":")[0]
    else:
        host_ip = clean_host

    stream_url = f"http://{host_ip}:81/stream"
    calib_url = f"http://{host_ip}:80/calibrate"

    print("=" * 80)
    print(" [*] Visor Hibrido ESP32-S3 V8: Camara UVC (TCP), Gas (UDP) & Luz LED (WS2812)")
    print(f" [*] Video MJPEG Stream (TCP Puerto 81):  {stream_url}")
    print(f" [*] Telemetria de Gas (UDP Puerto 5005):  0.0.0.0:{GAS_UDP_PORT}")
    print(f" [*] Control Calibracion (TCP Puerto 80):  {calib_url}")
    print(f" [*] Control Luz LED     (TCP Puerto 80):  http://{host_ip}:80/light")
    print(" [*] Atajos de Teclado:")
    print("       'L' : Alternar Encendido / Apagado de Luz LED de Inspeccion")
    print("       'C' : Calibrar R0 en Aire Limpio")
    print("       'S' : Captura de pantalla (.png)")
    print("       'E' : Exportar historial a CSV")
    print("       'Q' : Salir")
    print("=" * 80)

    window_name = "ESP32-S3 · Hexapodo Secundario: Camara UVC + Gas + Luz LED"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    # Iniciar subsistemas desacoplados
    video_rx = VideoStreamReceiver(stream_url)
    gas_rx = GasTelemetryReceiverUDP(port=GAS_UDP_PORT)
    light_ctrl = LightController(host_ip)

    video_rx.start()
    gas_rx.start()

    canvas = np.zeros((600, 1120, 3), dtype=np.uint8)
    last_calib_time = 0.0

    try:
        while True:
            draw_hud(canvas, video_rx, gas_rx, light_ctrl, last_calib_time)
            cv2.imshow(window_name, canvas)

            key = cv2.waitKey(30) & 0xFF
            if key == 27 or key == ord('q') or key == ord('Q'):
                break
            elif key == ord('l') or key == ord('L'):
                light_ctrl.toggle()
            elif key == ord('c') or key == ord('C'):
                threading.Thread(target=send_calibration_request, args=(calib_url,), daemon=True).start()
                last_calib_time = time.time()
            elif key == ord('s') or key == ord('S'):
                snap_name = f"captura_con_luz_{int(time.time())}.png"
                cv2.imwrite(snap_name, canvas)
                safe_print(f"[+] Captura guardada como {snap_name}")
            elif key == ord('e') or key == ord('E'):
                with gas_rx.lock:
                    recs = list(gas_rx.records_to_export)
                export_csv(recs)

            try:
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    break
            except Exception:
                pass

    finally:
        video_rx.stop()
        gas_rx.stop()
        cv2.destroyAllWindows()
        safe_print("[*] Visor con control de luz finalizado correctamente.")

if __name__ == "__main__":
    main()
