# === IMPORTS ===
import streamlit as st
from pymongo import MongoClient
from datetime import datetime, timedelta
from PIL import Image
import base64
from io import BytesIO
import openai
import pytz
import time

# === CONFIGURACIÓN ===
st.set_page_config(page_title="Visión GPT-4o – Proyecto 10K", layout="wide")
st.title("👁️ Visión GPT-4o – Proyecto 10K")
tz = pytz.timezone("America/Bogota")

# === SECRETOS ===
MONGO_URI = st.secrets["mongo_uri"]
OPENAI_API_KEY = st.secrets["openai_api_key"]

# === CONEXIONES ===
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["ubicaciones_migracion"]
openai.api_key = OPENAI_API_KEY

# === FUNCIONES ===
def convertir_imagen_base64(imagen):
    buffer = BytesIO()
    imagen.save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode()

def reducir_imagen(imagen, max_ancho=600):
    if imagen.width > max_ancho:
        proporcion = max_ancho / imagen.width
        nuevo_tamano = (int(imagen.width * proporcion), int(imagen.height * proporcion))
        return imagen.resize(nuevo_tamano)
    return imagen

# === SESSION STATE ===
for key in ["fase", "objeto_en_ubicacion", "inicio_ubicacion", "imagen_b64"]:
    if key not in st.session_state:
        st.session_state[key] = None

# === PESTAÑAS ===
tab_migracion, tab_historial = st.tabs(["🧪 Migración", "📚 Historial"])

# === TAB MIGRACIÓN ===
with tab_migracion:
    # Si no hay sesión activa, verifica si hay en Mongo
    if not st.session_state["inicio_ubicacion"]:
        doc_activo = col.find_one({"fin": None})
        if doc_activo:
            st.session_state["fase"] = "ubicando"
            st.session_state["inicio_ubicacion"] = doc_activo["inicio"]
            st.session_state["objeto_en_ubicacion"] = doc_activo["objeto"]
            st.session_state["imagen_b64"] = doc_activo.get("imagen_b64")
        else:
            st.session_state["fase"] = "espera_foto"

    # === FASE: Espera de foto ===
    if st.session_state["fase"] == "espera_foto":
        archivo = st.file_uploader("📷 Sube una foto para análisis", type=["jpg", "jpeg", "png"])
        if archivo:
            imagen = Image.open(archivo)
            imagen_reducida = reducir_imagen(imagen)
            imagen_b64 = convertir_imagen_base64(imagen_reducida)
            b64_img = "data:image/jpeg;base64," + imagen_b64

            with st.spinner("⏳ Enviando imagen a GPT-4o..."):
                try:
                    respuesta = openai.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "user", "content": [
                                {"type": "text", "text": "Detecta solo objetos visibles. Devuelve una lista clara."},
                                {"type": "image_url", "image_url": {"url": b64_img}}
                            ]}
                        ],
                        max_tokens=300
                    )
                    texto = respuesta.choices[0].message.content
                    objetos = [o.strip("-• ").capitalize() for o in texto.split("\n") if o.strip()]

                    if not objetos:
                        st.warning("⚠️ No se detectaron objetos.")
                        st.stop()

                    seleccion = st.selectbox("Selecciona el objeto a ubicar:", objetos)
                    if seleccion and st.button("🟢 Iniciar ubicación"):
                        ahora = datetime.now(tz)
                        col.insert_one({
                            "objeto": seleccion,
                            "inicio": ahora,
                            "fin": None,
                            "imagen_b64": imagen_b64
                        })
                        st.session_state["fase"] = "ubicando"
                        st.session_state["objeto_en_ubicacion"] = seleccion
                        st.session_state["inicio_ubicacion"] = ahora
                        st.session_state["imagen_b64"] = imagen_b64
                        st.rerun()

                except Exception as e:
                    st.error(f"❌ Error al procesar imagen: {e}")

    # === FASE: Ubicando (cronómetro real) ===
    elif st.session_state["fase"] == "ubicando":
        st.success(f"📍 Ubicando: `{st.session_state['objeto_en_ubicacion']}`")
        cronometro = st.empty()

        # Mostrar cronómetro en tiempo real sin bloquear
        ahora = datetime.now(tz)
        inicio = st.session_state["inicio_ubicacion"]
        duracion = ahora - inicio
        tiempo_str = str(duracion).split(".")[0]
        cronometro.info(f"⏱️ Tiempo transcurrido: `{tiempo_str}`")

        # Forzar actualización cada segundo
        st.experimental_rerun()

        # Finalización de la ubicación
        lugar = st.text_input("📌 ¿Dónde quedó ubicado?")
        if lugar and st.button("⏹ Finalizar ubicación"):
            fin = datetime.now(tz)
            col.update_one(
                {
                    "objeto": st.session_state["objeto_en_ubicacion"],
                    "inicio": st.session_state["inicio_ubicacion"],
                    "fin": None
                },
                {
                    "$set": {
                        "fin": fin,
                        "ubicacion": lugar,
                        "duracion_segundos": (fin - inicio).total_seconds()
                    }
                }
            )
            st.success("✅ Ubicación finalizada.")
            for key in ["fase", "objeto_en_ubicacion", "inicio_ubicacion", "imagen_b64"]:
                st.session_state[key] = None
            st.rerun()

# === TAB HISTORIAL ===
with tab_historial:
    registros = list(col.find().sort("inicio", -1))
    if registros:
        for reg in registros:
            fecha = reg["inicio"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
            with st.expander(f"🕓 {fecha} — {reg.get('objeto', 'Sin nombre')}"):
                if "imagen_b64" in reg:
                    st.image(Image.open(BytesIO(base64.b64decode(reg["imagen_b64"]))), width=300)

                st.write(f"🧱 Objeto: {reg.get('objeto')}")
                st.write(f"📌 Ubicación: {reg.get('ubicacion', '—')}")
                st.write(f"⏱️ Duración: {round(reg.get('duracion_segundos', 0))} segundos")
    else:
        st.info("📭 No hay registros aún.")