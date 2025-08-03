import streamlit as st
from openai import OpenAI
from pymongo import MongoClient
from datetime import datetime
import pytz

# Configuración inicial
st.set_page_config(page_title="📸 Visión GPT-4o", layout="wide")
st.title("👁️ Visión GPT-4o – Proyecto 10K")

# Mongo y zona horaria
client = MongoClient(st.secrets["mongo_uri"])
db = client["proyecto_10k"]
col = db["registro_sesiones"]
tz = pytz.timezone("America/Bogota")

# API Key OpenAI
openai_api_key = st.secrets["openai_api_key"]
client_ai = OpenAI(api_key=openai_api_key)

# Subida de imagen
uploaded_file = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])
if uploaded_file:
    st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)

    if st.button("🔍 Detectar objetos"):
        with st.spinner("Analizando con GPT-4o..."):
            try:
                # Enviar imagen directamente como archivo (recomendado para GPT-4o)
                response = client_ai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Eres un modelo experto en visión por computadora."},
                        {"role": "user", "content": "Describe brevemente los objetos visibles en esta imagen."}
                    ],
                    files=[{"file": uploaded_file}],
                    max_tokens=500
                )
                resultado = response.choices[0].message.content

                st.success("✅ Objetos detectados por IA.")
                st.write("📦 Objetos detectados:")
                st.markdown(f"- {resultado}")

                # Guardar en MongoDB
                doc = {
                    "timestamp": datetime.now(tz),
                    "descripcion": resultado,
                    "filename": uploaded_file.name
                }
                col.insert_one(doc)

            except Exception as e:
                st.error(f"Error en la detección: {e}")