import streamlit as st
import openai
from pymongo import MongoClient
from PIL import Image
import pytz
from datetime import datetime
import time
import io

# --- CONFIGURACIÓN GENERAL ---
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# --- CLAVES Y CONEXIÓN ---
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

openai.api_key = st.secrets["openai_api_key"]
tz = pytz.timezone("America/Bogota")

# --- SESIÓN Y VARIABLES DE ESTADO ---
if "img_bytes" not in st.session_state:
    st.session_state.img_bytes = None
if "objetos_detectados" not in st.session_state:
    st.session_state.objetos_detectados = []
if "orden" not in st.session_state:
    st.session_state.orden = []
if "cronometro_activo" not in st.session_state:
    st.session_state.cronometro_activo = False
if "inicio_cronometro" not in st.session_state:
    st.session_state.inicio_cronometro = None

# --- SUBIDA DE IMAGEN ---
imagen = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if imagen:
    st.session_state.img_bytes = imagen.read()
    st.image(st.session_state.img_bytes, caption="Imagen cargada", use_container_width=True)

    # --- LLAMADA A OPENAI PARA DETECCIÓN DE OBJETOS ---
    with st.spinner("Analizando imagen..."):
        prompt = "Lista los objetos visibles en esta imagen, en viñetas simples (máximo 8), sin dar contexto ni explicación."
        try:
            base64_image = st.session_state.img_bytes.encode("base64") if isinstance(st.session_state.img_bytes, str) else None
            respuesta = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Eres un asistente que identifica objetos en imágenes."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.2,
            )
            texto = respuesta.choices[0].message.content
            objetos = [obj for obj in texto.split("\n") if any(c.isalpha() for c in obj)]
            objetos = [obj.strip("•-•. 0123456789").strip() for obj in objetos if len(obj.strip()) > 2]
            st.session_state.objetos_detectados = objetos
            st.session_state.orden = []
        except Exception as e:
            st.error(f"Error en la detección: {e}")

# --- MOSTRAR OBJETOS DETECTADOS Y SELECCIÓN ---
if st.session_state.objetos_detectados:
    st.markdown("### 📦 Objetos detectados:")
    for i, obj in enumerate(st.session_state.objetos_detectados):
        col1, col2 = st.columns([0.1, 0.9])
        with col1:
            check = st.checkbox("", key=f"check_{i}")
        with col2:
            st.markdown(f"**{obj}**")

    if st.button("✅ Iniciar ordenamiento"):
        seleccionados = [
            st.session_state.objetos_detectados[i]
            for i in range(len(st.session_state.objetos_detectados))
            if st.session_state.get(f"check_{i}", False)
        ]
        if seleccionados:
            st.session_state.orden = seleccionados
            st.session_state.inicio_cronometro = datetime.now(tz)
            st.session_state.cronometro_activo = True
            st.rerun()

# --- CRONÓMETRO Y ORDENAMIENTO ---
if st.session_state.cronometro_activo and st.session_state.orden:
    st.markdown("### 🕒 Ordenando objetos:")
    tiempo_transcurrido = (datetime.now(tz) - st.session_state.inicio_cronometro).total_seconds()
    minutos = int(tiempo_transcurrido // 60)
    segundos = int(tiempo_transcurrido % 60)
    st.markdown(f"🧭 Tiempo transcurrido: `{minutos:02d}:{segundos:02d}`")

    for i, item in enumerate(st.session_state.orden, start=1):
        st.markdown(f"{i}. {item}")

    if st.button("📝 Finalizar sesión"):
        doc = {
            "fecha": datetime.now(tz),
            "objetos": st.session_state.orden,
            "tiempo_segundos": int(tiempo_transcurrido)
        }
        col.insert_one(doc)
        st.success("✅ Sesión registrada exitosamente.")
        # Reset
        st.session_state.cronometro_activo = False
        st.session_state.orden = []
        st.session_state.objetos_detectados = []
        st.rerun()