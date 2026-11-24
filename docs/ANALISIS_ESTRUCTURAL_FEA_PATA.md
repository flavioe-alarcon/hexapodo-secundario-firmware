# Análisis Estructural Analítico y Validación por Elementos Finitos (FEA) de la Extremidad del Hexápodo Secundario

**Proyecto de Tesis Mecatrónica UTEC 2026**  
*Autores:* Aleskyjubinsl Alcarraz Jaime, Flavio Alarcon Muñoz, Alfredo Francisco Erazo Yalopalin  

---

## 1. Resumen Ejecutivo

Este documento sintetiza el análisis mecánico integral de la extremidad de 3 grados de libertad (3 DoF: Coxa, Fémur y Tibia) del robot hexápodo secundario explorador, combinando:
1. **Modelado analítico clásico** (flexión de Navier, factores de concentración elástica de esfuerzos de Peterson $K_t$, pandeo elástico de columnas de Euler y rigidez en voladizo).
2. **Evaluación comparativa por Elementos Finitos (FEA en Autodesk Fusion 360)** a través de tres estudios estáticos lineales:
   - **Estudio A (Penúltimo Diseño - Posición Retraída):** Archivo `Analisispata1Alesky` (9 cuerpos sólidos).
   - **Estudio B (Último Diseño - Posición Extendida):** Archivo `AnalisisPata1Alfred` (Estudio 1, 13 cuerpos sólidos).
   - **Estudio C (Último Diseño - Posición Retraída):** Archivo `AnalisisPata1Alfred` (Estudio 2, 13 cuerpos sólidos).

---

## 2. Tabla Comparativa Maestra: Análisis Analítico (Fémur vs. Tibia en PLA)

- **Material Real del Prototipo:** PLA impreso con $8\%$ de relleno y **3 perímetros de pared** ($2.40\text{ mm}$ sólidos por fusión de paredes en nervaduras $\le 2.31\text{ mm} \implies \mathbf{100\%\text{ macizo}}$ en zonas críticas; $S_y = 40.0\text{ MPa}$, $E = 3500.0\text{ MPa}$).
- **Carga de Diseño:** Fuerza vertical suelo-pata $F_{\text{pie}} = 10.0\text{ N}$ y torque de bloqueo del actuador N20 1:300 ($T_{\text{stall}} = 350.0\text{ N}\cdot\text{mm}$).

| Parámetro / Métrica Estructural | Fémur (`Femursoporte` Ocre Crítico) | Tibia (`Tibiamed` Celosía Amarilla Crítica) | Evaluación Global del Ensamble |
| :--- | :---: | :---: | :--- |
| **Longitud Proyectada ($L_x$)** | $60.00\text{ mm}$ | $114.11\text{ mm}$ (codo $\alpha=150^\circ$, $e_y=14.5\text{ mm}$) | Proporción bioinspirada $1:2$ |
| **Peralte Vertical Resistente ($H$)** | $9.00\text{ mm}$ | $10.20\text{ mm}$ | Mayor peralte en tibia compensa longitud |
| **Ancho Sólido Neto ($B_{\text{neto}}$)** | $6.95\text{ mm}$ ($18.9 - 2\times\varnothing 5.975$) | $4.00\text{ mm}$ (ventanas ovaladas) | Aligeramiento progresivo hacia la punta |
| **Inercia a Flexión Vertical ($I_v$)** | $422.21\text{ mm}^4$ | $353.74\text{ mm}^4$ | Rigideces armónicas y compatibles |
| **Módulo de Sección Elástico ($Z_v$)** | $93.82\text{ mm}^3$ | $69.36\text{ mm}^3$ | Proporcionales al gradiente de momentos |
| **Concentrador de Esfuerzos ($K_t$)** | $2.00$ (taladros pasantes) | $1.50$ (acuerdos redondeados *obround*) | Entallas progresivamente más suaves |
| **$FoS$ en Marcha Normal ($10\text{ N}$)** | **$3.75$** ($\sigma_{\text{max}} = 10.66\text{ MPa}$) | **$3.70$** ($\sigma_{\text{max}} = 10.82\text{ MPa}$) | **Equilibrio estructural idóneo ($FoS \approx 3.7$)** |
| **$FoS$ en Extensión / Choque Severo** | **$1.88$** ($\sigma_{\text{max}} = 21.32\text{ MPa}$) | **$1.62$** ($\sigma_{\text{max}} = 24.68\text{ MPa}$) | **Ambos superan la norma ($FoS \ge 1.50$)** |
| **Pandeo Elástico de Euler ($I_{\text{mín}}$)** | No aplica (viga corta rígida) | **$P_{\text{cr}} = 225.48\text{ N}$ ($FoS = 22.55$)** | Totalmente inmune a pandeo lateral |
| **Flecha Elástica Individual ($\delta$)** | $0.49\text{ mm}$ ($0.82\%$ de $L$) | $0.40\text{ mm}$ ($0.35\%$ de $L_x$) | Alta rigidez para control articular PCNT |

