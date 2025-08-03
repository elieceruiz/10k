import streamlit as st
import openai
import base64
from datetime import datetime
import time
from pymongo import MongoClient

# === CONFIG APP ===
st.set_page_config(page_title="🧠 Proyecto 10K – Orden Manual", layout="centered")
st.title("📸 Proyecto 10K – Organización guiada sin intervención")

# === SECRETS ===
openai.api_key = st.secrets["openai_api_key"]
mongo_uri = st.secrets["mongo_uri"]

# === CONEXIÓN MONGO ===
client = MongoClient(mongo_uri)
db = client["proyecto10k"]
col = db["organizacion_guiada"]

# === CARGA DE IMAGEN ===
uploaded_file = st.file_uploader("📤 Sube una imagen del entorno", type=["jpg", "jpeg", "png"])

# === NOMBRE USUARIO ===
username = st.text_input("🧍 Tu nombre:", "eliecer")

if uploaded_file:
    st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)
    bytes_data = uploaded_file.read()
    encoded_image = base64.b64encode(bytes_data).decode("utf-8")
    image_url = f"data:image/jpeg;base64,{encoded_image}"

    # === GPT-4o DETECCIÓN UNA VEZ ===
    if "objetos_detectados" not in st.session_state:
        with st.spinner("🔍 Detectando objetos en la imagen..."):
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
            texto = response.choices[0].message.content.strip()
            st.session_state.objetos_detectados = [o.strip() for o in texto.split(",") if o.strip()]
            st.session_state.objetos_seleccionados = {}
            st.session_state.orden_total = len(st.session_state.objetos_detectados)
            st.session_state.imagen_codificada = encoded_image

    objetos = st.session_state.objetos_detectados

    st.subheader("✅ Selección manual de objetos a organizar")
    ordenes_disponibles = list(range(1, len(objetos) + 1))

    for obj in objetos:
        col1, col2 = st.columns([3, 1])
        with col1:
            check = st.checkbox(f"{obj}", key=f"check_{obj}")
        with col2:
            if check:
                orden = st.select_slider(
                    f"Orden:",
                    options=ordenes_disponibles,
                    key=f"orden_{obj}"
                )
                st.session_state.objetos_seleccionados[obj] = orden
            else:
                st.session_state.objetos_seleccionados.pop(obj, None)

    if len(st.session_state.objetos_seleccionados) > 0:
        st.divider()
        st.subheader("🛠️ Organización paso a paso")

        # Ordenamos los objetos según número asignado
        lista_ordenada = sorted(
            st.session_state.objetos_seleccionados.items(),
            key=lambda x: x[1]
        )

        paso = st.session_state.get("paso_actual", 0)

        if paso < len(lista_ordenada):
            objeto_actual, orden_actual = lista_ordenada[paso]
            st.markdown(f"### 👉 Objeto {orden_actual}: **{objeto_actual}**")

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
                        col.insert_one({
                            "usuario": username,
                            "fecha": datetime.utcnow(),
                            "objeto": objeto_actual,
                            "orden": orden_actual,
                            "lugar_asignado": lugar,
                            "tiempo_organizacion_segundos": tiempo,
                            "nombre_imagen": uploaded_file.name,
                            "imagen_base64": st.session_state.imagen_codificada
                        })
                        st.success(f"📦 '{objeto_actual}' registrado.")
                        st.session_state[f"inicio_{objeto_actual}"] = None
                        st.session_state["paso_actual"] = paso + 1
                        st.rerun()
        else:
            st.balloons()
            st.success("🎉 Todos los objetos fueron organizados.")

    else:
        st.info("Seleccioná al menos un objeto para continuar.")

    # === REINICIAR SESIÓN COMPLETA ===
    st.divider()
    if st.button("🔄 Reiniciar todo"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()