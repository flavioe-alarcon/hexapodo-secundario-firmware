#!/bin/bash
# ==============================================================================
# Lanzador para Raspberry Pi 5 (Ubuntu 24.04 / 22.04 LTS con ROS 2 Jazzy/Humble)
# PRUEBA VALIDADA Y EXITOSA: Receptor de Cámara UVC Dedicado y Publicador ROS 2
# ==============================================================================
cd "$(dirname "$0")"
echo "Iniciando nodo validado de camara UVC en Raspberry Pi 5..."
python3 VALIDADO_EXITOSO_nodo_camara_solo_raspberry.py
