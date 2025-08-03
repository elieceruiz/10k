import streamlit as st
import openai
import base64
import requests
from datetime import datetime
import time
from pymongo import MongoClient

# === CONFIG APP ===
st.set_page_config(page_title="🧠 Proyecto 10K – Organización guiada", layout="centered")
st.title("📸 Visión y Orden – Proyecto 10K")

# === SECRETS ===
openai.api_key = st.secrets["openai_api_key"]
mongo_uri = st.secrets["mongo_uri"]

# === CONEXIÓN MONGO ===
client = MongoClient(mongo_uri)
db = client["proyecto10k"]
col = db["organizacion_guiada"]

# === CARGA DE IMAGEN ===
uploaded_file = st.file_uploader("📤 Sube una imagen del entorno a organizar", type=["jpg", "jpeg", "png"])

# === NOMBRE USUARIO ===
username = st.text_input("🧍 Tu nombre:", "eliecer")

if uploaded_file:
    st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)
    bytes_data = uploaded_file.read()
    encoded_image = base64.b64encode(bytes_data).decode("utf-8")
    image_url = f"data:image/jpeg;base64,{encoded_image}"

    # === GPT-4o DETECCIÓN ===
    with st.spinner("🔍 Detectando objetos en la imagen..."):
        try:
            response = openai.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "Detectá y listá objetos visibles. No describas. Solo nombrá los elementos visibles, separados por comas."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Detectá objetos visibles en esta imagen y listalos, separados por comas."},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                ],
                max_tokens=150,
            )

            resultado = response.choices[0].message.content.strip()
            st.success("🎯 Objetos detectados:")
            st.write(resultado)

            objetos_detectados = [o.strip() for o in resultado.split(",") if o.strip()]
            st.markdown(f"🔢 Total detectados: **{len(objetos_detectados)}**")

            # === LIMPIEZA DE OBJETOS ===
            st.markdown("### ✂️ Limpieza de objetos detectados")
            objetos_utiles = st.multiselect(
                "❓ ¿Cuáles objetos querés conservar para organizar?",
                objetos_detectados,
                default=objetos_detectados
            )

            if len(objetos_utiles) == 0:
                st.warning("Tenés que conservar al menos un objeto.")
                st.stop()

            # === ORDEN PERSONALIZADO ===
            st.markdown("### 📋 Ahora seleccioná el orden en que los vas a organizar")
            orden_seleccionado = st.multiselect(
                "🔢 Orden de organización",
                opciones := objetos_utiles,
                default=objetos_utiles,
                key="orden"
            )

            if len(orden_seleccionado) != len(objetos_utiles):
                st.warning("Seleccioná todos los objetos en el orden deseado.")
                st.stop()

            # === MÓDULO INTERACTIVO DE ORGANIZACIÓN ===
            st.divider()
            st.markdown("### 🛠️ Organización guiada paso a paso")

            paso = st.session_state.get("paso_actual", 0)
            if paso < len(orden_seleccionado):
                objeto_actual = orden_seleccionado[paso]
                st.markdown(f"### 👉 Objeto {paso+1}/{len(orden_seleccionado)}: **{objeto_actual}**")

                if f"inicio_{objeto_actual}" not in st.session_state:
                    st.session_state[f"inicio_{objeto_actual}"] = None

                if st.session_state[f"inicio_{objeto_actual}"] is None:
                    if st.button("⏱️ Iniciar organización"):
                        st.session_state[f"inicio_{objeto_actual}"] = time.time()
                else:
                    tiempo = int(time.time() - st.session_state[f"inicio_{objeto_actual}"])
                    st.write(f"🕒 Tiempo transcurrido: {tiempo} segundos")

                    lugar = st.text_input(f"📍 ¿Dónde quedará '{objeto_actual}' permanentemente?")
                    if lugar:
                        if st.button("✅ Registrar y pasar al siguiente"):
                            doc = {
                                "usuario": username,
                                "fecha": datetime.utcnow(),
                                "objeto": objeto_actual,
                                "orden": paso + 1,
                                "lugar_asignado": lugar,
                                "tiempo_organizacion_segundos": tiempo,
                                "nombre_imagen": uploaded_file.name
                            }
                            col.insert_one(doc)
                            st.success(f"📦 Objeto '{objeto_actual}' registrado con éxito.")
                            st.session_state[f"inicio_{objeto_actual}"] = None
                            st.session_state["paso_actual"] = paso + 1
                            st.rerun()
            else:
                st.balloons()
                st.success("🎉 Todos los objetos fueron organizados.")
        except Exception as e:
            st.error(f"❌ Error al analizar la imagen: {str(e)}")