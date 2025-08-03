import streamlit as st
from pymongo import MongoClient
from datetime import datetime
from PIL import Image
import pytz
import io
import openai
import time

# --- CONFIG STREAMLIT ---
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# --- CLAVES SEGURAS ---
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

openai.api_key = st.secrets["openai_api_key"]
tz = pytz.timezone("America/Bogota")

# --- FUNCIONES AUXILIARES ---
def analizar_imagen(imagen):
    try:
        buffer = io.BytesIO()
        imagen.save(buffer, format="JPEG")
        img_bytes = buffer.getvalue()

        base64_img = f"data:image/jpeg;base64,{img_bytes.hex()}"

        prompt = (
            "Mira esta imagen. Lista solo los nombres de los objetos visibles. "
            "No des descripciones ni uses viñetas ni numeración. Un nombre por línea."
        )

        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Eres un asistente que analiza imágenes y enumera objetos visibles."},
                {"role": "user", "content": prompt},
                {"role": "user", "content": base64_img}
            ],
            max_tokens=150
        )

        resultado = response.choices[0].message.content.strip()
        objetos = [obj.strip() for obj in resultado.split('\n') if obj.strip()]
        return objetos

    except Exception as e:
        st.error(f"Error en la detección: {e}")
        return []

# --- VARIABLES DE SESIÓN ---
if "objetos_detectados" not in st.session_state:
    st.session_state.objetos_detectados = []

if "seleccionados" not in st.session_state:
    st.session_state.seleccionados = []

if "cronometro_activo" not in st.session_state:
    st.session_state.cronometro_activo = False

if "inicio_cronometro" not in st.session_state:
    st.session_state.inicio_cronometro = None

# --- SUBIDA DE IMAGEN ---
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if uploaded_file:
    imagen = Image.open(uploaded_file)
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    if st.button("🔍 Detectar objetos con IA"):
        objetos = analizar_imagen(imagen)
        st.session_state.objetos_detectados = objetos
        st.session_state.seleccionados = []

# --- LISTA CON CHECKBOXES ---
if st.session_state.objetos_detectados:
    st.markdown("### 📦 Objetos detectados:")
    nuevos_seleccionados = []

    for i, obj in enumerate(st.session_state.objetos_detectados):
        if st.checkbox(f"{obj}", key=f"check_{i}"):
            nuevos_seleccionados.append(obj)

    st.session_state.seleccionados = nuevos_seleccionados

# --- BOTÓN PARA INICIAR SESIÓN ---
if st.session_state.seleccionados:
    if not st.session_state.cronometro_activo:
        if st.button("▶️ Iniciar sesión de organización"):
            st.session_state.inicio_cronometro = time.time()
            st.session_state.cronometro_activo = True
            st.rerun()

# --- CRONÓMETRO ---
if st.session_state.cronometro_activo:
    tiempo_transcurrido = int(time.time() - st.session_state.inicio_cronometro)
    minutos, segundos = divmod(tiempo_transcurrido, 60)
    st.markdown(f"🧭 Tiempo transcurrido: {minutos:02d}:{segundos:02d}")

    if tiempo_transcurrido >= 120:
        st.success("✅ 2 minutos alcanzados. Sesión registrada.")

        # Guardar sesión en Mongo
        ahora = datetime.now(tz)
        doc = {
            "fecha": ahora.strftime("%Y-%m-%d"),
            "hora": ahora.strftime("%H:%M:%S"),
            "objetos": st.session_state.seleccionados,
            "duracion_segundos": tiempo_transcurrido,
            "imagen_nombre": uploaded_file.name if uploaded_file else "no_imagen"
        }
        col.insert_one(doc)

        # Resetear
        st.session_state.cronometro_activo = False
        st.session_state.inicio_cronometro = None
        st.session_state.objetos_detectados = []
        st.session_state.seleccionados = []

        st.rerun()