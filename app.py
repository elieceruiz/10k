import streamlit as st
import openai
import base64
from datetime import datetime
import time
from pymongo import MongoClient
import pandas as pd

# === CONFIG APP ===
st.set_page_config(page_title="🧠 Proyecto 10K", layout="centered")

# === SECRETS ===
openai.api_key = st.secrets["openai_api_key"]
mongo_uri = st.secrets["mongo_uri"]

# === CONEXIÓN MONGO ===
client = MongoClient(mongo_uri)
db = client["proyecto10k"]
col = db["organizacion_guiada"]

# === TABS ===
tab1, tab2 = st.tabs(["📸 Organizar", "📜 Historial"])

with tab1:
    st.title("📸 Proyecto 10K – Organización paso a paso")

    uploaded_file = st.file_uploader("Subí una imagen del entorno", type=["jpg", "jpeg", "png"])

    if uploaded_file:
        st.image(uploaded_file, caption="Imagen cargada", use_container_width=True)
        bytes_data = uploaded_file.read()
        encoded_image = base64.b64encode(bytes_data).decode("utf-8")
        image_url = f"data:image/jpeg;base64,{encoded_image}"

        if "objetos_detectados" not in st.session_state:
            with st.spinner("🔍 Detectando objetos en la imagen..."):
                response = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "system", "content": "Listá objetos visibles, separados por comas. No describas."},
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
                st.session_state.orden_contador = 1
                st.session_state.imagen_codificada = encoded_image
                st.session_state.imagen_nombre = uploaded_file.name

        st.subheader("✅ Selección y orden automático")

        objetos = st.session_state.objetos_detectados

        for obj in objetos:
            key_check = f"check_{obj}"
            key_orden = f"orden_{obj}"

            prev_checked = st.session_state.objetos_seleccionados.get(obj, {}).get("checked", False)
            checked = st.checkbox(f"{obj}", key=key_check, value=prev_checked)

            if checked and not prev_checked:
                st.session_state.objetos_seleccionados[obj] = {
                    "orden": st.session_state.orden_contador,
                    "checked": True
                }
                st.session_state.orden_contador += 1

            elif not checked and prev_checked:
                del st.session_state.objetos_seleccionados[obj]
                # Reordenar los que siguen
                nuevos_ordenes = {}
                nuevo_contador = 1
                for k in sorted(st.session_state.objetos_seleccionados, key=lambda x: st.session_state.objetos_seleccionados[x]["orden"]):
                    nuevos_ordenes[k] = {
                        "orden": nuevo_contador,
                        "checked": True
                    }
                    nuevo_contador += 1
                st.session_state.objetos_seleccionados = nuevos_ordenes
                st.session_state.orden_contador = nuevo_contador

            if checked:
                st.markdown(f"🔢 Orden en esta sesión: **{st.session_state.objetos_seleccionados[obj]['orden']}**")

        seleccionados = st.session_state.objetos_seleccionados

        if seleccionados:
            st.divider()
            st.subheader("🛠️ Organización guiada")

            lista_ordenada = sorted(seleccionados.items(), key=lambda x: x[1]["orden"])
            paso = st.session_state.get("paso_actual", 0)

            if paso < len(lista_ordenada):
                objeto_actual, data = lista_ordenada[paso]
                orden_actual = data["orden"]
                st.markdown(f"### 👉 Objeto {orden_actual}: **{objeto_actual}**")

                if f"inicio_{objeto_actual}" not in st.session_state:
                    st.session_state[f"inicio_{objeto_actual}"] = None

                if st.session_state[f"inicio_{objeto_actual}"] is None:
                    if st.button("⏱️ Iniciar organización"):
                        st.session_state[f"inicio_{objeto_actual}"] = time.time()
                else:
                    tiempo = int(time.time() - st.session_state[f"inicio_{objeto_actual}"])
                    st.write(f"🕒 Tiempo transcurrido: {tiempo} segundos")

                    lugar = st.text_input(f"📍 ¿Dónde quedará '{objeto_actual}'?")
                    if lugar:
                        if st.button("✅ Registrar y pasar al siguiente"):
                            col.insert_one({
                                "fecha": datetime.utcnow(),
                                "objeto": objeto_actual,
                                "orden": orden_actual,
                                "lugar_asignado": lugar,
                                "tiempo_organizacion_segundos": tiempo,
                                "nombre_imagen": st.session_state.imagen_nombre,
                                "imagen_base64": st.session_state.imagen_codificada
                            })
                            st.success(f"📦 '{objeto_actual}' registrado.")
                            st.session_state[f"inicio_{objeto_actual}"] = None
                            st.session_state["paso_actual"] = paso + 1
                            st.rerun()
            else:
                st.balloons()
                st.success("🎉 Todos los objetos fueron organizados.")

        # === RESET ===
        st.divider()
        if st.button("🔄 Reiniciar todo"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

with tab2:
    st.title("📜 Historial de organización")

    docs = list(col.find().sort("fecha", -1))
    if docs:
        df = pd.DataFrame(docs)
        df = df[["fecha", "objeto", "orden", "lugar_asignado", "tiempo_organizacion_segundos", "nombre_imagen"]]
        df["fecha"] = df["fecha"].dt.strftime("%Y-%m-%d %H:%M")
        df = df.rename(columns={
            "fecha": "Fecha",
            "objeto": "Objeto",
            "orden": "Orden",
            "lugar_asignado": "Lugar",
            "tiempo_organizacion_segundos": "Tiempo (s)",
            "nombre_imagen": "Imagen"
        })
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Aún no hay registros.")