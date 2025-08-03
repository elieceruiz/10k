import streamlit as st
import openai
from pymongo import MongoClient
import base64
from PIL import Image
from datetime import datetime
import pytz
import time

# === CONFIGURACIÓN ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")
tz = pytz.timezone("America/Bogota")

# === CLAVES Y DB ===
openai.api_key = st.secrets["openai_api_key"]
client = MongoClient(st.secrets["mongo_uri"])
db = client["proyecto_10k"]
col = db["registro_sesiones"]

# === ESTADO ===
if "img_bytes" not in st.session_state: st.session_state.img_bytes = None
if "objetos_detectados" not in st.session_state: st.session_state.objetos_detectados = []
if "seleccionados" not in st.session_state: st.session_state.seleccionados = []
if "orden" not in st.session_state: st.session_state.orden = {}
if "tiempo_inicio" not in st.session_state: st.session_state.tiempo_inicio = None
if "registro_tiempos" not in st.session_state: st.session_state.registro_tiempos = {}

# === SUBIDA DE IMAGEN ===
img_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if img_file:
    st.image(img_file, caption="Imagen cargada", use_container_width=True)
    st.session_state.img_bytes = img_file.read()
    base64_img = base64.b64encode(st.session_state.img_bytes).decode("utf-8")

    if st.button("🔍 Detectar objetos con GPT-4o"):
        with st.spinner("Analizando..."):
            try:
                respuesta = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Eres un asistente que detecta objetos en imágenes."},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Lista los objetos visibles en viñetas. Solo nombres, no descripciones."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
                            ]
                        }
                    ],
                    max_tokens=200
                )
                texto = respuesta.choices[0].message.content.strip()
                items = [i.strip("• ").strip() for i in texto.split("\n") if i.strip()]
                st.session_state.objetos_detectados = items
                st.session_state.seleccionados = []
                st.session_state.orden = {}
                st.session_state.registro_tiempos = {}
                st.success("✅ Objetos detectados correctamente.")
            except Exception as e:
                st.error(f"Error en la detección: {e}")

# === MOSTRAR OBJETOS Y SELECCIÓN ===
if st.session_state.objetos_detectados:
    st.markdown("### 📦 Objetos detectados:")
    for i, obj in enumerate(st.session_state.objetos_detectados, 1):
        col1, col2 = st.columns([0.1, 0.9])
        with col1:
            check = st.checkbox(f"{i}", key=f"obj_{i}")
        with col2:
            st.markdown(obj)

        if check and obj not in st.session_state.seleccionados:
            st.session_state.seleccionados.append(obj)
        elif not check and obj in st.session_state.seleccionados:
            st.session_state.seleccionados.remove(obj)

# === CRONÓMETRO Y ORDEN ===
if st.session_state.seleccionados:
    st.markdown("### 🧭 Orden y Cronómetro")
    for idx, obj in enumerate(st.session_state.seleccionados, 1):
        st.markdown(f"**{idx}. {obj}**")

    if st.button("▶️ Iniciar Cronómetro"):
        st.session_state.tiempo_inicio = time.time()

# === MOSTRAR TIEMPO ACTUAL ===
if st.session_state.tiempo_inicio:
    elapsed = int(time.time() - st.session_state.tiempo_inicio)
    minutos = elapsed // 60
    segundos = elapsed % 60
    st.markdown(f"⏱ Tiempo transcurrido: `{minutos:02}:{segundos:02}`")
    st.experimental_rerun()

# === GUARDAR SESIÓN ===
if st.session_state.tiempo_inicio and st.button("💾 Finalizar y Guardar"):
    now = datetime.now(tz)
    doc = {
        "fecha": now.strftime("%Y-%m-%d"),
        "hora": now.strftime("%H:%M:%S"),
        "objetos_ordenados": st.session_state.seleccionados,
        "duracion_segundos": int(time.time() - st.session_state.tiempo_inicio)
    }
    col.insert_one(doc)
    st.success("✅ Registro guardado exitosamente.")
    st.session_state.objetos_detectados = []
    st.session_state.seleccionados = []
    st.session_state.tiempo_inicio = None
    st.session_state.img_bytes = None
    st.rerun()