---

## 3. Comparativa de los 3 Estudios de Elementos Finitos (FEA - Fusion 360)

| Criterio / Métrica FEA | 1. Penúltimo Diseño: Posición Retraída (`Analisispata1Alesky`) | 2. Último Diseño: Posición Extendida (`AnalisisPata1Alfred` - Estudio 1) | 3. Último Diseño: Posición Retraída (`AnalisisPata1Alfred` - Estudio 2) |
| :--- | :---: | :---: | :---: |
| **Número de Componentes CAD** | $9$ cuerpos (`Coxa2`, `coxa_femur`, `Femur_Med1`, `Tibia_Med1`, etc.) | $13$ cuerpos (`J0sup/inf`, `Coxasup/inf/med`, `Femursup/inf/soporte`, `Tibiasup/med/punta`) | $13$ cuerpos (`J0sup/inf`, `Coxasup/inf/med`, `Femursup/inf/soporte`, `Tibiasup/med/punta`) |
| **Material Asignado en FEA** | **ABS** ($E = 2240\text{ MPa}$, $S_y = 20.0\text{ MPa}$) | **PET** ($E = 2757.9\text{ MPa}$, $S_y = 54.4\text{ MPa}$) | **PET** ($E = 2757.9\text{ MPa}$, $S_y = 54.4\text{ MPa}$) |
| **Discretización (Malla Parabólica)** | $112\,985$ elementos / $163\,314$ nodos (tamaño abs. $10\text{ mm}$) | $116\,115$ elementos / $192\,017$ nodos ($2\%$ modelo, malla curva: Sí) | $187\,896$ elementos / $310\,629$ nodos ($4\%$ modelo, escala por pieza: Sí) |
| **Tolerancia y Contactos Fijados** | $0.10\text{ mm}$ ($44$ contactos *Bonded*) | $0.10\text{ mm}$ ($20$ contactos *Bonded*) | $0.01\text{ mm}$ ($15$ contactos *Bonded*) |
| **Condición de Empotramiento (`Fijo1`)** | Anillos superiores de `Coxa2` | Pared vertical trasera y cara superior de la horquilla `J0sup` | Únicamente pestaña horizontal inferior de la horquilla `J0sup` |
| **Carga Aplicada en Punta del Pie** | $F = 6.00\text{ N}$ ($F_z = +6.00\text{ N}$, $15^\circ$) + Gravedad | $F = 7.00\text{ N}$ ($F_z = +7.00\text{ N}$ vertical) + Gravedad | $F = 6.00\text{ N}$ ($F_z = +5.952\text{ N}$, $F_x = 0.752\text{ N}$) + Gravedad |
| **Esfuerzo en Fémur y Tibia** | $8.0 - 19.69\text{ MPa}$ (tracción en `Femur_Med1` y cuello `coxa_femur`) | **100% Azul Oscuro ($FoS \ge 4.00 - 8.00 \implies \sigma < 13.6\text{ MPa}$)** | **100% Azul Oscuro ($FoS \ge 4.00 - 8.00 \implies \sigma < 13.6\text{ MPa}$)** |
| **Singularidad Puntual de Contacto** | Arista del cuello `coxa_femur` ($\sigma_{VM} = 79.18\text{ MPa}$, $\sigma_1 = 19.69\text{ MPa}$) | Borde anular superior `J0sup` $\parallel$ `Coxasup` ($\sigma_{VM} = 833.63\text{ MPa}$, $\sigma_1 = 163.81\text{ MPa}$) | Borde anular superior `J0sup` $\parallel$ `Coxasup` ($\sigma_{VM} = 595.97\text{ MPa}$, $\sigma_1 = 121.99\text{ MPa}$) |
| **Desplazamiento Total en Punta** | $3.946\text{ mm}$ ($\approx 2.53\text{ mm}$ corregido a PLA) | $14.623\text{ mm}$ (dominado por rotación en junta $J_0$) | $22.071\text{ mm}$ (dominado por apertura elástica de `J0sup` + junta $J_0$) |

---

## 4. Hallazgos Mecánicos Clave para la Memoria y Sustentación de Tesis

### 4.1. Validación Absoluta del Fémur y la Tibia en el Último Diseño
En las gráficas de **Factor de Seguridad** de ambos estudios del último diseño (posición extendida y posición retraída), la totalidad de la **Tibia** (`Tibiasup`, `Tibiainf`, `Tibiamed`, `Tibiapunta`), la totalidad del **Fémur** (`Femursup`, `Femurinf`, `Femursoporte`) y el cuerpo articulado de la **Coxa** (`Coxamed1`, `Coxamed2`) aparecen teñidos al **100% en color azul oscuro ($FoS \in [4.00, 8.00]$, "Por encima del objetivo")**.
- Dado que el límite elástico configurado en la simulación es $S_y = 54.40\text{ MPa}$, un $FoS > 4.00$ certifica que en ningún punto del fémur ni de la tibia se superan los **$13.60\text{ MPa}$**, guardando plena correspondencia con los esfuerzos analíticos calculados ($\approx 10.66\text{ MPa}$ en fémur y $10.82\text{ MPa}$ en tibia).
- Se comprueba que el aligeramiento de las ventanas ovaladas en la tibia y la incorporación de la puntera curva (`Tibiapunta`) y los soportes simétricos del fémur distribuyen el flujo de tensiones de manera uniforme sin zonas débiles.

