# Workspace de Localización Cooperativa (`coop_ws`)

Este espacio de trabajo es un **ROS 2 Workspace Overlay** diseñado para desacoplar el desarrollo de la relocalización visual y monitoreo ambiental del **Hexápodo Secundario** sin modificar ninguna línea del workspace principal (`ros2_ws`).

---

## 📌 Principio de Funcionamiento: ROS 2 Overlay

Un *overlay workspace* se monta encima de otro (*underlay*). Permite consumir los tipos de mensajes, mapas y tópicos del robot primario sin alterar su repositorio Git ni sus dependencias.

```text
[ Underlay: ros2_ws (Alesky) ]  ──►  Provee /map, /rtabmap/mapData y hexapod_mapa.db
              ▲
              │ (Hereda interfaces y TF)
[ Overlay: coop_ws (Flavio)  ]  ──►  Publica /secundario/... y la TF (map -> secundario_base_link)
```

---

## 🚀 Compilación y Ejecución

### 1. Compilar el paquete
Desde la terminal en Linux/WSL (ROS 2 Jazzy o Humble):
```bash
# 1. Cargar el workspace del robot grande (Underlay)
source ~/ros2_ws/install/setup.bash

# 2. Entrar y compilar el workspace cooperativo (Overlay)
cd pruebas/coop_ws
colcon build --packages-select hexapod_cooperative
source install/setup.bash
```

### 2. Ejecutar la relocalización
```bash
# Lanzar el puente de streaming y el estimador de pose PnP-RANSAC
ros2 launch hexapod_cooperative relocalizacion_cooperativa.launch.py esp32_ip:=192.168.4.1
```
