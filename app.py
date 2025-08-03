import streamlit as st
from datetime import datetime, timedelta
import time
import base64
import openai
from pymongo import MongoClient
from PIL import Image
from io import BytesIO
import pandas as pd
import requests

# === CONFIGURACIÓN ===
st.set_page_config(page_title="👁️ Proyecto 10K – Visión Resiliente", layout="centered")
st.title("👁️ Proyecto 10K – Visión Resiliente")

# === CLAVES SEGURAS ===
openai.api_key = st.secrets["openai_api_key"]
client = MongoClient(st.secrets["mongo_uri"])
db = client["proyecto_10k"]
col = db["objetos_organizados"]

# === SUBIDA DE IMAGEN ===
imagen = st.file_uploader("📤 Sube una imagen", type=["jpg", "jpeg", "png"])

if imagen:
    st.image(imagen, caption="Imagen cargada", use_container_width=True)

    # Codificar imagen
    bytes_imagen = imagen.read()
    imagen_pil = Image.open(BytesIO(bytes_imagen))
    buffered = BytesIO()
    imagen_pil.save(buffered, format="JPEG")
    imagen_codificada = base64.b64encode(buffered.getvalue()).decode()
    st.session_state.imagen_codificada = imagen_codificada
    st.session_state.imagen_nombre = imagen.name

    objetos_detectados = []
    fuente = ""

    # === DETECCIÓN GPT-4o (PRIMER INTENTO) ===
    with st.spinner("🔍 Detectando objetos con OpenAI..."):
        try:
            respuesta = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "Eres un asistente visual que enumera objetos en imágenes. Solo lista los nombres, separados por comas."
                    },
                    {
                        "role": "user",
                        "content": f"¿Qué objetos ves en esta imagen?: {imagen_codificada}"
                    }
                ]
            )
            contenido = respuesta.choices[0].message.content
            objetos_detectados = [x.strip() for x in contenido.split(",") if x.strip()]
            fuente = "OpenAI GPT-4o"
        except openai.OpenAIError:
            # === BACKUP: Hugging Face ===
            st.warning("⚠️ GPT-4o no disponible. Usando motor alterno gratuito (Hugging Face)...")
            api_url = "https://api-inference.huggingface.co/models/Salesforce/blip-image-captioning-base"
            headers = {"Accept": "application/json"}
            response = requests.post(
                api_url,
                headers=headers,
                files={"image": buffered.getvalue()}
            )
            try:
                data = response.json()
                if isinstance(data, list) and "generated_text" in data[0]:
                    texto = data[0]["generated_text"]
                    objetos_detectados = [x.strip().lower() for x in texto.replace(".", "").split() if len(x) > 3]
                    fuente = "Hugging Face (backup)"
            except:
                st.error("❌ No fue posible detectar objetos con ningún modelo.")

    if objetos_detectados:
        st.markdown(f"### 🔎 Objetos detectados por IA ({fuente}):")
        seleccionados = {}

        for idx, obj in enumerate(objetos_detectados):
            check = st.checkbox(f"{obj}", key=f"chk_{idx}")
            if check:
                orden = st.number_input(f"Orden para '{obj}':", min_value=1, step=1, key=f"orden_{idx}")
                seleccionados[obj] = {"orden": orden}

        # === FLUJO DE ORGANIZACIÓN ===
        if seleccionados:
            st.divider()
            st.subheader("🛠️ Organización guiada")

            if "lista_ordenada" not in st.session_state:
                st.session_state.lista_ordenada = sorted(seleccionados.items(), key=lambda x: x[1]["orden"])
                st.session_state.paso_actual = 0

            lista_ordenada = st.session_state.lista_ordenada
            paso = st.session_state.paso_actual

            if paso < len(lista_ordenada):
                objeto_actual, data = lista_ordenada[paso]
                orden_actual = data["orden"]
                st.markdown(f"### 👉 Objeto {orden_actual}: **{objeto_actual}**")

                key_inicio = f"inicio_{objeto_actual}"
                key_tiempo = f"tiempo_{objeto_actual}"

                if key_inicio not in st.session_state:
                    st.session_state[key_inicio] = None
                    st.session_state[key_tiempo] = 0

                if st.session_state[key_inicio] is None:
                    if st.button("⏱️ Iniciar organización"):
                        st.session_state[key_inicio] = time.time()
                        st.rerun()
                else:
                    tiempo_actual = int(time.time() - st.session_state[key_inicio])
                    st.session_state[key_tiempo] = tiempo_actual
                    formato = str(timedelta(seconds=tiempo_actual))

                    color = "green" if tiempo_actual < 120 else "red"
                    icono = "" if tiempo_actual < 120 else "🔔"

                    st.markdown(f"<h4>⏱️ Tiempo organizando: <span style='color:{color}'>{formato}</span> {icono}</h4>", unsafe_allow_html=True)
                    time.sleep(1)
                    st.rerun()

                lugar = st.text_input(f"📍 ¿Dónde quedará '{objeto_actual}'?")

                if lugar and st.session_state[key_inicio] is not None:
                    if st.button("✅ Registrar y pasar al siguiente"):
                        col.insert_one({
                            "fecha": datetime.utcnow(),
                            "objeto": objeto_actual,
                            "orden": orden_actual,
                            "lugar_asignado": lugar,
                            "tiempo_organizacion_segundos": st.session_state[key_tiempo],
                            "fuente": fuente,
                            "nombre_imagen": st.session_state.imagen_nombre,
                            "imagen_base64": st.session_state.imagen_codificada
                        })
                        st.success(f"📦 '{objeto_actual}' registrado.")
                        st.session_state.paso_actual += 1
                        st.rerun()
            else:
                st.balloons()
                st.success("🎉 Todos los objetos fueron organizados.")
                if st.button("🔄 Reiniciar todo"):
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()
    else:
        st.info("No se detectaron objetos.")

# === HISTORIAL Y PROGRESO GLOBAL ===
with st.expander("📜 Historial"):
    docs = list(col.find().sort("fecha", -1))
    if docs:
        df = pd.DataFrame(docs)
        df["fecha"] = df["fecha"].dt.strftime("%Y-%m-%d %H:%M:%S")
        df = df[["fecha", "objeto", "orden", "lugar_asignado", "tiempo_organizacion_segundos", "fuente"]]
        df["tiempo_h:m:s"] = df["tiempo_organizacion_segundos"].apply(lambda s: str(timedelta(seconds=s)))
        st.dataframe(df)

        total_segundos = sum(doc.get("tiempo_organizacion_segundos", 0) for doc in docs)
        total_horas = total_segundos / 3600
        porcentaje = min(total_horas / 10000, 1.0)
        tiempo_formateado = str(timedelta(seconds=total_segundos))

        st.subheader("⏱️ Progreso hacia las 10.000 horas")
        st.markdown(f"**Tiempo acumulado organizando:** `{tiempo_formateado}`")
        st.progress(porcentaje, text=f"{total_horas:.2f} horas / 10.000 horas")
    else:
        st.info("Aún no hay registros.")

# === ENLACE PARA REVISAR SALDO OPENAI ===
st.markdown("🔗 [Verifica tu saldo de tokens en OpenAI](https://platform.openai.com/usage)")