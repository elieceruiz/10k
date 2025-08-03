import streamlit as st
from pymongo import MongoClient
from PIL import Image
from io import BytesIO
import openai
import pytz
from datetime import datetime, timedelta
import base64
import json
import time

# === CONFIGURACIÓN GENERAL ===
st.set_page_config(page_title="👁️ Visión GPT-4o – Proyecto 10K", layout="centered")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# === SECRETOS Y CONEXIONES ===
MONGO_URI = st.secrets["mongo_uri"]
client = MongoClient(MONGO_URI)
db = client["proyecto_10k"]
col = db["registro_sesiones"]

openai.api_key = st.secrets["openai_api_key"]
tz = pytz.timezone("America/Bogota")

# === SUBIDA DE IMAGEN ===
imagen = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if imagen:
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    # Convertir imagen a base64
    image_bytes = imagen.read()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    if st.button("🔍 Detectar objetos"):
        with st.spinner("Procesando con IA..."):
            try:
                response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Eres un detector visual de objetos."},
                        {"role": "user", "content": "Analiza esta imagen y devuelve SOLO una lista JSON válida (ej: [\"objeto1\", \"objeto2\"]) con los nombres de los objetos visibles, sin ningún texto adicional."},
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=150,
                    temperature=0.2
                )

                resultado = response.choices[0].message.content.strip()

                # --- Intentar convertir la respuesta en JSON ---
                try:
                    objetos_detectados = json.loads(resultado)
                    st.success("✅ Objetos detectados por IA.")
                except json.JSONDecodeError:
                    st.error("❌ La respuesta de OpenAI no es una lista JSON válida.")
                    st.code(resultado)
                    objetos_detectados = []

            except Exception as e:
                st.error(f"Error en la detección: {str(e)}")
                objetos_detectados = []

        # === MOSTRAR OBJETOS DETECTADOS Y ORDEN ===
        if objetos_detectados:
            st.subheader("📦 Objetos detectados:")
            elementos_ordenados = []

            for idx, obj in enumerate(objetos_detectados):
                col1, col2 = st.columns([0.1, 0.9])
                with col1:
                    check = st.checkbox(f"{idx+1}", key=f"check_{idx}")
                with col2:
                    st.write(f"**{obj}**")

                if check:
                    elementos_ordenados.append(obj)

            if st.button("🚀 Iniciar cronómetro"):
                start_time = datetime.now(tz)
                st.session_state["start"] = start_time
                st.success("Cronómetro iniciado...")

        # === CRONÓMETRO GLOBAL ===
        if "start" in st.session_state:
            elapsed = datetime.now(tz) - st.session_state["start"]
            minutos = elapsed.total_seconds() // 60
            segundos = int(elapsed.total_seconds() % 60)
            st.markdown(f"🧭 **Tiempo transcurrido:** {int(minutos):02d}:{segundos:02d}")

            # Guardar en Mongo
            doc = {
                "timestamp": datetime.now(tz),
                "objetos": elementos_ordenados,
                "duracion_segundos": int(elapsed.total_seconds())
            }
            col.insert_one(doc)

# === HISTORIAL DE SESIONES ===
with st.expander("📜 Ver historial"):
    registros = list(col.find().sort("timestamp", -1).limit(10))
    for reg in registros:
        fecha = reg["timestamp"].astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")
        objetos = ", ".join(reg.get("objetos", []))
        dur = reg.get("duracion_segundos", 0)
        st.markdown(f"- **{fecha}** → ⏱ {dur} seg | 📦 {objetos}")