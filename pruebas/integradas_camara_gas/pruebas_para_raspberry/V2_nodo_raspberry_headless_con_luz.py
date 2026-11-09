#!/usr/bin/env python3
"""
========================================================================================
PROYECTO FINAL DE CARRERA - INGENIERIA MECATRONICA - UTEC 2026
SISTEMA ROBOTICO COOPERATIVO DE INSPECCION EN MINERIA SUBTERRANEA
========================================================================================
Archivo : V2_nodo_raspberry_headless_con_luz.py
Equipo  : Hexapodo Primario (Raspberry Pi 5 - Ubuntu 22.04 LTS)
Rol     : Receptor y Supervisor Central de Mision con Control de Iluminacion LED
Entrada : 
  - Stream de Video UVC (TCP HTTP Multipart en Puerto 81)
  - Telemetria de Gas MiCS-5524 (Datagramas UDP a 20 Hz en Puerto 5005)
Salida  :
  - Control de Luz LED RGB WS2812 (HTTP TCP en Puerto 80: /light)
  - Registro de Caja Negra continuo en 'registro_mision_hexapodo.csv'
  - Telemetria estructurada en consola / terminal SSH
  - Puente automatico hacia topicos ROS 2 Humble (si rclpy esta disponible)
========================================================================================
"""

import sys
import os
import time
import json
import csv
import socket
import signal
import threading
import datetime
import urllib.request

# Compatibilidad UTF-8 universal (Windows cp1252 y Linux UTF-8)
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# ======================================================================================
# SECCION 1: CONFIGURACION MAESTRA DE RED Y PUERTOS
# ======================================================================================
ESP32_HOST          = "192.168.4.1"                     # IP fija del SoftAP en ESP32-S3
VIDEO_STREAM_URL    = f"http://{ESP32_HOST}:81/stream"   # Endpoint dedicado MJPEG (TCP)
GAS_UDP_PORT        = 5005                              # Puerto de escucha para el sensor de gas
LIGHT_URL           = f"http://{ESP32_HOST}:80/light"    # Endpoint HTTP para control de luz
CALIBRATE_URL       = f"http://{ESP32_HOST}:80/calibrate" # Endpoint HTTP para calibrar R0
LOG_FILE_PATH       = "registro_mision_hexapodo.csv"    # Destino de la caja negra

# Deteccion automatica de soporte ROS 2 Humble (Ubuntu 22.04)
ROS2_AVAILABLE = False
try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import Float32, String, Bool
    from sensor_msgs.msg import CompressedImage
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False


# ======================================================================================
# SECCION 2: EVALUADOR DE SEGURIDAD MINERA (D.S. N° 024-2016-EM)
# ======================================================================================
def evaluar_atmosfera_minera(ratio_r0_rs):
    if ratio_r0_rs < 1.30:
        return ("SEGURO", "Atmósfera limpia dentro de umbrales admisibles (D.S. 024-2016-EM)", (34, 197, 94))
    elif 1.30 <= ratio_r0_rs < 2.00:
        return ("ALERTA", "Presencia moderada de CO / gases reductores. Operar con cautela.", (234, 179, 8))
    else:
        return ("CRITICO", "Evacuar personal inmediatamente. Nivel letal / toxicidad critica.", (239, 68, 68))


