#!/usr/bin/env python3
"""
========================================================================================
PROYECTO FINAL DE CARRERA - INGENIERIA MECATRONICA - UTEC 2026
SISTEMA ROBOTICO COOPERATIVO DE INSPECCION EN MINERIA SUBTERRANEA
========================================================================================
Archivo : V1_nodo_raspberry_headless.py
Equipo  : Hexapodo Primario (Raspberry Pi 5 - Ubuntu 22.04 LTS)
Rol     : Receptor y Supervisor Central de Mision en Modo Headless (Sin Monitor)
Entrada : 
  - Stream de Video UVC (TCP HTTP Multipart en Puerto 81)
  - Telemetria de Gas MiCS-5524 (Datagramas UDP a 20 Hz en Puerto 5005)
Salida  :
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
ESP32_HOST          = "192.168.4.1"                   # IP fija del SoftAP en ESP32-S3
VIDEO_STREAM_URL    = f"http://{ESP32_HOST}:81/stream" # Endpoint dedicado MJPEG (TCP)
GAS_UDP_PORT        = 5005                            # Puerto de escucha para el sensor de gas
CALIBRATE_URL       = f"http://{ESP32_HOST}:80/calibrate" # Endpoint HTTP para calibrar R0
LOG_FILE_PATH       = "registro_mision_hexapodo.csv"  # Destino de la caja negra

# Deteccion automatica de soporte ROS 2 Humble (Ubuntu 22.04)
ROS2_AVAILABLE = False
try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import CompressedImage
    from std_msgs.msg import Float32MultiArray, String
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False


# ======================================================================================
# SECCION 2: EVALUACION DE SEGURIDAD ATMOSFERICA (D.S. N° 024-2016-EM)
# ======================================================================================
def evaluar_atmosfera_minera(ratio):
    """
    Evalua la concentracion de gases segun la Ley de Potencias del sensor SnO2 (MiCS-5524)
    y los limites maximos permisibles de la normativa minera peruana D.S. N° 024-2016-EM.
    """
    if ratio < 1.05:
        return "AIRE LIMPIO", "VERDE", "Atmosfera segura - Operacion normal"
    elif ratio < 1.30:
        return "BAJA PRESENCIA", "AMARILLO", "Trazas detectadas - Inspeccion preventiva"
    elif ratio < 1.80:
        return "GAS MODERADO", "NARANJA", "Atencion requerida - Ventilacion auxiliar"
    elif ratio < 3.00:
        return "ALTA TOXICIDAD", "ROJO", "Peligro de asfixia/intoxicacion - Alerta Nivel 1"
    else:
        return "EVACUACION CRITICA", "ROJO_PARPADEO", "PELIGRO LETAL - Repliegue inmediato del robot"


# ======================================================================================
# SECCION 3: RECEPTOR DE VIDEO UVC POR TCP (PUERTO 81) CON TOLERANCIA HOT-PLUG
# ======================================================================================
class ReceptorVideoTCP:
    """
    Hilo consumidor del stream MJPEG HTTP de bajo retardo.
    Maneja conexion en caliente (Hot-Plug): si la camara se desenchufa, recibe el
    cuadro Standby (16x16) sin cerrar el socket ni generar excepciones.
    """
    def __init__(self, stream_url=VIDEO_STREAM_URL):
        self.stream_url = stream_url
        self.running = False
        self.en_linea = False
        self.fps = 0.0
        self.kb_sec = 0.0
        self.total_cuadros = 0
        self.camara_fisica_conectada = False
        self.ultimo_jpeg_bytes = None
        self.ancho = 0
        self.alto = 0
        self.lock = threading.Lock()
        self.hilo = None

    def iniciar(self):
        self.running = True
        self.hilo = threading.Thread(target=self._bucle_recepcion, daemon=True)
        self.hilo.start()

    def detener(self):
        self.running = False

    def _bucle_recepcion(self):
        buffer_datos = bytearray()
        contador_fps = 0
        temporizador_fps = time.time()
        bytes_en_este_segundo = 0

        while self.running:
            try:
                peticion = urllib.request.Request(self.stream_url, headers={'User-Agent': 'RPi5-Headless/1.0'})
                flujo = urllib.request.urlopen(peticion, timeout=4.0)
                self.en_linea = True

                while self.running:
                    fragmento = flujo.read(4096)
                    if not fragmento:
                        break

                    bytes_en_este_segundo += len(fragmento)
                    buffer_datos.extend(fragmento)

                    # Parser robusto basado en encabezado HTTP Content-Length
                    while True:
                        pos_cl = buffer_datos.find(b'Content-Length: ')
                        if pos_cl != -1:
                            pos_fin_hdr = buffer_datos.find(b'\r\n\r\n', pos_cl)
                            if pos_fin_hdr != -1:
                                str_len = buffer_datos[pos_cl + 16 : pos_fin_hdr].decode('ascii', errors='ignore').strip()
                                try:
                                    longitud_jpeg = int(str_len)
                                    inicio_jpeg = pos_fin_hdr + 4
                                    if len(buffer_datos) >= inicio_jpeg + longitud_jpeg:
                                        jpeg_datos = buffer_datos[inicio_jpeg : inicio_jpeg + longitud_jpeg]
                                        buffer_datos = buffer_datos[inicio_jpeg + longitud_jpeg :]

                                        # El cuadro Standby mide 631 bytes (16x16 px). Si es mayor, es video real
                                        es_camara_real = bool(longitud_jpeg > 1000)

                                        with self.lock:
                                            self.ultimo_jpeg_bytes = bytes(jpeg_datos)
                                            self.camara_fisica_conectada = es_camara_real
                                            if es_camara_real:
                                                self.total_cuadros += 1

                                        if es_camara_real:
                                            contador_fps += 1
                                            ahora = time.time()
                                            if ahora - temporizador_fps >= 1.0:
                                                dt = ahora - temporizador_fps
                                                self.fps = contador_fps / dt
                                                self.kb_sec = (bytes_en_este_segundo / 1024.0) / dt
                                                contador_fps = 0
                                                bytes_en_este_segundo = 0
                                                temporizador_fps = ahora
                                        else:
                                            self.fps = 0.0
                                            self.kb_sec = (bytes_en_este_segundo / 1024.0)
                                        continue
                                except ValueError:
                                    buffer_datos = buffer_datos[pos_fin_hdr + 4 :]
                                    continue
                        break

            except Exception:
                self.en_linea = False
                self.camara_fisica_conectada = False
                time.sleep(1.5)


# ======================================================================================
# SECCION 4: RECEPTOR DE TELEMETRIA DE GASES POR UDP (PUERTO 5005)
# ======================================================================================
class ReceptorGasesUDP:
    """
    Hilo receptor de paquetes UDP a 20 Hz enviados desde el ESP32-S3.
    Decodifica el JSON de bajo nivel y actualiza las variables en memoria compartida.
    """
    def __init__(self, puerto=GAS_UDP_PORT):
        self.puerto = puerto
        self.running = False
        self.en_linea = False
        self.datos = {
            "v_raw": 0.5, "v_med": 0.5, "v_ema": 0.5,
            "rs": 7500.0, "r0": 7500.0, "ratio": 1.0, "gas_pct": 0.0
        }
        self.frecuencia_hz = 0.0
        self.total_paquetes = 0
        self.ultima_recepcion = 0.0
        self.lock = threading.Lock()
        self.hilo = None

    def iniciar(self):
        self.running = True
        self.hilo = threading.Thread(target=self._bucle_recepcion, daemon=True)
        self.hilo.start()

    def detener(self):
        self.running = False

    def _bucle_recepcion(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('0.0.0.0', self.puerto))
            sock.settimeout(1.0)
        except Exception as e:
            print(f"[!] Error vinculando socket UDP {self.puerto}: {e}")
            return

        conteo_segundo = 0
        t0 = time.time()

        while self.running:
            try:
                paquete, _ = sock.recvfrom(1024)
                if paquete:
                    payload = json.loads(paquete.decode('utf-8', errors='replace'))
                    ahora = time.time()
                    with self.lock:
                        self.datos = payload
                        self.en_linea = True
                        self.ultima_recepcion = ahora
                        self.total_paquetes += 1
                    conteo_segundo += 1
            except socket.timeout:
                with self.lock:
                    self.en_linea = False
            except Exception:
                pass

            ahora = time.time()
            if ahora - t0 >= 1.0:
                self.frecuencia_hz = conteo_segundo / (ahora - t0)
                conteo_segundo = 0
                t0 = ahora

        sock.close()


# ======================================================================================
# SECCION 5: CAJA NEGRA DE MISION (DATA LOGGER CSV EN DISCO)
# ======================================================================================
class CajaNegraLogger:
    """
    Graba de manera continua los datos sensoriales a 5 Hz en formato CSV.
    Permite respaldar la evidencia fisica para la memoria de tesis y graficas en MATLAB/Python.
    """
    def __init__(self, ruta_archivo=LOG_FILE_PATH):
        self.ruta_archivo = ruta_archivo
        self.running = False
        self.registros_grabados = 0
        self.hilo = None
        self._inicializar_archivo()

    def _inicializar_archivo(self):
        if not os.path.exists(self.ruta_archivo):
            with open(self.ruta_archivo, mode='w', newline='', encoding='utf-8') as f:
                escritor = csv.writer(f)
                escritor.writerow([
                    "timestamp_iso", "unix_time",
                    "voltaje_raw", "voltaje_mediana", "voltaje_ema",
                    "resistencia_rs_ohm", "resistencia_r0_ohm",
                    "ratio_r0_rs", "gas_porcentaje", "estado_seguridad"
                ])

    def iniciar(self, cliente_gas):
        self.cliente_gas = cliente_gas
        self.running = True
        self.hilo = threading.Thread(target=self._bucle_registro, daemon=True)
        self.hilo.start()

    def detener(self):
        self.running = False

    def _bucle_registro(self):
        while self.running:
            time.sleep(0.2) # Muestreo a 5 Hz (cada 200 ms)
            with self.cliente_gas.lock:
                g = dict(self.cliente_gas.datos)
                en_linea = self.cliente_gas.en_linea
                t_ult = self.cliente_gas.ultima_recepcion

            if not en_linea or (time.time() - t_ult > 2.0):
                continue

            ratio = g.get("ratio", 1.0)
            estado, _, _ = evaluar_atmosfera_minera(ratio)
            ahora_iso = datetime.datetime.now().isoformat()
            ahora_unix = f"{time.time():.3f}"

            try:
                with open(self.ruta_archivo, mode='a', newline='', encoding='utf-8') as f:
                    escritor = csv.writer(f)
                    escritor.writerow([
                        ahora_iso, ahora_unix,
                        f"{g.get('v_raw', 0):.3f}",
                        f"{g.get('v_med', 0):.3f}",
                        f"{g.get('v_ema', 0):.3f}",
                        f"{g.get('rs', 0):.1f}",
                        f"{g.get('r0', 0):.1f}",
                        f"{ratio:.3f}",
                        f"{g.get('gas_pct', 0):.1f}",
                        estado
                    ])
                self.registros_grabados += 1
            except Exception:
                pass


# ======================================================================================
# SECCION 6: PUENTE HACIA ROS 2 HUMBLE (OPCIONAL Y AUTOMATICO EN RASPBERRY PI 5)
# ======================================================================================
class NodoROS2Puente:
    """
    Publicador nativo de topicos ROS 2 para integrarse con Nav2 y RTAB-Map SLAM.
    Se activa unicamente si el entorno de Ubuntu 22.04 tiene cargado ROS 2.
    """
    def __init__(self):
        self.activo = False
        if ROS2_AVAILABLE:
            try:
                rclpy.init(args=None)
                self.nodo = Node("puente_esp32_hexapodo")
                self.pub_imagen = self.nodo.create_publisher(CompressedImage, "/secondary_robot/camera/compressed", 10)
                self.pub_gas = self.nodo.create_publisher(Float32MultiArray, "/secondary_robot/gas_telemetry", 10)
                self.pub_alerta = self.nodo.create_publisher(String, "/secondary_robot/safety_alert", 10)
                self.activo = True
            except Exception:
                self.activo = False

    def publicar(self, jpeg_bytes, gas_dict, estado_minero):
        if not self.activo:
            return

        # 1. Publicar imagen comprimida si existe
        if jpeg_bytes is not None and len(jpeg_bytes) > 1000:
            msg_img = CompressedImage()
            msg_img.header.stamp = self.nodo.get_clock().now().to_msg()
            msg_img.header.frame_id = "secondary_camera_optical_frame"
            msg_img.format = "jpeg"
            msg_img.data = list(jpeg_bytes)
            self.pub_imagen.publish(msg_img)

        # 2. Publicar vector de datos de gas: [V_ema, Rs, R0, Ratio, %]
        msg_gas = Float32MultiArray()
        msg_gas.data = [
            float(gas_dict.get("v_ema", 0.0)),
            float(gas_dict.get("rs", 0.0)),
            float(gas_dict.get("r0", 0.0)),
            float(gas_dict.get("ratio", 1.0)),
            float(gas_dict.get("gas_pct", 0.0))
        ]
        self.pub_gas.publish(msg_gas)

        # 3. Publicar alerta de seguridad
        msg_alerta = String()
        msg_alerta.data = estado_minero
        self.pub_alerta.publish(msg_alerta)


# ======================================================================================
# SECCION 7: PANEL DE TELEMETRIA EN TERMINAL SSH (MONITOREO HEADLESS)
# ======================================================================================
def imprimir_panel_terminal(video_rx, gas_rx, logger, t_inicio, ros2_puente):
    """
    Imprime un panel formateado en la consola de Linux / SSH refrescado cada 1 segundo.
    Usa secuencias ANSI para actualizar la pantalla sin parpadeos ni saturacion.
    """
    sys.stdout.write("\033[2J\033[H") # Limpiar pantalla y ubicar cursor en (0,0)

    tiempo_mision = int(time.time() - t_inicio)
    minutos, segundos = divmod(tiempo_mision, 60)

    with video_rx.lock:
        v_online = video_rx.en_linea
        v_cam_ok = video_rx.camara_fisica_conectada
        v_fps = video_rx.fps
        v_kb = video_rx.kb_sec
        v_total = video_rx.total_cuadros

    with gas_rx.lock:
        g_online = gas_rx.en_linea
        g = dict(gas_rx.datos)
        g_hz = gas_rx.frecuencia_hz

    ratio = g.get("ratio", 1.0)
    gas_pct = g.get("gas_pct", 0.0)
    estado, color_tag, desc = evaluar_atmosfera_minera(ratio)

    print("=" * 80)
    print("   SISTEMA DE INSPECCION ROBOTICA COOPERATIVA EN MINERIA SUBTERRANEA")
    print("   NODO SUPERVISOR CENTRAL RASPBERRY PI 5 (UBUNTU 22.04 LTS HEADLESS)")
    print("=" * 80)
    print(f" [MISION] Tiempo: {minutos:02d}:{segundos:02d} | Caja Negra: {logger.registros_grabados} registros grabados")
    print(f" [ESTADO ROS 2] : {'ACTIVO (Topicos publicados en Humble)' if ros2_puente.activo else 'MODO AUTONOMO STANDALONE'}")
    print("-" * 80)

    # 1. ESTADO DE VISION UVC
    estado_cam_str = "TRANSMITIENDO STREAM REAL" if (v_online and v_cam_ok) else (
        "STANDBY / CAMARA DESCONECTADA" if v_online else "SIN CONEXION TCP CON ESP32"
    )
    print(f" [CAMARA UVC (TCP:81)]  : {estado_cam_str}")
    print(f"    Rendimiento          : {v_fps:.1f} FPS | Flujo de Red: {v_kb:.1f} KB/s | Cuadros: #{v_total}")
    print("-" * 80)

    # 2. ESTADO DE GASES Y SEGURIDAD MINERA
    print(f" [SENSOR GAS (UDP:5005)] : {'EN LINEA (' + f'{g_hz:.0f}' + ' Hz)' if g_online else 'DESCONECTADO'}")
    print(f"    Voltaje Vout         : {g.get('v_ema', 0.0):.3f} V (Raw: {g.get('v_raw', 0.0):.3f} V)")
    print(f"    Resistencia Rs       : {g.get('rs', 0.0)/1000.0:.2f} kOhm | R0 Base: {g.get('r0', 0.0)/1000.0:.2f} kOhm")
    print(f"    Proporcion R0 / Rs   : {ratio:.3f}x")
    print(f"    Intensidad de Gas    : {gas_pct:.1f} %")
    print("-" * 80)

    # 3. EVALUACION NORMATIVA MINERA D.S. N° 024-2016-EM
    alerta_banner = f"*** [{estado}] *** -> {desc}"
    print(f" [SEGURIDAD MINERA]      : {alerta_banner}")
    print("=" * 80)
    print(" [Atajos SSH]: Presione Ctrl + C para finalizar la mision y guardar el log.")
    sys.stdout.flush()


# ======================================================================================
# SECCION 8: PUNTO DE ENTRADA PRINCIPAL (MAIN)
# ======================================================================================
def main():
    print("[*] Iniciando subsistema de supervision central en Raspberry Pi 5...")

    # Inicializar receptores
    video_rx = ReceptorVideoTCP(stream_url=VIDEO_STREAM_URL)
    gas_rx = ReceptorGasesUDP(puerto=GAS_UDP_PORT)
    logger = CajaNegraLogger(ruta_archivo=LOG_FILE_PATH)
    ros2_puente = NodoROS2Puente()

    # Manejador de cierre limpio (Ctrl+C o SIGTERM del sistema)
    terminar_mision = threading.Event()
    def manejador_cierre(sig, frame):
        terminar_mision.set()

    signal.signal(signal.SIGINT, manejador_cierre)
    signal.signal(signal.SIGTERM, manejador_cierre)

    # Iniciar hilos en segundo plano
    video_rx.iniciar()
    gas_rx.iniciar()
    logger.iniciar(gas_rx)

    t_inicio = time.time()

    try:
        while not terminar_mision.is_set():
            # 1. Publicar a ROS 2 si esta activo
            if ros2_puente.activo:
                with video_rx.lock:
                    jpg_data = video_rx.ultimo_jpeg_bytes
                with gas_rx.lock:
                    g_data = dict(gas_rx.datos)
                ratio = g_data.get("ratio", 1.0)
                estado_minero, _, _ = evaluar_atmosfera_minera(ratio)
                ros2_puente.publicar(jpg_data, g_data, estado_minero)

            # 2. Refrescar panel en terminal SSH cada 1 segundo
            imprimir_panel_terminal(video_rx, gas_rx, logger, t_inicio, ros2_puente)
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
