"""Nodo receptor del flujo MJPEG y telemetria de gases desde el ESP32-S3.

Convierte el streaming HTTP multipart y las lecturas JSON en topicos estandar de ROS 2.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from std_msgs.msg import Float32, Header
import cv2
import numpy as np


class ReceptorESP32Node(Node):
    def __init__(self):
        super().__init__('receptor_esp32_node')

        self.declare_parameter('esp32_ip', '192.168.4.1')
        self.declare_parameter('frame_rate', 15.0)

        self.esp32_ip = self.get_parameter('esp32_ip').value
        self.stream_url = f"http://{self.esp32_ip}/stream"
        self.data_url = f"http://{self.esp32_ip}/data"

        # Publicadores ROS 2
        self.pub_image = self.create_publisher(Image, '/secundario/camera/image_raw', 10)
        self.pub_info = self.create_publisher(CameraInfo, '/secundario/camera/camera_info', 10)
        self.pub_gas_ratio = self.create_publisher(Float32, '/secundario/gas/r0_rs_ratio', 10)
        self.pub_gas_volt = self.create_publisher(Float32, '/secundario/gas/voltage', 10)

        self.get_logger().info(f"Receptor ESP32 configurado para {self.esp32_ip}")


def main(args=None):
    rclpy.init(args=args)
    node = ReceptorESP32Node()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
