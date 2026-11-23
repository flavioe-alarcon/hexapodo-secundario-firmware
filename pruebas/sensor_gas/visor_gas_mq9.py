"""
========================================================================================
Visor y Monitor de Telemetria en Tiempo Real para Sensor de Gas MQ-9 & ACS758
Plataforma: Arduino Nano (ATmega328P @ 16 MHz) en puerto COM15 / 115200 baud
Tesis de Ingenieria Mecatronica - UTEC 2026
Autores: Aleskyjubinsl Alcarraz, Flavio Alarcon, Alfredo Erazo
Asesor: Dante Inga Narvaez

Robot: Hexapodo Primario / Banco de Ensayos
Metricas:
  - Sensor MQ-9: Voltaje A0, Ratio R0/Rs, Alarma Digital D0 (Potenciometro)
  - Sensor ACS758: Corriente (A), Voltaje A1, Potencia (W)
========================================================================================
"""

import sys
import os
import time
import json
import threading
import datetime
import serial
import serial.tools.list_ports
import cv2
import numpy as np

# Soporte UTF-8 en Windows
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

def find_default_port():
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        if "COM15" in p.device or "FT232" in p.description or "0403:6001" in p.hwid:
            return p.device
    for p in ports:
        if "USB" in p.description or "Serial" in p.description:
            return p.device
    return "COM15"

class MQ9Receiver:
    def __init__(self, port="COM15", baud=115200):
        self.port = port
        self.baud = baud
        self.running = False
        self.connected = False
        self.lock = threading.Lock()
        self.ser = None
        
        self.latest = {
            "t": 0,
            "gas_v": 0.0,
            "gas_raw": 0.0,
            "gas_ratio": 1.0,
            "rs_r0": 1.0,
            "ppm_alc": 0.0,
            "ppm_co": 0.0,
            "gas_alerta": 0,
            "i_amp": 0.0,
            "i_v": 2.500,
            "pot_w": 0.0
        }
        self.status_msg = "Iniciando..."
        self.calibrated = False

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass

    def send_cmd(self, cmd):
        if self.ser and self.ser.is_open:
            try:
                self.ser.write(cmd.encode('ascii'))
                safe_print(f"[CMD] Comando enviado: {cmd}")
            except Exception as e:
                safe_print(f"[-] Error enviando comando: {e}")

    def _run(self):
        while self.running:
            try:
                safe_print(f"[+] Conectando a {self.port} @ {self.baud} baud...")
                self.ser = serial.Serial(self.port, self.baud, timeout=1.0)
                time.sleep(1.8) # Reset de Arduino al abrir DTR
                self.connected = True
                self.status_msg = f"Conectado a {self.port}"
                safe_print(f"[+] Conexion establecida en {self.port}")

                while self.running and self.ser.is_open:
                    line = self.ser.readline().decode('utf-8', errors='ignore').strip()
                    if not line:
                        continue
                    if line.startswith("{") and line.endswith("}"):
                        try:
                            data = json.loads(line)
                            with self.lock:
                                if "status" in data and data["status"] == "calibrado":
                                    self.calibrated = True
                                    self.status_msg = "Sensores Calibrados OK"
                                else:
                                    for k in self.latest:
                                        if k in data:
                                            self.latest[k] = data[k]
                                    self.status_msg = "Adquiriendo datos"
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                self.connected = False
                self.status_msg = f"Error: {e}"
                time.sleep(2.0)
            finally:
                if self.ser and self.ser.is_open:
                    try:
                        self.ser.close()
                    except Exception:
                        pass
                self.connected = False

def draw_header(img, w, connected, status_msg, recording):
    cv2.rectangle(img, (0, 0), (w, 55), (20, 24, 30), -1)
    cv2.line(img, (0, 55), (w, 55), (45, 55, 72), 2)

    cv2.putText(img, "MONITOR DE GAS MQ-9 & CORRIENTE ACS758", (20, 32),
                cv2.FONT_HERSHEY_DUPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(img, "UTEC 2026 - Tesis Mecatronica | Robot Primario", (20, 48),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 174, 192), 1, cv2.LINE_AA)

    # Estado de conexion
    dot_color = (0, 220, 100) if connected else (0, 50, 220)
    cv2.circle(img, (w - 230, 28), 6, dot_color, -1, cv2.LINE_AA)
    cv2.putText(img, status_msg[:22], (w - 215, 33),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (226, 232, 240), 1, cv2.LINE_AA)

    # Indicador de Grabacion CSV
    if recording:
        cv2.circle(img, (w - 20, 28), 7, (0, 0, 240), -1, cv2.LINE_AA)
        cv2.putText(img, "REC", (w - 65, 33),
                    cv2.FONT_HERSHEY_DUPLEX, 0.45, (0, 0, 255), 1, cv2.LINE_AA)

