import streamlit as st
from pymongo import MongoClient
from datetime import datetime
from PIL import Image
import io
import base64
import pytz
import openai
import time
import uuid

# === CONFIGURACIÓN ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === VARIABLES SENSIBLES ===
MONGO_URI = st.secrets["mongo_uri"]
openai.api_key = st.secrets["openai_api_key"]

# === CONEXIONES ===
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

tz = pytz.timezone("America/Bogota")

# === SUBIDA DE IMAGEN ===
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if uploaded_file:
    st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)

    # Convertir imagen a base64
    image_bytes = uploaded_file.read()
    imagen_base64 = base64.b64encode(image_bytes).decode()

    if st.button("🧠 Detectar objetos"):
        with st.spinner("Analizando la imagen con GPT-4o..."):
            try:
                respuesta = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": "Detecta y lista brevemente los objetos visibles en una imagen. Devuelve solo una lista con nombres de objetos."
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "¿Qué objetos ves en esta imagen?"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagen_base64}"}}
                            ]
                        }
                    ],
                    max_tokens=300,
                    temperature=0.3,
                )
                texto = respuesta.choices[0].message.content.strip()
                objetos_detectados = [obj.strip("•- ").strip() for obj in texto.split("\n") if obj.strip()]

                if objetos_detectados:
                    st.success("✅ Objetos detectados por IA.")
                    st.markdown("**📦 Objetos detectados:**")
                    objeto_checks = {}
                    for i, obj in enumerate(objetos_detectados, 1):
                        objeto_checks[obj] = st.checkbox(f"{i}. {obj}", key=f"chk_{i}")

                    if st.button("🕒 Iniciar sesión de práctica"):
                        seleccionados = [k for k, v in objeto_checks.items() if v]
                        if seleccionados:
                            session_id = str(uuid.uuid4())
                            inicio = datetime.now(tz)
                            st.session_state["session_data"] = {
                                "id": session_id,
                                "inicio": inicio,
                                "objetos": seleccionados,
                                "tiempos": {obj: 0 for obj in seleccionados},
                                "activo": True,
                                "obj_actual": 0,
                                "ultima_vez": time.time(),
                                "imagen": imagen_base64
                            }
                            st.rerun()
                        else:
                            st.warning("Selecciona al menos un objeto para iniciar.")

            except openai.RateLimitError:
                st.error("🚫 Límite de uso alcanzado. Espera unos segundos e intenta de nuevo.")
            except openai.AuthenticationError:
                st.error("🚫 API Key inválida o no autorizada.")
            except Exception as e:
                st.error(f"❌ Error en la detección: {e}")

# === SESIÓN ACTIVA ===
if "session_data" in st.session_state and st.session_state["session_data"]["activo"]:
    data = st.session_state["session_data"]
    st.subheader("⏱️ Cronómetro en curso")

    tiempo_actual = time.time()
    transcurrido = tiempo_actual - data["ultima_vez"]
    obj = data["objetos"][data["obj_actual"]]
    data["tiempos"][obj] += transcurrido
    data["ultima_vez"] = tiempo_actual

    st.write(f"🟢 Objeto actual: **{obj}**")
    st.write(f"⏳ Tiempo en este objeto: `{int(data['tiempos'][obj])} seg`")

    if st.button("⏩ Siguiente objeto"):
        if data["obj_actual"] + 1 < len(data["objetos"]):
            data["obj_actual"] += 1
            data["ultima_vez"] = time.time()
            st.rerun()
        else:
            # Terminar sesión
            fin = datetime.now(tz)
            doc = {
                "timestamp": fin,
                "duracion_seg": sum(data["tiempos"].values()),
                "objetos": data["objetos"],
                "tiempos": data["tiempos"],
                "imagen": data["imagen"]
            }
            col.insert_one(doc)
            st.success("✅ Sesión registrada.")
            del st.session_state["session_data"]
            st.rerun()

# === HISTORIAL DE SESIONES ===
st.subheader("📚 Historial de sesiones")
registros = list(col.find().sort("timestamp", -1).limit(5))

if registros:
    for reg in registros:
        try:
            fecha = reg["timestamp"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
            st.markdown(f"#### 📅 {fecha}")
            st.image(base64.b64decode(reg["imagen"]), caption="📷 Imagen registrada", use_container_width=True)
            for i, obj in enumerate(reg["objetos"], 1):
                t = int(reg["tiempos"].get(obj, 0))
                st.write(f"{i}. {obj} – {t} seg")
            st.markdown("---")
        except Exception:
            st.warning("⚠️ Registro corrupto o incompleto.")
else:
    st.info("No hay sesiones completas registradas aún.")