# ======================================================================================
# SECCION 3: RECEPTOR DE VIDEO TCP (DESACOPLADO Y NO BLOQUEANTE)
# ======================================================================================
class ReceptorVideoTCP:
    def __init__(self, stream_url):
        self.stream_url = stream_url
        self.activo = False
        self.conectado = False
        self.ultimo_jpeg_bytes = None
        self.es_standby = True
        self.fps = 0.0
        self.kb_s = 0.0
        self.total_cuadros = 0
        self.lock = threading.Lock()
        self.hilo = None

    def iniciar(self):
        self.activo = True
        self.hilo = threading.Thread(target=self._hilo_lector, daemon=True)
        self.hilo.start()

    def detener(self):
        self.activo = False

    def _hilo_lector(self):
        bufer = bytearray()
        conteo_fps = 0
        temporizador = time.time()
        bytes_segundo = 0

        while self.activo:
            try:
                peticion = urllib.request.Request(self.stream_url, headers={'User-Agent': 'RaspberryPi5-Headless'})
                flujo = urllib.request.urlopen(peticion, timeout=3.5)
                self.conectado = True

                while self.activo:
                    bloque = flujo.read(4096)
                    if not bloque:
                        break
                    bytes_segundo += len(bloque)
                    bufer.extend(bloque)

                    while True:
                        pos_cl = bufer.find(b'Content-Length: ')
                        if pos_cl != -1:
                            fin_hdr = bufer.find(b'\r\n\r\n', pos_cl)
                            if fin_hdr != -1:
                                str_len = bufer[pos_cl + 16 : fin_hdr].decode('ascii', errors='ignore').strip()
                                try:
                                    longitud = int(str_len)
                                    inicio_jpeg = fin_hdr + 4
                                    if len(bufer) >= inicio_jpeg + longitud:
                                        jpeg_datos = bufer[inicio_jpeg : inicio_jpeg + longitud]
                                        bufer = bufer[inicio_jpeg + longitud :]
                                        es_espera = bool(longitud < 1000)

                                        with self.lock:
                                            self.ultimo_jpeg_bytes = bytes(jpeg_datos)
                                            self.es_standby = es_espera
                                            if not es_espera:
                                                self.total_cuadros += 1

                                        if not es_espera:
                                            conteo_fps += 1
                                            ahora = time.time()
                                            if ahora - temporizador >= 1.0:
                                                dt = ahora - temporizador
                                                self.fps = conteo_fps / dt
                                                self.kb_s = (bytes_segundo / 1024.0) / dt
                                                conteo_fps = 0
                                                bytes_segundo = 0
                                                temporizador = ahora
                                        continue
                                except ValueError:
                                    bufer = bufer[fin_hdr + 4 :]
                                    continue
                        break

            except Exception:
                self.conectado = False
                time.sleep(1.0)


