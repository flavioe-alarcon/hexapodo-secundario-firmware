#!/usr/bin/env python3
"""
========================================================================================
PROYECTO FINAL DE CARRERA - INGENIERIA MECATRONICA - UTEC 2026
SISTEMA ROBOTICO COOPERATIVO DE INSPECCION EN MINERIA SUBTERRANEA
========================================================================================
Archivo : nodo_camara_solo_raspberry.py
Equipo  : Hexapodo Primario (Raspberry Pi 5 - Ubuntu 24.04 / 22.04 LTS con ROS 2 Jazzy)
Rol     : Receptor de Video UVC Dedicado y Publicador de ROS 2 (Prueba Aislada de Camara)
Entrada : 
  - Stream MJPEG TCP en Puerto 81 (http://192.168.4.1:81/stream)
  - Telemetria de Estado en Puerto 80 (http://192.168.4.1:80/status)
Salida  :
  - Topico ROS 2: /secondary_robot/camera/compressed (sensor_msgs/msg/CompressedImage)
  - Topico ROS 2: /secondary_robot/camera/status (std_msgs/msg/String)
  - Monitor en terminal SSH con metricas en vivo y deteccion de Standby / Camara Real
========================================================================================
"""

import sys
import os
import time
import json
import socket
import signal
import threading
import urllib.request
import urllib.error

# Soporte UTF-8 en consola
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# --------------------------------------------------------------------------------------
# Configuracion de Red del ESP32-S3
# --------------------------------------------------------------------------------------
ESP32_HOST          = "192.168.4.1"
VIDEO_STREAM_URL    = f"http://{ESP32_HOST}:81/stream"
STATUS_URL          = f"http://{ESP32_HOST}:80/status"

# Deteccion automatica de soporte ROS 2 (Jazzy / Humble)
ROS2_AVAILABLE = False
try:
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    from sensor_msgs.msg import CompressedImage
    ROS2_AVAILABLE = True
except ImportError:
    ROS2_AVAILABLE = False


class NodoCamaraROS2:
    """Gestiona los publicadores de ROS 2 si rclpy esta disponible."""
    def __init__(self):
        self.node = None
        self.pub_image = None
        self.pub_status = None
        if ROS2_AVAILABLE:
            try:
                rclpy.init(args=None)
                self.node = Node("nodo_camara_secundario")
                self.pub_image = self.node.create_publisher(
                    CompressedImage, "/secondary_robot/camera/compressed", 10
                )
                self.pub_status = self.node.create_publisher(
                    String, "/secondary_robot/camera/status", 10
                )
            except Exception as e:
                print(f"[ROS 2] Error al inicializar nodo: {e}")
                self.node = None

    def publicar_frame(self, jpeg_bytes, es_standby):
        if not self.node or not self.pub_image:
            return
        try:
            msg = CompressedImage()
            msg.header.stamp = self.node.get_clock().now().to_msg()
            msg.header.frame_id = "camera_link_secondary"
            msg.format = "jpeg"
            msg.data = list(jpeg_bytes)
            self.pub_image.publish(msg)

            # Publicar estado
            status_msg = String()
            status_msg.data = "STANDBY" if es_standby else "EN_VIVO"
            self.pub_status.publish(status_msg)
        except Exception:
            pass

    def spin_once(self):
        if self.node:
            rclpy.spin_once(self.node, timeout_sec=0.001)

    def destruir(self):
        if self.node:
            try:
                self.node.destroy_node()
                rclpy.shutdown()
            except Exception:
                pass


