import streamlit as st
from pymongo import MongoClient
from PIL import Image
import pytz
from datetime import datetime
import time
import base64
import openai
import io

# === CONFIGURACIÓN ===
st.set_page_config(page_title="👁️ Proyecto 10K", layout="wide")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === CREDENCIALES ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]
openai.api_key = st.secrets["openai_api_key"]
tz = pytz.timezone("America/Bogota")

# === ESTADOS DE SESIÓN ===
if "objetos_detectados" not in st.session_state:
    st.session_state.objetos_detectados = []
if "objetos_seleccionados" not in st.session_state:
    st.session_state.objetos_seleccionados = []
if "orden_asignado" not in st.session_state:
    st.session_state.orden_asignado = {}
if "iniciado" not in st.session_state:
    st.session_state.iniciado = False
if "tiempos_objetos" not in st.session_state:
    st.session_state.tiempos_objetos = {}
if "inicio_global" not in st.session_state:
    st.session_state.inicio_global = None

# === FUNCIONES ===
def detectar_objetos(imagen: Image.Image):
    try:
        buffer = io.BytesIO()
        imagen.save(buffer, format="JPEG")
        b64_img = base64.b64encode(buffer.getvalue()).decode()

        prompt = f"""
Lista solo los objetos visibles y comunes en la siguiente imagen (sin explicaciones):
{b64_img}
"""
        respuesta = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un experto en visión artificial."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        texto = respuesta.choices[0].message.content
        objetos = [line.split(". ", 1)[-1] for line in texto.strip().splitlines() if ". " in line]
        return objetos
    except Exception as e:
        st.error(f"Error en la detección: {e}")
        return []

def guardar_sesion():
    tiempo_total = int(time.time() - st.session_state.inicio_global)
    ahora = datetime.now(tz)
    doc = {
        "timestamp": ahora,
        "objetos": st.session_state.objetos_seleccionados,
        "orden": st.session_state.orden_asignado,
        "tiempos": st.session_state.tiempos_objetos,
        "tiempo_total": tiempo_total
    }
    col.insert_one(doc)

# === INTERFAZ ===
img_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if img_file:
    imagen = Image.open(img_file)
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    if st.button("🔍 Detectar objetos"):
        st.session_state.objetos_detectados = detectar_objetos(imagen)
        st.session_state.objetos_seleccionados = []
        st.session_state.orden_asignado = {}
        st.session_state.tiempos_objetos = {}
        st.session_state.iniciado = False
        st.session_state.inicio_global = None

# === SELECCIÓN DE OBJETOS ===
if st.session_state.objetos_detectados:
    st.markdown("📦 **Objetos detectados:**")
    for i, obj in enumerate(st.session_state.objetos_detectados, 1):
        col1, col2 = st.columns([0.1, 0.9])
        with col1:
            sel = st.checkbox("", key=f"sel_{i}")
        with col2:
            st.markdown(f"**{obj}**")
        if sel and obj not in st.session_state.objetos_seleccionados:
            st.session_state.objetos_seleccionados.append(obj)
        elif not sel and obj in st.session_state.objetos_seleccionados:
            st.session_state.objetos_seleccionados.remove(obj)

# === ASIGNAR ORDEN ===
if st.session_state.objetos_seleccionados:
    st.markdown("📌 **Asigna el orden de intervención:**")
    for obj in st.session_state.objetos_seleccionados:
        orden = st.number_input(f"{obj}", min_value=1, max_value=10, step=1, key=f"orden_{obj}")
        st.session_state.orden_asignado[obj] = orden

# === INICIO DE SESIÓN ===
if st.session_state.objetos_seleccionados and st.button("▶️ Iniciar sesión"):
    st.session_state.iniciado = True
    st.session_state.inicio_global = time.time()
    for obj in st.session_state.objetos_seleccionados:
        st.session_state.tiempos_objetos[obj] = {"inicio": time.time(), "duracion": 0}

# === CRONÓMETRO ===
if st.session_state.iniciado:
    st.markdown("⏱️ **Cronómetro en curso:**")
    elapsed = int(time.time() - st.session_state.inicio_global)
    st.markdown(f"🧭 Tiempo total: **{elapsed} segundos**")

    for obj in sorted(st.session_state.orden_asignado.items(), key=lambda x: x[1]):
        nombre = obj[0]
        inicio = st.session_state.tiempos_objetos[nombre]["inicio"]
        duracion = int(time.time() - inicio)
        st.session_state.tiempos_objetos[nombre]["duracion"] = duracion
        st.markdown(f"🔸 **{nombre}** – {duracion} segundos")

    if st.button("⏹ Finalizar sesión"):
        guardar_sesion()
        st.success("✅ Sesión guardada exitosamente")
        st.rerun()

# === HISTORIAL ===
st.divider()
st.subheader("📚 Historial de sesiones")
registros = list(col.find().sort("timestamp", -1))

if registros:
    for reg in registros:
        fecha = reg["timestamp"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(f"🕓 **{fecha}**")
        st.markdown(f"📦 Objetos: {', '.join(reg['objetos'])}")
        st.markdown(f"🧭 Tiempo total: {reg['tiempo_total']} segundos")
        st.markdown("---")
else:
    st.info("No hay sesiones completas registradas aún.")