def draw_card(img, x, y, w, h, title, val_str, unit_str, color=(0, 200, 255), sub_str=""):
    cv2.rectangle(img, (x, y), (x + w, y + h), (26, 32, 44), -1)
    cv2.rectangle(img, (x, y), (x + w, y + h), (45, 55, 72), 1)

    cv2.putText(img, title.upper(), (x + 12, y + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (160, 174, 192), 1, cv2.LINE_AA)

    cv2.putText(img, val_str, (x + 12, y + 54),
                cv2.FONT_HERSHEY_DUPLEX, 0.95, color, 2, cv2.LINE_AA)

    if unit_str:
        (tw, _), _ = cv2.getTextSize(val_str, cv2.FONT_HERSHEY_DUPLEX, 0.95, 2)
        cv2.putText(img, unit_str, (x + 16 + tw, y + 52),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.48, (203, 213, 225), 1, cv2.LINE_AA)

    if sub_str:
        cv2.putText(img, sub_str, (x + 12, y + 74),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (148, 163, 184), 1, cv2.LINE_AA)

def main():
    port = sys.argv[1] if len(sys.argv) > 1 else find_default_port()
    safe_print(f"==================================================")
    safe_print(f" Iniciando Visor de Gas MQ-9 & Corriente ACS758")
    safe_print(f" Puerto: {port} | Baud: 115200")
    safe_print(f"==================================================")

    receiver = MQ9Receiver(port=port, baud=115200)
    receiver.start()

    W, H = 1050, 680
    win_name = "Monitor de Gas MQ-9 & Corriente ACS758 - UTEC 2026"
    cv2.namedWindow(win_name, cv2.WINDOW_AUTOSIZE)

    # Buffers para graficas temporales
    history_len = 220
    hist_gas_v = [0.0] * history_len
    hist_ratio = [1.0] * history_len
    hist_current = [0.0] * history_len

    recording = False
    csv_file = None
    csv_path = ""

    from pathlib import Path
    repo_root = Path(__file__).resolve().parents[2]
    datos_dir = repo_root / "pruebas" / "datos_mision"
    img_dir = repo_root / "pruebas" / "imagenes_experimentos"
    datos_dir.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)

    try:
        while True:
            t0 = time.time()
            with receiver.lock:
                data = dict(receiver.latest)
                connected = receiver.connected
                status_msg = receiver.status_msg

            # Actualizar buffers
            hist_gas_v.pop(0)
            hist_gas_v.append(data["gas_v"])

            hist_ratio.pop(0)
            hist_ratio.append(data["gas_ratio"])

            hist_current.pop(0)
            hist_current.append(data["i_amp"])

            # Grabar CSV si esta activo
            if recording and csv_file:
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                csv_file.write(f"{now_str},{data['t']},{data['gas_v']:.3f},{data['gas_raw']:.1f},"
                               f"{data['gas_ratio']:.3f},{data['gas_alerta']},{data['i_amp']:.2f},"
                               f"{data['i_v']:.3f},{data['pot_w']:.2f}\n")
                csv_file.flush()

            # Renderizado de UI
            canvas = np.zeros((H, W, 3), dtype=np.uint8)
            canvas[:] = (15, 18, 22) # Fondo oscuro

            draw_header(canvas, W, connected, status_msg, recording)

            # Tarjetas de Gas MQ-9
            draw_card(canvas, 20, 70, 235, 88, "Voltaje de Gas (A0)", f"{data['gas_v']:.3f}", "V", (0, 210, 255), f"ADC: {data['gas_raw']:.0f} / 1023 | Rs/R0: {data.get('rs_r0', 1.0):.2f}")
            
            # Tarjeta de PPM de Etanol (Alcohol)
            ppm_alc = data.get("ppm_alc", 0.0)
            alc_color = (0, 230, 100) if ppm_alc < 100.0 else ((0, 180, 255) if ppm_alc < 500.0 else (0, 50, 255))
            draw_card(canvas, 270, 70, 245, 88, "Concentracion Etanol", f"{ppm_alc:.1f}", "ppm", alc_color, f"Modelo MQ-9 (7630*(Rs/R0)^-2.32)")

            # Tarjeta de PPM de CO / Alarma Digital
            ppm_co = data.get("ppm_co", 0.0)
            alerta = data["gas_alerta"]
            alert_color = (0, 0, 230) if alerta == 1 else (0, 200, 80)
            alert_text = "!ALERTA!" if alerta == 1 else "NORMAL"
            draw_card(canvas, 530, 70, 245, 88, "CO Estimado / Alarma", f"{ppm_co:.1f}", "ppm", alert_color, f"D0: {alert_text} | CO ref. Mineria")

            # Tarjeta de Corriente ACS758
            draw_card(canvas, 790, 70, 240, 88, "Corriente Bateria", f"{data['i_amp']:.2f}", "A", (255, 180, 50), f"P: {data['pot_w']:.1f} W (LiPo 3S)")

            # --- Barra Horizontal de Intensidad de Gas ---
            bar_x, bar_y, bar_w, bar_h = 20, 172, W - 40, 32
            cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (26, 32, 44), -1)
            cv2.rectangle(canvas, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (45, 55, 72), 1)

            # Porcentaje relativo (0V = 0%, 4.5V = 100%)
            pct_gas = np.clip((data["gas_v"] - 0.5) / 3.5, 0.0, 1.0)
            fill_w = int(bar_w * pct_gas)
            
            # Gradiente simple
            bar_color = (0, 220, 120) if pct_gas < 0.3 else ((0, 200, 255) if pct_gas < 0.65 else (0, 30, 255))
            if fill_w > 0:
                cv2.rectangle(canvas, (bar_x + 1, bar_y + 1), (bar_x + fill_w, bar_y + bar_h - 1), bar_color, -1)

            pct_text = f"Etanol: {ppm_alc:.1f} ppm | CO: {ppm_co:.1f} ppm | Intensidad: {int(pct_gas * 100)}% ({data['gas_v']:.2f} V)"
            cv2.putText(canvas, pct_text, (bar_x + 15, bar_y + 21),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)

            # --- Grafica 1: Osciloscopio de Voltaje de Gas A0 (220 px alto) ---
            gx, gy, gw, gh = 20, 220, W - 40, 190
            cv2.rectangle(canvas, (gx, gy), (gx + gw, gy + gh), (20, 24, 30), -1)
            cv2.rectangle(canvas, (gx, gy), (gx + gw, gy + gh), (45, 55, 72), 1)

            cv2.putText(canvas, "CURVA DE VOLTAJE DE GAS MQ-9 [A0] (0.0 V - 5.0 V)", (gx + 12, gy + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 220, 255), 1, cv2.LINE_AA)

            # Lineas de grilla de voltaje
            for v_grid in [1.0, 2.0, 3.0, 4.0]:
                y_line = int(gy + gh - (v_grid / 5.0) * (gh - 30) - 10)
                cv2.line(canvas, (gx, y_line), (gx + gw, y_line), (35, 42, 54), 1)
                cv2.putText(canvas, f"{v_grid:.1f}V", (gx + gw - 35, y_line - 3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.32, (100, 116, 139), 1)

            # Trazar curva de gas
            pts_gas = []
            for i, val in enumerate(hist_gas_v):
                px = int(gx + (i / float(history_len - 1)) * gw)
                py = int(gy + gh - (val / 5.0) * (gh - 30) - 10)
                py = np.clip(py, gy + 5, gy + gh - 5)
                pts_gas.append((px, py))
            if len(pts_gas) > 1:
                cv2.polylines(canvas, [np.array(pts_gas, dtype=np.int32)], False, (0, 220, 255), 2, cv2.LINE_AA)

            # --- Grafica 2: Curva de Ratio R0/Rs y Corriente Instantanea ---
            g2x, g2y, g2w, g2h = 20, 425, W - 40, 190
            cv2.rectangle(canvas, (g2x, g2y), (g2x + g2w, g2y + g2h), (20, 24, 30), -1)
            cv2.rectangle(canvas, (g2x, g2y), (g2x + g2w, g2y + g2h), (45, 55, 72), 1)

            cv2.putText(canvas, "RATIO RELATIVO DE CONCENTRACION (R0/Rs) [AMARILLO] & CORRIENTE (A) [AZUL]", (g2x + 12, g2y + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 230, 100), 1, cv2.LINE_AA)

            # Grilla para ratio (escala 0.0x a 6.0x)
            for r_grid in [1.0, 2.0, 3.0, 4.0, 5.0]:
                y_line = int(g2y + g2h - (r_grid / 6.0) * (g2h - 30) - 10)
                cv2.line(canvas, (g2x, y_line), (g2x + g2w, y_line), (35, 42, 54), 1)
                cv2.putText(canvas, f"{r_grid:.1f}x", (g2x + g2w - 35, y_line - 3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.32, (100, 116, 139), 1)

            pts_ratio = []
            for i, val in enumerate(hist_ratio):
                px = int(g2x + (i / float(history_len - 1)) * g2w)
                py = int(g2y + g2h - (val / 6.0) * (g2h - 30) - 10)
                py = np.clip(py, g2y + 5, g2y + g2h - 5)
                pts_ratio.append((px, py))
            if len(pts_ratio) > 1:
                cv2.polylines(canvas, [np.array(pts_ratio, dtype=np.int32)], False, (0, 230, 255), 2, cv2.LINE_AA)

            # Trazar curva de corriente (Escala 0 a 10 A)
            pts_curr = []
            for i, val in enumerate(hist_current):
                px = int(g2x + (i / float(history_len - 1)) * g2w)
                py = int(g2y + g2h - (val / 10.0) * (g2h - 30) - 10)
                py = np.clip(py, g2y + 5, g2y + g2h - 5)
                pts_curr.append((px, py))
            if len(pts_curr) > 1:
                cv2.polylines(canvas, [np.array(pts_curr, dtype=np.int32)], False, (255, 160, 40), 1, cv2.LINE_AA)

            # Barra de Estado inferior / Atajos
            bar_bot_y = H - 35
            cv2.rectangle(canvas, (0, bar_bot_y), (W, H), (15, 18, 22), -1)
            cv2.line(canvas, (0, bar_bot_y), (W, bar_bot_y), (45, 55, 72), 1)
            help_str = "[C] Calibrar Cero | [R] Iniciar/Detener Grabacion CSV | [S] Captura PNG | [Q / ESC] Salir"
            cv2.putText(canvas, help_str, (20, H - 12),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (160, 174, 192), 1, cv2.LINE_AA)

            cv2.imshow(win_name, canvas)

            # Teclado interactivo
            key = cv2.waitKey(25) & 0xFF
            if key in [ord('q'), ord('Q'), 27]: # Q o ESC
                break
            elif key in [ord('c'), ord('C')]:
                receiver.send_cmd('c')
            elif key in [ord('s'), ord('S')]:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                shot_path = str(img_dir / f"captura_mq9_{timestamp}.png")
                cv2.imwrite(shot_path, canvas)
                safe_print(f"[+] Captura guardada en: {shot_path}")
            elif key in [ord('r'), ord('R')]:
                recording = not recording
                if recording:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    csv_path = str(datos_dir / f"registro_mq9_corriente_{timestamp}.csv")
                    csv_file = open(csv_path, "w", encoding="utf-8")
                    csv_file.write("fecha_hora,millis,gas_v,gas_raw,gas_ratio,gas_alerta,i_amp,i_v,pot_w\n")
                    safe_print(f"[+] Grabacion CSV iniciada: {csv_path}")
                else:
                    if csv_file:
                        csv_file.close()
                        csv_file = None
                        safe_print(f"[+] Grabacion CSV guardada y cerrada: {csv_path}")

    finally:
        if csv_file:
            csv_file.close()
        receiver.stop()
        cv2.destroyAllWindows()
        safe_print("[+] Visor cerrado correctamente.")

if __name__ == '__main__':
    main()
