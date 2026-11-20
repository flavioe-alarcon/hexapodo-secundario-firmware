import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'hexapod_cooperative'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'README.md']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='flavio',
    maintainer_email='flavio@todo.todo',
    description='Relocalizacion visual monocular y telemetria ambiental para el Hexapodo Secundario.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'receptor_esp32_node = hexapod_cooperative.receptor_esp32_node:main',
            'relocalizador_pnp_node = hexapod_cooperative.relocalizador_pnp_node:main',
        ],
    },
)
