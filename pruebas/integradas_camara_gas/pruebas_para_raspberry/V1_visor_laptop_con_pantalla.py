"""
========================================================================================
Visor Integrado de Video UVC y Telemetría de Gases MiCS-5524 para ESP32-S3 (OpenCV)
Tesis de Ingeniería Mecatrónica - UTEC 2026
Autores: Aleskyjubinsl Alcarraz, Flavio Alarcón, Alfredo Erazo
Asesor: Dante Inga Narváez

Arquitectura Híbrida de Máximo Rendimiento:
  - Video UVC MJPEG (TCP en Puerto 81): http://192.168.4.1:81/stream
  - Sensor de Gas (UDP Datagramas 20 Hz): Puerto UDP 5005
  - Control de Calibración R0 (HTTP TCP): http://192.168.4.1:80/calibrate
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

                    # Limitar crecimiento de buffer
                    if len(bytes_buffer) > 256 * 1024:
                        last_frame = bytes_buffer.rfind(b'--frame')
                        if last_frame != -1:
                            bytes_buffer = bytes_buffer[last_frame:]
                        else:
                            bytes_buffer.clear()

                stream.close()
            except Exception:
                self.connected = False
                time.sleep(0.5)


class GasTelemetryReceiverUDP:
    """Hilo receptor de telemetría de gases por datagramas UDP (Puerto 5005, Cero Sobrecarga)"""
    def __init__(self, port=GAS_UDP_PORT):
        self.port = port
        self.running = False
        self.connected = False
        self.lock = threading.Lock()
        self.data = {
            "v_raw": 0.0,
            "v_med": 0.0,
            "v_ema": 0.0,
            "rs": 0.0,
            "r0": 0.0,
            "ratio": 1.0,
            "gas_pct": 0.0,
            "calibrating": True,
            "seq": 0,
            "timestamp": time.time()
        }
        self.history_v_ema = []
        self.history_v_med = []
        self.records_to_export = []
        self.thread = None

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _worker(self):
        safe_print(f"[GAS-UDP] Abriendo socket de escucha UDP en puerto {self.port}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', self.port))
            sock.settimeout(1.0) # 1 segundo sin datos indica desconexion
            safe_print(f"[GAS-UDP] Socket UDP escuchando activamente en 0.0.0.0:{self.port}")
        except Exception as e:
            safe_print(f"[GAS-UDP] Error vinculando puerto UDP {self.port}: {e}")
            return

        while self.running:
            try:
                raw_bytes, addr = sock.recvfrom(2048)
                if raw_bytes:
                    payload = raw_bytes.decode('utf-8', errors='replace')
                    d = json.loads(payload)
                    d["timestamp"] = time.time()

                    with self.lock:
                        self.data = d
                        self.connected = True
                        self.history_v_ema.append(d.get("v_ema", 0.0))
                        self.history_v_med.append(d.get("v_med", 0.0))
                        if len(self.history_v_ema) > 120:
                            self.history_v_ema.pop(0)
                            self.history_v_med.pop(0)

                        self.records_to_export.append({
                            "t": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                            "v_raw": d.get("v_raw", 0.0),
                            "v_med": d.get("v_med", 0.0),
                            "v_ema": d.get("v_ema", 0.0),
                            "rs": d.get("rs", 0.0),
                            "r0": d.get("r0", 0.0),
                            "ratio": d.get("ratio", 0.0),
                            "gas_pct": d.get("gas_pct", 0.0),
                            "seq": d.get("seq", 0)
                        })
            except socket.timeout:
                with self.lock:
                    self.connected = False
            except Exception:
                pass

        sock.close()


def draw_hud(canvas, video_rx, gas_rx, calib_message_time):
    canvas.fill(20)

    h_total, w_total = canvas.shape[:2]

    # -------------------------------------------------------------
    # 1. ZONA IZQUIERDA: Video UVC de la Cámara (640 x 480)
    # -------------------------------------------------------------
    vid_x, vid_y = 15, 60
    vid_w, vid_h = 640, 480

    with video_rx.lock:
        frame = video_rx.latest_frame
        fps = video_rx.fps
        kb_sec = video_rx.kb_sec
        v_conn = video_rx.connected
        frames_cnt = video_rx.total_frames
        is_standby = video_rx.is_standby

    if frame is not None and v_conn and not is_standby and frame.shape[0] >= 30:
        frame_resized = cv2.resize(frame, (vid_w, vid_h))
        canvas[vid_y:vid_y+vid_h, vid_x:vid_x+vid_w] = frame_resized

        cv2.rectangle(canvas, (vid_x, vid_y), (vid_x + vid_w, vid_y + 32), (10, 10, 10), -1)
        info_txt = f"UVC TCP {frame.shape[1]}x{frame.shape[0]} | {fps:.1f} FPS | {kb_sec:.1f} KB/s | #{frames_cnt}"
        cv2.putText(canvas, info_txt, (vid_x + 10, vid_y + 22),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (56, 189, 248), 2, cv2.LINE_AA)
    else:
        cv2.rectangle(canvas, (vid_x, vid_y), (vid_x + vid_w, vid_y + vid_h), (20, 27, 38), -1)
        cv2.rectangle(canvas, (vid_x, vid_y), (vid_x + vid_w, vid_y + vid_h), (51, 65, 85), 2)
        cv2.putText(canvas, "[ CAMARA UVC EN ESPERA ]", (vid_x + 140, vid_y + 200),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (245, 158, 11), 2, cv2.LINE_AA)
        cv2.putText(canvas, "Sensor de gases operando por UDP en tiempo real", (vid_x + 85, vid_y + 245),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.58, (34, 197, 94), 1, cv2.LINE_AA)
        cv2.putText(canvas, "Conecta la camara al puerto USB nativo del ESP32-S3", (vid_x + 75, vid_y + 285),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (148, 163, 184), 1, cv2.LINE_AA)
        cv2.putText(canvas, "La transmision iniciara automaticamente al detectarla", (vid_x + 80, vid_y + 315),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (56, 189, 248), 1, cv2.LINE_AA)

    # -------------------------------------------------------------
    # 2. ZONA DERECHA: Telemetría de Gases MiCS-5524 (UDP)
    # -------------------------------------------------------------
    px = 675
    with gas_rx.lock:
        g = gas_rx.data
        g_conn = gas_rx.connected
        hist_ema = list(gas_rx.history_v_ema)

    gas_pct = g.get("gas_pct", 0.0)
    v_ema = g.get("v_ema", 0.0)
    v_raw = g.get("v_raw", 0.0)
    v_med = g.get("v_med", 0.0)
    rs = g.get("rs", 0.0)
    r0 = g.get("r0", 0.0)
    ratio = g.get("ratio", 1.0)
    is_calib = g.get("calibrating", False)
    seq = g.get("seq", 0)

    # Encabezado Panel Gas
    cv2.rectangle(canvas, (px, 60), (w_total - 15, 115), (30, 41, 59), -1)
    cv2.rectangle(canvas, (px, 60), (w_total - 15, 115), (51, 65, 85), 1)
    cv2.putText(canvas, "SENSOR DE GASES (MiCS-5524)", (px + 12, 85),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (56, 189, 248), 2, cv2.LINE_AA)

    status_str = f"EN LINEA (UDP 20 Hz) #{seq}" if g_conn else "DESCONECTADO (Sin UDP)"
    status_col = (34, 197, 94) if g_conn else (68, 68, 239)
    cv2.putText(canvas, status_str, (px + 12, 105),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_col, 2, cv2.LINE_AA)

    # Tarjeta 1: Intensidad / Nivel de Detección de Gas (%)
    cy = 125
    cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 90), (15, 23, 42), -1)
    cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 90), (51, 65, 85), 1)

    if is_calib:
        bar_col = (11, 158, 245)
        alarm_txt = "CALIBRANDO R0"
    elif gas_pct > 70.0:
        bar_col = (68, 68, 239)
        alarm_txt = "PELIGRO / ALARMA"
    elif gas_pct > 40.0:
        bar_col = (11, 158, 245)
        alarm_txt = "ADVERTENCIA"
    elif gas_pct > 15.0:
        bar_col = (14, 200, 240)
        alarm_txt = "MODERADO"
    else:
        bar_col = (34, 197, 94)
        alarm_txt = "NORMAL / LIMPIO"

    cv2.putText(canvas, "NIVEL DE GAS:", (px + 15, cy + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (148, 163, 184), 1, cv2.LINE_AA)

    if is_calib:
        cv2.putText(canvas, "CALIBRANDO", (px + 140, cy + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, bar_col, 2, cv2.LINE_AA)
    else:
        cv2.putText(canvas, f"{gas_pct:.1f} %", (px + 140, cy + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.85, bar_col, 2, cv2.LINE_AA)

    cv2.putText(canvas, f"[{alarm_txt}]", (px + 265, cy + 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, bar_col, 1, cv2.LINE_AA)

    # Barra gráfica de gas
    bar_x = px + 15
    bar_y = cy + 48
    bar_w = (w_total - 15) - bar_x - 15
    bar_h = 24
    cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (30, 41, 59), -1)
    cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (71, 85, 105), 1)
    fill_w = int((gas_pct / 100.0) * bar_w) if not is_calib else int(bar_w * 0.5)
    if fill_w > 0:
        cv2.rectangle(canvas, (bar_x + 1, bar_y + 1), (bar_x + fill_w - 1, bar_y + bar_h - 1), bar_col, -1)

    # Tarjeta 2: Voltajes y Resistencias
    cy = 225
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
    cy = 340
    cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 200), (10, 15, 25), -1)
    cv2.rectangle(canvas, (px, cy), (w_total - 15, cy + 200), (51, 65, 85), 1)
    cv2.putText(canvas, "OSCILOSCOPIO VOLTAJE Vout (0.0 V - 3.14 V)", (px + 15, cy + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (148, 163, 184), 1, cv2.LINE_AA)

    plot_x = px + 40
    plot_y = cy + 32
    plot_w = (w_total - 15) - plot_x - 15
    plot_h = 150

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

    # -------------------------------------------------------------
    # 3. BARRA SUPERIOR E INFERIOR
    # -------------------------------------------------------------
    cv2.rectangle(canvas, (0, 0), (w_total, 48), (15, 23, 42), -1)
    cv2.line(canvas, (0, 48), (w_total, 48), (56, 189, 248), 1)
    cv2.putText(canvas, "ESP32-S3 · SUBSISTEMA HIBRIDO: VISION UVC (TCP) & GAS (UDP)", (20, 32),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)

    cv2.rectangle(canvas, (0, h_total - 42), (w_total, h_total), (15, 23, 42), -1)
    cv2.line(canvas, (0, h_total - 42), (w_total, h_total - 42), (51, 65, 85), 1)

    footer_txt = "[C] Calibrar R0 (Aire Limpio)   |   [S] Captura Pantalla   |   [E] Exportar CSV   |   [Q] Salir"
    cv2.putText(canvas, footer_txt, (25, h_total - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (203, 213, 225), 1, cv2.LINE_AA)

    if is_calib:
        cv2.putText(canvas, ">> CALIBRANDO R0 EN AIRE LIMPIO... <<", (px + 40, h_total - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (11, 158, 245), 2, cv2.LINE_AA)
    elif time.time() - calib_message_time < 3.0:
        cv2.putText(canvas, ">> R0 CALIBRADO EXITOSAMENTE <<", (px + 50, h_total - 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (34, 197, 94), 2, cv2.LINE_AA)


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

    print("=" * 75)
    print(" [*] Visor Hibrido ESP32-S3: Camara UVC (TCP) & Gas MiCS-5524 (UDP)")
    print(f" [*] Video MJPEG Stream (TCP Puerto 81):  {stream_url}")
    print(f" [*] Telemetria de Gas (UDP Puerto 5005):  0.0.0.0:{GAS_UDP_PORT}")
    print(f" [*] Control Calibracion (TCP Puerto 80):  {calib_url}")
    print(" [*] Atajos:")
    print("       'c' : Calibrar R0 en Aire Limpio")
    print("       's' : Captura de pantalla (.png)")
    print("       'e' : Exportar historial a CSV")
    print("       'q' : Salir")
    print("=" * 75)

    window_name = "ESP32-S3 · Hexapodo Secundario: Camara UVC & Gas MiCS-5524"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    # Iniciar hilos desacoplados (Video TCP + Gas UDP)
    video_rx = VideoStreamReceiver(stream_url)
    gas_rx = GasTelemetryReceiverUDP(port=GAS_UDP_PORT)

    video_rx.start()
    gas_rx.start()

    canvas = np.zeros((600, 1120, 3), dtype=np.uint8)
    last_calib_time = 0.0

    try:
        while True:
            draw_hud(canvas, video_rx, gas_rx, last_calib_time)
            cv2.imshow(window_name, canvas)

            key = cv2.waitKey(30) & 0xFF
            if key == 27 or key == ord('q') or key == ord('Q'):
                break
            elif key == ord('c') or key == ord('C'):
                threading.Thread(target=send_calibration_request, args=(calib_url,), daemon=True).start()
                last_calib_time = time.time()
            elif key == ord('s') or key == ord('S'):
                snap_name = f"captura_integrada_{int(time.time())}.png"
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
        safe_print("[*] Visor integrado finalizado correctamente.")

if __name__ == "__main__":
    main()
