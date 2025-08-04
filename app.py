# === TAB MIGRACIÓN ADAPTADA ===
with tab_migracion:
    st.subheader("🧪 Captura con cámara + Modo Zen")

    col_zen = db["ubicaciones_zen"]

    # Inicializar estados
    for key in ["foto_cargada", "objetos_detectados", "orden_confirmado", "orden_final", "indice_actual", "cronometro_inicio", "tiempos_zen"]:
        if key not in st.session_state:
            st.session_state[key] = None if key not in ["objetos_detectados", "orden_final", "tiempos_zen"] else []

    # 1. Subida de imagen y análisis con GPT
    if st.session_state["foto_cargada"] is None:
        archivo = st.file_uploader("📷 Toca para tomar foto (cámara móvil)", type=["jpg", "jpeg", "png"], label_visibility="collapsed", key="foto_gpt4o")
        if archivo:
            st.session_state["foto_cargada"] = Image.open(archivo)
            imagen_reducida = reducir_imagen(st.session_state["foto_cargada"])
            st.session_state["imagen_b64"] = convertir_imagen_base64(imagen_reducida)
            st.rerun()

    elif st.session_state["foto_cargada"] and not st.session_state["objetos_detectados"]:
        st.image(st.session_state["foto_cargada"], caption="✅ Foto cargada", use_container_width=True)
        with st.spinner("🧠 Analizando con GPT-4o..."):
            try:
                b64_img = "data:image/jpeg;base64," + st.session_state["imagen_b64"]
                respuesta = openai.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role": "user", "content": [
                            {"type": "text", "text": "Detecta solo objetos visibles. Devuelve una lista clara, sin contexto extra."},
                            {"type": "image_url", "image_url": {"url": b64_img}}
                        ]}
                    ],
                    max_tokens=300
                )
                contenido = respuesta.choices[0].message.content
                objetos = [obj.strip("-• ").capitalize() for obj in contenido.split("\n") if obj.strip()]
                st.session_state["objetos_detectados"] = objetos
            except Exception as e:
                st.error(f"❌ Error en la detección: {e}")
                st.session_state["foto_cargada"] = None

    # 2. Selección ordenada de objetos
    if st.session_state["objetos_detectados"] and not st.session_state["orden_confirmado"]:
        seleccionados = st.session_state["orden_final"]
        st.markdown("### ✋ Toca los objetos que vas a ubicar, en orden:")
        cols = st.columns(3)
        for i, obj in enumerate(st.session_state["objetos_detectados"]):
            if obj not in seleccionados:
                with cols[i % 3]:
                    if st.button(obj):
                        seleccionados.append(obj)
                        st.rerun()

        if seleccionados:
            st.markdown("🧩 Orden seleccionado:")
            st.write([f"{i+1}. {x}" for i, x in enumerate(seleccionados)])

            if st.button("✅ Confirmar orden"):
                st.session_state["orden_confirmado"] = True
                st.session_state["indice_actual"] = 0
                st.rerun()

    # 3. Ejecución Modo Zen
    elif st.session_state["orden_confirmado"] and st.session_state["indice_actual"] is not None:
        tareas = st.session_state["orden_final"]
        idx = st.session_state["indice_actual"]

        if idx < len(tareas):
            actual = tareas[idx]
            st.header(f"📍 {idx+1}. Ubicar: **{actual}**")

            if st.session_state["cronometro_inicio"] is None:
                if st.button("🎯 Empezar tarea"):
                    st.session_state["cronometro_inicio"] = datetime.now(tz)
                    st.rerun()
            else:
                cronometro = st.empty()
                fin_button = st.button("✅ Terminé de ubicar")

                while True:
                    ahora = datetime.now(tz)
                    transcurrido = ahora - st.session_state["cronometro_inicio"]
                    cronometro.markdown(f"⏱️ Duración: `{str(transcurrido).split('.')[0]}`")
                    time.sleep(1)

                    if fin_button:
                        lugar = st.text_input("📝 ¿Dónde quedó ubicado?")
                        if lugar:
                            fin = datetime.now(tz)
                            st.session_state["tiempos_zen"].append({
                                "objeto": actual,
                                "inicio": st.session_state["cronometro_inicio"].isoformat(),
                                "fin": fin.isoformat(),
                                "duracion_segundos": (fin - st.session_state["cronometro_inicio"]).total_seconds(),
                                "ubicacion": lugar
                            })
                            st.session_state["indice_actual"] += 1
                            st.session_state["cronometro_inicio"] = None
                            st.rerun()
                        else:
                            st.warning("⚠️ Escribe dónde quedó ubicado el objeto.")
        else:
            st.success("🎉 ¡Todos los objetos fueron ubicados!")

            # Guardar todo
            col.insert_one({
                "timestamp": datetime.now(tz),
                "objetos": st.session_state["orden_final"],
                "imagen_b64": st.session_state["imagen_b64"],
                "tiempos_zen": st.session_state["tiempos_zen"],
                "fuente": "migracion_zen"
            })

            # Guardar ubicación por separado
            for t in st.session_state["tiempos_zen"]:
                col_zen.insert_one(t)

            # Reset
            for k in ["foto_cargada", "objetos_detectados", "orden_confirmado", "orden_final", "indice_actual", "cronometro_inicio", "tiempos_zen", "imagen_b64"]:
                st.session_state[k] = None if k not in ["orden_final", "tiempos_zen"] else []

            st.balloons()
            st.rerun()