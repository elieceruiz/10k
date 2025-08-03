import streamlit as st
from PIL import Image
import io
import base64
import time
from datetime import datetime
import pytz
from pymongo import MongoClient
import openai

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="👁️ Visión GPT – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")
st.markdown("📤 Sube una imagen")

# --- CONEXIÓN MONGO ---
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

# --- CLAVE OPENAI ---
openai.api_key = st.secrets["openai_api_key"]

# --- ZONA HORARIA CO ---
tz = pytz.timezone("America/Bogota")

# --- SUBIDA DE IMAGEN ---
imagen = st.file_uploader("Arrastra o selecciona una imagen", type=["jpg", "jpeg", "png"])
if imagen:
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    # Procesar solo si no se ha hecho antes
    if "objetos_detectados" not in st.session_state:
        bytes_imagen = imagen.read()
        imagen_base64 = base64.b64encode(bytes_imagen).decode("utf-8")
        prompt = f"""
Eres un asistente de visión artificial. Detecta SOLO los objetos claramente visibles en esta imagen en base64, devuélvelos como lista JSON simple, sin descripciones. Ejemplo: ["maleta", "celular", "cuaderno"]
Imagen base64 (recortada):
{imagen_base64[:4000]}...
"""
        try:
            respuesta = openai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=150
            )
            texto = respuesta.choices[0].message.content.strip()
            st.session_state.objetos_detectados = eval(texto)
            st.session_state.imagen_bytes = bytes_imagen
            st.success("✅ Objetos detectados por IA.")
        except Exception as e:
            st.error(f"❌ Error en la detección: {e}")

# --- LISTAR Y SELECCIONAR ORDEN ---
if "objetos_detectados" in st.session_state:
    st.subheader("📦 Objetos detectados:")
    objetos = st.session_state.objetos_detectados
    orden_elegido = {}

    for i, obj in enumerate(objetos):
        if obj not in st.session_state:
            st.session_state[obj] = {"iniciado": False, "inicio": None, "duracion": 0}

        col1, col2 = st.columns([3, 1])
        with col1:
            orden = st.select_slider(f"{obj}", options=list(range(1, len(objetos) + 1)), key=f"orden_{obj}")
        with col2:
            iniciar = st.button(f"▶️ Iniciar {obj}", key=f"iniciar_{obj}")

        if iniciar and not st.session_state[obj]["iniciado"]:
            st.session_state[obj]["iniciado"] = True
            st.session_state[obj]["inicio"] = time.time()
            st.rerun()

        if st.session_state[obj]["iniciado"]:
            ahora = time.time()
            transcurrido = int(ahora - st.session_state[obj]["inicio"])
            st.info(f"🕒 {obj} en proceso: {transcurrido} segundos")

            if st.button(f"✅ Finalizar {obj}", key=f"finalizar_{obj}"):
                fin = time.time()
                duracion = int(fin - st.session_state[obj]["inicio"])
                # Guardar en Mongo
                doc = {
                    "objeto": obj,
                    "duracion_segundos": duracion,
                    "fecha": datetime.now(tz),
                    "orden": st.session_state[f"orden_{obj}"],
                    "imagen_base64": base64.b64encode(st.session_state.imagen_bytes).decode("utf-8")
                }
                col.insert_one(doc)
                st.success(f"✔️ Registrado: {obj} – {duracion} segundos")
                # Resetear estado del objeto
                st.session_state[obj] = {"iniciado": False, "inicio": None, "duracion": duracion}
                st.rerun()

# --- HISTORIAL DE OBJETOS REGISTRADOS ---
with st.expander("🕓 Historial reciente"):
    registros = list(col.find().sort("fecha", -1).limit(10))
    for reg in registros:
        st.write(f"📌 **{reg['objeto']}** – ⏱️ {reg['duracion_segundos']}s – 🗓️ {reg['fecha'].strftime('%Y-%m-%d %H:%M:%S')}")

# --- ENLACE A USO DE OPENAI ---
st.markdown("---")
st.markdown("🔗 [Ver uso de OpenAI](https://platform.openai.com/usage)")