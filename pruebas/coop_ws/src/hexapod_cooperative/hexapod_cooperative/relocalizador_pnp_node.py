"""Nodo principal de relocalizacion visual monocular 2D-to-3D (PnP-RANSAC).

Estima la pose 6-DoF del Hexapodo Secundario en el sistema de coordenadas 'map'
y publica la transformacion TF correspondiente sin modificar el arbol TF del primario.
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import PoseStamped, TransformStamped
from visualization_msgs.msg import Marker
import tf2_ros
from .mapa_db_reader import MapaDBReader


class RelocalizadorPnPNode(Node):
    def __init__(self):
        super().__init__('relocalizador_pnp_node')

        self.declare_parameter('database_path', '~/.ros/hexapod_mapa.db')
        self.declare_parameter('frame_id_map', 'map')
        self.declare_parameter('child_frame_id', 'secundario_base_link')

        db_path = self.get_parameter('database_path').value
        self.map_frame = self.get_parameter('frame_id_map').value
        self.child_frame = self.get_parameter('child_frame_id').value

        self.db_reader = MapaDBReader(db_path)
        self.tf_broadcaster = tf2_ros.TransformBroadcaster(self)

        # Publicadores de pose y marcador para RViz
        self.pub_pose = self.create_publisher(PoseStamped, '/secundario/pose', 10)
        self.pub_marker = self.create_publisher(Marker, '/secundario/marker', 10)

        # Suscriptor al video del secundario
        self.sub_image = self.create_subscription(
            Image,
            '/secundario/camera/image_raw',
            self.image_callback,
            10
        )

        self.get_logger().info("Nodo Relocalizador PnP-RANSAC inicializado.")

    def image_callback(self, msg):
        # Aqui se realiza el emparejamiento 2D con los landmarks 3D y cv2.solvePnPRansac
        pass


def main(args=None):
    rclpy.init(args=args)
    node = RelocalizadorPnPNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
