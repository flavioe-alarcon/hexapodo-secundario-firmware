"""Launch para iniciar el sistema de relocalizacion cooperativa y visualizacion."""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('hexapod_cooperative')
    default_rviz = os.path.join(pkg_share, 'config', 'cooperativo.rviz')
    default_camera_info = os.path.join(pkg_share, 'config', 'camara_secundaria.yaml')

    return LaunchDescription([
        DeclareLaunchArgument(
            'esp32_ip',
            default_value='192.168.4.1',
            description='Direccion IP del ESP32-S3 del Hexapodo Secundario'
        ),
        DeclareLaunchArgument(
            'database_path',
            default_value=os.path.expanduser('~/.ros/hexapod_mapa.db'),
            description='Ruta a la base de datos 3D generada por hexapod_mapping'
        ),
        DeclareLaunchArgument(
            'rviz',
            default_value='true',
            description='Abrir RViz con la configuracion cooperativa'
        ),

        # Nodo receptor ESP32
        Node(
            package='hexapod_cooperative',
            executable='receptor_esp32_node',
            name='receptor_esp32',
            output='screen',
            parameters=[{'esp32_ip': LaunchConfiguration('esp32_ip')}]
        ),

        # Nodo relocalizador PnP
        Node(
            package='hexapod_cooperative',
            executable='relocalizador_pnp_node',
            name='relocalizador_pnp',
            output='screen',
            parameters=[{'database_path': LaunchConfiguration('database_path')}]
        ),
    ])