class ReceptorCamaraTCP:
    """Cliente TCP HTTP que procesa el stream multipart MJPEG de forma resiliente."""
    def __init__(self, ros_handler):
        self.ros_handler = ros_handler
        self.activo = True
        self.conectado = False
        self.es_standby = True
        self.fps = 0.0
        self.kb_s = 0.0
        self.total_cuadros = 0
        self.bytes_ultimo_frame = 0
        self.ultimo_tiempo_frame = 0

    def iniciar(self):
        print("\n" + "=" * 70)
        print("  ROBOT HEXAPODO · RECEPTOR DE CAMARA UVC (TEST RASPBERRY PI 5)")
        print("=" * 70)
        print(f"[*] Destino ESP32-S3    : {VIDEO_STREAM_URL}")
        print(f"[*] Soporte ROS 2 Jazzy : {'HABILITADO' if ROS2_AVAILABLE else 'NO DISPONIBLE (Modo consola)'}")
        print("[*] Iniciando lazo de recepcion TCP...\n")

        # Iniciar hilo de refresco de consola
        hilo_consola = threading.Thread(target=self._hilo_monitor_consola, daemon=True)
        hilo_consola.start()

        while self.activo:
            try:
                req = urllib.request.Request(VIDEO_STREAM_URL, headers={"User-Agent": "RaspberryPi-UVC-Client/2.0"})
                with urllib.request.urlopen(req, timeout=4.0) as stream:
                    self.conectado = True
                    bufer = bytearray()
                    conteo_frames = 0
                    conteo_bytes = 0
                    t_inicio_seg = time.time()

                    while self.activo:
                        chunk = stream.read(4096)
                        if not chunk:
                            break
                        bufer.extend(chunk)
                        conteo_bytes += len(chunk)

                        # Buscar delimitadores JPEG: SOI (0xFF, 0xD8) y EOI (0xFF, 0xD9)
                        while True:
                            idx_inicio = bufer.find(b'\xff\xd8')
                            if idx_inicio == -1:
                                if len(bufer) > 8192:
                                    bufer = bufer[-4096:]
                                break

                            idx_fin = bufer.find(b'\xff\xd9', idx_inicio + 2)
                            if idx_fin == -1:
                                if idx_inicio > 0:
                                    del bufer[:idx_inicio]
                                break

                            # Extraer JPEG valido
                            jpeg_bytes = bytes(bufer[idx_inicio:idx_fin + 2])
                            del bufer[:idx_fin + 2]

                            tam_frame = len(jpeg_bytes)
                            self.bytes_ultimo_frame = tam_frame
                            self.total_cuadros += 1
                            conteo_frames += 1

                            # Clasificar si es Standby (631 bytes) o frame real de la camara
                            self.es_standby = (tam_frame <= 700)

                            # Publicar en ROS 2 si esta activo
                            self.ros_handler.publicar_frame(jpeg_bytes, self.es_standby)
                            self.ros_handler.spin_once()

                        # Calcular FPS y KB/s cada 1 segundo
                        ahora = time.time()
                        delta_t = ahora - t_inicio_seg
                        if delta_t >= 1.0:
                            self.fps = conteo_frames / delta_t
                            self.kb_s = (conteo_bytes / 1024.0) / delta_t
                            conteo_frames = 0
                            conteo_bytes = 0
                            t_inicio_seg = ahora

            except Exception as e:
                self.conectado = False
                self.fps = 0.0
                self.kb_s = 0.0
                time.sleep(1.0)

    def _hilo_monitor_consola(self):
        while self.activo:
            time.sleep(1.0)
            if not self.conectado:
                print(f"[{time.strftime('%H:%M:%S')}] \033[93m[CONECTANDO]\033[0m Esperando conexion Wi-Fi con ESP32-S3 (192.168.4.1)...", end='\r')
            else:
                if self.es_standby:
                    estado_str = "\033[93m[STANDBY - CAMARA APAGADA/DESCONECTADA]\033[0m"
                    tipo_frame = "Frame espera (16x16 px)"
                else:
                    estado_str = "\033[92m[EN VIVO - UVC ACTIVA]\033[0m"
                    tipo_frame = f"JPEG real ({self.bytes_ultimo_frame/1024.0:.1f} KB)"

                ros_str = "\033[92m/secondary_robot/camera/compressed\033[0m" if ROS2_AVAILABLE else "Inactivo"

                sys.stdout.write(
                    f"\r[{time.strftime('%H:%M:%S')}] {estado_str} | "
                    f"FPS: \033[96m{self.fps:4.1f}\033[0m | "
                    f"Flujo: \033[96m{self.kb_s:5.1f} KB/s\033[0m | "
                    f"{tipo_frame} | Total: {self.total_cuadros} | ROS 2: {ros_str}    "
                )
                sys.stdout.flush()

    def detener(self):
        self.activo = False


def main():
    ros_handler = NodoCamaraROS2()
    receptor = ReceptorCamaraTCP(ros_handler)

    def handle_sigint(sig, frame):
        print("\n\n[*] Deteniendo nodo de camara...")
        receptor.detener()
        ros_handler.destruir()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)
    receptor.iniciar()


if __name__ == "__main__":
    main()
