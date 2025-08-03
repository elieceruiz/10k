import streamlit as st
from pymongo import MongoClient
from PIL import Image
import openai
import pytz
import io
import time
from datetime import datetime

# --- CONFIG STREAMLIT ---
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# --- CONEXIÓN MONGO ---
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

# --- CLAVE OPENAI ---
openai.api_key = st.secrets["openai_api_key"]

# --- ZONA HORARIA CO ---
tz = pytz.timezone("America/Bogota")

# --- ESTADOS DE SESIÓN ---
if "objetos_detectados" not in st.session_state:
    st.session_state.objetos_detectados = []

if "seleccionados" not in st.session_state:
    st.session_state.seleccionados = {}

if "cronometros" not in st.session_state:
    st.session_state.cronometros = {}

if "inicio_global" not in st.session_state:
    st.session_state.inicio_global = None

# --- SUBIR IMAGEN ---
imagen = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if imagen:
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    # Detectar objetos al presionar botón
    if st.button("🔍 Detectar objetos"):
        try:
            bytes_imagen = imagen.read()
            base64_imagen = bytes_imagen.encode("base64") if isinstance(bytes_imagen, str) else bytes_imagen

            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Eres un experto en visión por computadora."},
                    {"role": "user", "content": f"Describe en palabras simples los objetos visibles en esta imagen."}
                ],
                max_tokens=100  # límite impuesto para evitar errores
            )

            texto = response.choices[0].message.content
            objetos = [line.strip(" .") for line in texto.split(",") if line.strip()]
            st.session_state.objetos_detectados = objetos
            st.session_state.seleccionados = {}
            st.session_state.cronometros = {}

            st.success("✅ Objetos detectados por IA.")

        except Exception as e:
            st.error(f"Error en la detección: {e}")

# --- MOSTRAR OBJETOS DETECTADOS ---
if st.session_state.objetos_detectados:
    st.subheader("📦 Objetos detectados:")
    for idx, obj in enumerate(st.session_state.objetos_detectados, 1):
        col1, col2 = st.columns([0.8, 0.2])
        with col1:
            check = st.checkbox(f"{idx}. {obj}", key=f"check_{idx}")
        with col2:
            if check:
                if obj not in st.session_state.seleccionados:
                    st.session_state.seleccionados[obj] = time.time()
                    st.success(f"Iniciado: {obj}")
            else:
                if obj in st.session_state.seleccionados:
                    fin = time.time()
                    duracion = round(fin - st.session_state.seleccionados[obj])
                    st.session_state.cronometros[obj] = duracion
                    del st.session_state.seleccionados[obj]

# --- BOTÓN PARA FINALIZAR Y GUARDAR ---
if st.button("💾 Finalizar sesión"):
    ahora = datetime.now(tz)
    doc = {
        "fecha": ahora.isoformat(),
        "objetos": list(st.session_state.cronometros.keys()),
        "tiempos": st.session_state.cronometros,
        "total_segundos": sum(st.session_state.cronometros.values())
    }
    col.insert_one(doc)
    st.success("✅ Sesión guardada en MongoDB.")
    st.session_state.objetos_detectados = []
    st.session_state.seleccionados = {}
    st.session_state.cronometros = {}

# --- MOSTRAR CRONÓMETRO GLOBAL ---
if st.session_state.seleccionados:
    st.subheader("🕒 Cronómetro en curso:")
    for obj, inicio in st.session_state.seleccionados.items():
        transcurrido = round(time.time() - inicio)
        st.markdown(f"- **{obj}**: {transcurrido} segundos")