# ======================================================================================
# SECCION 4: RECEPTOR DE TELEMETRIA DE GASES POR UDP
# ======================================================================================
class ReceptorGasesUDP:
    def __init__(self, puerto=5005):
        self.puerto = puerto
        self.activo = False
        self.lock = threading.Lock()
        self.datos = {
            "v_raw": 0.5, "v_med": 0.5, "v_ema": 0.5,
            "rs": 7500.0, "r0": 7500.0, "ratio": 1.0,
            "gas_pct": 0.0, "calib": False, "seq": 0,
            "tasa_hz": 0.0, "ultimo_ping": 0.0
        }
        self.hilo = None

    def iniciar(self):
        self.activo = True
        self.hilo = threading.Thread(target=self._hilo_servidor, daemon=True)
        self.hilo.start()

    def detener(self):
        self.activo = False

    def _hilo_servidor(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", self.puerto))
            sock.settimeout(1.0)
        except Exception as e:
            print(f"[ERROR-UDP] Fallo al enlazar puerto {self.puerto}: {e}")
            return

        conteo = 0
        temporizador = time.time()

        while self.activo:
            try:
                paquete, _ = sock.recvfrom(2048)
                if not paquete:
                    continue
                js = json.loads(paquete.decode('utf-8'))
                conteo += 1
                ahora = time.time()
                if ahora - temporizador >= 1.0:
                    hz = conteo / (ahora - temporizador)
                    conteo = 0
                    temporizador = ahora
                else:
                    hz = self.datos.get("tasa_hz", 20.0)

                with self.lock:
                    self.datos = {
                        "v_raw": js.get("v_raw", 0.0),
                        "v_med": js.get("v_med", 0.0),
                        "v_ema": js.get("v_ema", 0.0),
                        "rs": js.get("rs", 7500.0),
                        "r0": js.get("r0", 7500.0),
                        "ratio": js.get("ratio", 1.0),
                        "gas_pct": js.get("gas_pct", 0.0),
                        "calib": js.get("calib", False),
                        "seq": js.get("seq", 0),
                        "tasa_hz": hz,
                        "ultimo_ping": ahora
                    }
            except socket.timeout:
                continue
            except Exception:
                time.sleep(0.1)

        sock.close()


# ======================================================================================
# SECCION 5: CONTROLADOR DE LUZ LED WS2812 (CLIENTE HTTP)
# ======================================================================================
class ControladorLuzLED:
    def __init__(self, light_url):
        self.light_url = light_url
        self.encendida = False
        self.lock = threading.Lock()

    def alternar(self):
        threading.Thread(target=self._enviar_comando, args=("toggle",), daemon=True).start()

    def fijar(self, estado: bool):
        val = "1" if estado else "0"
        threading.Thread(target=self._enviar_comando, args=(val,), daemon=True).start()

    def _enviar_comando(self, estado_param):
        try:
            url = f"{self.light_url}?state={estado_param}"
            req = urllib.request.Request(url, headers={'User-Agent': 'RaspberryPi5-LightControl'})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                with self.lock:
                    self.encendida = data.get("light", self.encendida)
        except Exception:
            pass


# ======================================================================================
# SECCION 6: REGISTRO CONTINUO EN CAJA NEGRA (CSV)
# ======================================================================================
class CajaNegraLogger:
    def __init__(self, ruta_archivo=LOG_FILE_PATH):
        self.ruta = ruta_archivo
        self.activo = False
        self.registros_grabados = 0
        self.hilo = None

    def iniciar(self, gas_rx):
        self.activo = True
        self.hilo = threading.Thread(target=self._hilo_grabador, args=(gas_rx,), daemon=True)
        self.hilo.start()

    def detener(self):
        self.activo = False

    def _hilo_grabador(self, gas_rx):
        existe = os.path.exists(self.ruta)
        with open(self.ruta, mode='a', newline='', encoding='utf-8') as archivo:
            escritor = csv.writer(archivo)
            if not existe:
                escritor.writerow([
                    "Timestamp", "Seq", "V_Raw_V", "V_Med_V", "V_EMA_V",
                    "Rs_Ohm", "R0_Ohm", "Ratio_R0_Rs", "Gas_Pct", "Estado_Minero"
                ])
                archivo.flush()

            while self.activo:
                time.sleep(0.2)
                with gas_rx.lock:
                    d = dict(gas_rx.datos)
                estado, _, _ = evaluar_atmosfera_minera(d["ratio"])
                ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                escritor.writerow([
                    ts, d["seq"], f"{d['v_raw']:.3f}", f"{d['v_med']:.3f}", f"{d['v_ema']:.3f}",
                    f"{d['rs']:.1f}", f"{d['r0']:.1f}", f"{d['ratio']:.3f}", f"{d['gas_pct']:.1f}",
                    estado
                ])
                self.registros_grabados += 1
                if self.registros_grabados % 10 == 0:
                    archivo.flush()


# ======================================================================================
# SECCION 7: PUENTE COMPATIBLE CON ROS 2 HUMBLE
# ======================================================================================
class NodoROS2Puente:
    def __init__(self, light_ctrl=None):
        self.activo = ROS2_AVAILABLE
        self.nodo = None
        self.light_ctrl = light_ctrl
        if self.activo:
            try:
                rclpy.init(args=None)
                self.nodo = Node('nodo_hexapodo_telemetria_v2')
                self.pub_gas_ratio = self.nodo.create_publisher(Float32, '/hexapodo/gas/ratio', 10)
                self.pub_gas_pct = self.nodo.create_publisher(Float32, '/hexapodo/gas/intensidad', 10)
                self.pub_gas_estado = self.nodo.create_publisher(String, '/hexapodo/gas/estado_minero', 10)
                self.pub_cam = self.nodo.create_publisher(CompressedImage, '/hexapodo/camara/comprimida', 10)
                
                # Suscriptor ROS 2 para controlar luz desde otros nodos/Nav2
                if self.light_ctrl is not None:
                    self.nodo.create_subscription(Bool, '/hexapodo/cmd_luz', self._cb_cmd_luz, 10)

                self.hilo_spin = threading.Thread(target=rclpy.spin, args=(self.nodo,), daemon=True)
                self.hilo_spin.start()
            except Exception as e:
                self.activo = False
                print(f"[ROS2] Error al inicializar nodo: {e}")

    def _cb_cmd_luz(self, msg):
        if self.light_ctrl:
            self.light_ctrl.fijar(msg.data)

    def publicar(self, jpeg_bytes, gas_data, estado_minero):
        if not self.activo or not self.nodo:
            return
        try:
            m_ratio = Float32(); m_ratio.data = float(gas_data["ratio"])
            self.pub_gas_ratio.publish(m_ratio)

            m_pct = Float32(); m_pct.data = float(gas_data["gas_pct"])
            self.pub_gas_pct.publish(m_pct)

            m_est = String(); m_est.data = str(estado_minero)
            self.pub_gas_estado.publish(m_est)

            if jpeg_bytes:
                img_msg = CompressedImage()
                img_msg.header.stamp = self.nodo.get_clock().now().to_msg()
                img_msg.format = "jpeg"
                img_msg.data = list(jpeg_bytes)
                self.pub_cam.publish(img_msg)
        except Exception:
            pass


# ======================================================================================
# SECCION 8: PANEL CONSOLA EN TIEMPO REAL (TERMINAL SSH)
# ======================================================================================
def imprimir_panel_terminal(video_rx, gas_rx, light_ctrl, logger, t_inicio, ros2_puente):
    with video_rx.lock:
        v_online = video_rx.conectado
        v_cam_ok = not video_rx.es_standby
        v_fps = video_rx.fps
        v_kb = video_rx.kb_s
        v_total = video_rx.total_cuadros

    with gas_rx.lock:
        g = dict(gas_rx.datos)
        g_online = (time.time() - g["ultimo_ping"]) < 2.0
        g_hz = g["tasa_hz"]
        ratio = g["ratio"]
        gas_pct = g["gas_pct"]

    with light_ctrl.lock:
        luz_on = light_ctrl.encendida

    estado, desc, _ = evaluar_atmosfera_minera(ratio)
    tiempo_mision = int(time.time() - t_inicio)
    minutos = tiempo_mision // 60
    segundos = tiempo_mision % 60

    if os.name == 'nt':
        os.system('cls')
    else:
        print("\033[H\033[J", end="")

    print("=" * 80)
    print("   TESIS MECATRONICA UTEC 2026 - MONITOREO AMBIENTAL EN MINERIA SUBTERRANEA")
    print("   NODO SUPERVISOR CENTRAL RASPBERRY PI 5 V2 (CON CONTROL DE ILUMINACION LED)")
    print("=" * 80)
    print(f" [MISION] Tiempo: {minutos:02d}:{segundos:02d} | Caja Negra: {logger.registros_grabados} registros grabados")
    print(f" [ESTADO ROS 2] : {'ACTIVO (Topicos publicados en Humble)' if ros2_puente.activo else 'MODO AUTONOMO STANDALONE'}")
    print("-" * 80)

    # 1. ESTADO DE VISION UVC
    estado_cam_str = "TRANSMITIENDO STREAM REAL" if (v_online and v_cam_ok) else (
        "STANDBY / CAMARA DESCONECTADA" if v_online else "SIN CONEXION TCP CON ESP32"
    )
    print(f" [CAMARA UVC (TCP:81)]      : {estado_cam_str}")
    print(f"    Rendimiento              : {v_fps:.1f} FPS | Flujo de Red: {v_kb:.1f} KB/s | Cuadros: #{v_total}")
    print("-" * 80)

    # 2. ESTADO DE ILUMINACION LED
    luz_str = "ENCENDIDA (100% Blanco para tunel minero)" if luz_on else "APAGADA (Modo ahorro / sigilo)"
    print(f" [ILUMINACION LED (WS2812)] : {luz_str}")
    print(f"    Control Remoto           : Topico ROS 2 '/hexapodo/cmd_luz' o HTTP '/light'")
    print("-" * 80)

    # 3. ESTADO DE GASES Y SEGURIDAD MINERA
    print(f" [SENSOR GAS (UDP:5005)]     : {'EN LINEA (' + f'{g_hz:.0f}' + ' Hz)' if g_online else 'DESCONECTADO'}")
    print(f"    Voltaje Vout             : {g.get('v_ema', 0.0):.3f} V (Raw: {g.get('v_raw', 0.0):.3f} V)")
    print(f"    Resistencia Rs           : {g.get('rs', 0.0)/1000.0:.2f} kOhm | R0 Base: {g.get('r0', 0.0)/1000.0:.2f} kOhm")
    print(f"    Proporcion R0 / Rs       : {ratio:.3f}x")
    print(f"    Intensidad de Gas        : {gas_pct:.1f} %")
    print("-" * 80)

    # 4. EVALUACION NORMATIVA MINERA D.S. N° 024-2016-EM
    alerta_banner = f"*** [{estado}] *** -> {desc}"
    print(f" [SEGURIDAD MINERA]          : {alerta_banner}")
    print("=" * 80)
    print(" [Atajos SSH]: Presione Ctrl + C para finalizar la mision y guardar el log.")
    sys.stdout.flush()


# ======================================================================================
# SECCION 9: PUNTO DE ENTRADA PRINCIPAL (MAIN)
# ======================================================================================
def main():
    print("[*] Iniciando subsistema de supervision central V2 en Raspberry Pi 5...")

    # Inicializar subsistemas
    video_rx = ReceptorVideoTCP(stream_url=VIDEO_STREAM_URL)
    gas_rx = ReceptorGasesUDP(puerto=GAS_UDP_PORT)
    light_ctrl = ControladorLuzLED(light_url=LIGHT_URL)
    logger = CajaNegraLogger(ruta_archivo=LOG_FILE_PATH)
    ros2_puente = NodoROS2Puente(light_ctrl=light_ctrl)

    terminar_mision = threading.Event()
    def manejador_cierre(sig, frame):
        terminar_mision.set()

    signal.signal(signal.SIGINT, manejador_cierre)
    signal.signal(signal.SIGTERM, manejador_cierre)

    video_rx.iniciar()
    gas_rx.iniciar()
    logger.iniciar(gas_rx)

    t_inicio = time.time()

    try:
        while not terminar_mision.is_set():
            if ros2_puente.activo:
                with video_rx.lock:
                    jpg_data = video_rx.ultimo_jpeg_bytes
                with gas_rx.lock:
                    g_data = dict(gas_rx.datos)
                ratio = g_data.get("ratio", 1.0)
                estado_minero, _, _ = evaluar_atmosfera_minera(ratio)
                ros2_puente.publicar(jpg_data, g_data, estado_minero)

            imprimir_panel_terminal(video_rx, gas_rx, light_ctrl, logger, t_inicio, ros2_puente)
            terminar_mision.wait(timeout=1.0)

    finally:
        print("\n\n[*] Cerrando hilos y guardando registros de mision de forma segura...")
        video_rx.detener()
        gas_rx.detener()
        logger.detener()
        if ros2_puente.activo:
            rclpy.shutdown()
        print(f"[OK] Mision concluida exitosamente. Archivo '{LOG_FILE_PATH}' guardado con {logger.registros_grabados} registros.")


if __name__ == "__main__":
    main()
