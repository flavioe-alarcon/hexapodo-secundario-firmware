#!/bin/bash
# ==============================================================================
# Lanzador para Raspberry Pi 5 (Ubuntu 22.04 LTS) - Modo Headless
# ==============================================================================
cd "$(dirname "$0")"
echo "Iniciando nodo de mision en Raspberry Pi 5..."
python3 V1_nodo_raspberry_headless.py