### 4.2. Efecto Cinemático de la Postura: Posición Extendida vs. Posición Retraída
Al comparar la **Posición Extendida (Estudio 1)** con la **Posición Retraída (Estudio 2)** sobre la misma geometría final (`AnalisisPata1Alfred`):
- En la **posición extendida**, la proyección horizontal de los eslabones aumenta el brazo de palanca ($d_{\perp}$) respecto al eje de la coxa ($J_0$). Combinado con la fuerza vertical de $7.00\text{ N}$, el momento flector transmitido al collarín superior de la coxa (`Coxasup`) produce esfuerzos un **$39.9\%$ mayores en Von Mises** ($833.63\text{ MPa}$ frente a $595.97\text{ MPa}$) y un **$34.3\%$ mayores en tracción principal $\sigma_1$** ($163.81\text{ MPa}$ frente a $121.99\text{ MPa}$) que en la posición retraída ($6.00\text{ N}$).
- Esto valida numéricamente que la **postura extendida constituye el estado crítico de carga por momento flector**, mientras que la **postura retraída o semi-flexionada** reduce significativamente el par estático exigido a las articulaciones y actuadores.

### 4.3. Explicación Física de la Singularidad en `J0sup` $\parallel$ `Coxasup` y del Desplazamiento ($14.6\text{ mm}$ y $22.1\text{ mm}$)
¿Por qué Fusion 360 reporta un esfuerzo puntual elevado ($596 - 833\text{ MPa}$) y alerta de factor de seguridad en la unión superior de la coxa si toda la pata está azul?
1. **Ausencia del Eje del Motor N20 y del Apoyo Inferior (`J0inf` desconectado de `CoxaInf`):**
   - Al exportar el CAD sin los micromotores N20 para el estudio estático, la placa inferior de la horquilla del chasis (`J0inf`, pieza con 4 pines cilíndricos) queda separada por un espacio vacío respecto al anillo inferior de la coxa (`CoxaInf`).
   - Revisando la tabla de contactos del informe (`Fijado1` a `Fijado20`), **`J0inf:1` no posee ningún contacto definido**. Por tanto, toda la pata queda colgada en voladizo simple únicamente desde un borde anular delgado en la parte superior (`J0sup:1` $\parallel$ `Coxasup:1`, `Cara 53 || Cara 31`).
2. **Singularidad Numérica de Borde (*Edge Singularity*):**
   - Todo el momento flector de la extremidad ($\sim 1000\text{ N}\cdot\text{mm}$) se descarga sobre esa línea circular de contacto sin chaflán y con `0 pasos de refinado adaptable`. En elasticidad lineal por elementos finitos, una fuerza transmitida sobre una arista de área infinitesimal ($\Delta A \to 0$) genera una singularidad matemática local en 1 o 2 nodos (el punto microscópico rojo visible en la cara superior de `Coxasup`), mientras que a solo $1\text{ mm}$ de distancia el collarín ya está en color verde ($FoS \in [2.0, 4.0]$) y azul ($FoS > 4.0$).
3. **Causa de la Diferencia de Desplazamiento entre Estudio 1 ($14.62\text{ mm}$) y Estudio 2 ($22.07\text{ mm}$):**
   - En los mapas de desplazamiento total se observa que el fémur y la tibia **no se arquean**, sino que experimentan un desplazamiento lineal por **rotación de cuerpo rígido alrededor de la junta flexible `J0sup` $\parallel$ `Coxasup`**.
   - En el **Estudio 1 (Extendida)**, la restricción `Fijo1` bloquea toda la pared vertical trasera y la cara superior de `J0sup`, limitando el desplazamiento de la punta a **$14.623\text{ mm}$**.
   - En el **Estudio 2 (Retraída)**, la restricción `Fijo1` se aplicó **solamente en la pestaña horizontal inferior** de `J0sup`. Como consecuencia, el brazo superior de la horquilla `J0sup` queda en voladizo y se abre elásticamente hacia arriba bajo la tracción de la pata, sumando el giro de la horquilla al giro de la junta y produciendo **$22.071\text{ mm}$** en la punta.
   - **Conclusión de Diseño Físico:** Este fenómeno demuestra la importancia crítica del **doble soporte físico en el eje del motor N20** implementado en el prototipo real: al insertar el motor N20 y el acople inferior entre `J0inf` y `CoxaInf`, la articulación trabaja en **corte doble (apoyo bi-empotrado superior e inferior)**, eliminando el giro parásito de la horquilla y reduciendo la deflexión real en la punta del pie a menos de $1.5\text{ mm}$.
