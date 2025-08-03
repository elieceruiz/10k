import streamlit as st
from pymongo import MongoClient
from datetime import datetime
import pytz
import time
from PIL import Image
import openai
import base64
import io

# --- CONFIGURACIÓN DE LA APP ---
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# --- CLAVES Y CLIENTES ---
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

openai.api_key = st.secrets["openai_api_key"]
tz = pytz.timezone("America/Bogota")

# --- ESTADO INICIAL ---
if "objetos" not in st.session_state:
    st.session_state.objetos = []
if "orden" not in st.session_state:
    st.session_state.orden = []
if "crono_activo" not in st.session_state:
    st.session_state.crono_activo = False
if "inicio_sesion" not in st.session_state:
    st.session_state.inicio_sesion = None
if "tiempos_objetos" not in st.session_state:
    st.session_state.tiempos_objetos = {}
if "actual" not in st.session_state:
    st.session_state.actual = 0

# --- SUBIR IMAGEN ---
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if uploaded_file:
    st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)

    # --- BOTÓN DE DETECCIÓN ---
    if st.button("🔍 Detectar objetos"):
        try:
            image_bytes = uploaded_file.getvalue()
            base64_image = base64.b64encode(image_bytes).decode("utf-8")

            prompt = "Enumera los objetos visibles en esta imagen, sin descripciones ni contexto. Solo nombres de objetos en español, máximo 10 elementos, en formato de lista JSON."

            respuesta = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Eres un modelo que detecta objetos en imágenes."},
                    {"role": "user", "content": [{"type": "text", "text": prompt},
                                                 {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}]},
                ],
                max_tokens=200,
            )

            texto = respuesta.choices[0].message.content.strip()
            try:
                objetos_detectados = eval(texto)
                if isinstance(objetos_detectados, list):
                    st.session_state.objetos = objetos_detectados
                    st.session_state.orden = []
                    st.session_state.tiempos_objetos = {}
                    st.rerun()
                else:
                    st.error("La respuesta no fue una lista.")
            except Exception as e:
                st.error(f"Error en la detección: {e}")
        except Exception as e:
            st.error(f"Error general: {e}")

# --- MOSTRAR OBJETOS DETECTADOS ---
if st.session_state.objetos:
    st.subheader("📦 Objetos detectados:")
    for i, obj in enumerate(st.session_state.objetos):
        col1, col2 = st.columns([0.1, 0.9])
        with col1:
            if st.button("✅", key=f"check_{i}"):
                if obj not in st.session_state.orden:
                    st.session_state.orden.append(obj)
                    st.rerun()
        with col2:
            st.markdown(f"**{obj}**")

# --- MOSTRAR ORDEN DE UBICACIÓN ---
if st.session_state.orden:
    st.subheader("📌 Orden de ubicación:")
    for i, obj in enumerate(st.session_state.orden):
        st.markdown(f"{i+1}. {obj}")

    if not st.session_state.crono_activo:
        if st.button("▶️ Iniciar sesión"):
            st.session_state.crono_activo = True
            st.session_state.inicio_sesion = datetime.now(tz)
            st.session_state.actual = 0
            st.session_state.tiempos_objetos = {}
            st.rerun()

# --- CRONÓMETRO ACTIVO ---
if st.session_state.crono_activo:
    st.subheader("⏱ Cronometrando...")

    ahora = datetime.now(tz)
    inicio = st.session_state.inicio_sesion
    transcurrido = (ahora - inicio).total_seconds()
    st.markdown(f"🧭 Tiempo total transcurrido: **{int(transcurrido)} segundos**")

    actual_idx = st.session_state.actual
    if actual_idx < len(st.session_state.orden):
        obj_actual = st.session_state.orden[actual_idx]
        st.markdown(f"🔧 Ubicando: **{obj_actual}**")

        if st.button("✅ Terminé con este"):
            tiempo_obj = datetime.now(tz) - st.session_state.inicio_sesion
            segundos = int(tiempo_obj.total_seconds())
            st.session_state.tiempos_objetos[obj_actual] = segundos

            st.session_state.actual += 1
            st.session_state.inicio_sesion = datetime.now(tz)
            st.rerun()
    else:
        st.success("🎯 ¡Todos los objetos han sido ubicados!")
        doc = {
            "fecha": datetime.now(tz),
            "objetos": st.session_state.orden,
            "tiempos": st.session_state.tiempos_objetos,
            "total_segundos": sum(st.session_state.tiempos_objetos.values())
        }
        col.insert_one(doc)
        st.session_state.crono_activo = False
        st.session_state.objetos = []
        st.session_state.orden = []
        st.session_state.tiempos_objetos = {}
        st.balloons()