import streamlit as st
import time
import requests
from io import BytesIO

def render_result_column(uploaded_image, config, service):
    """
    - 仅在点击 Generate Recognition 时才发送到后端
    - UI 仅包含：一行状态消息（在进度条上方）、进度条、以及错误消息（在进度条下方，正常不显示）
    - 进度由三段组成：detector / extractor / reader 各占 1/3
    - 完成后通过 /api/send/<file_id> 获取并展示图片
    """
    st.subheader("Result")

    if uploaded_image is None:
        st.info("Please upload an image before generating results.")
        return

    if st.button("Generate Recognition"):
        models = config.get("models", {}) or {}
        options = config.get("options", {}) or {}
        final_config = service.build_config(
            plate_model=models.get("plate_model"),
            number_model=models.get("number_model"),
            **options
        )

        status_msg = st.empty()
        progress = st.progress(0)
        error_box = st.empty()

        status_msg.info("Submitting job to backend...")
        error_box.empty()

        try:
            resp = service.process_image(uploaded_image, config=final_config)
        except Exception as e:
            status_msg.error("Submission failed")
            error_box.error(f"{e}")
            progress.progress(100)
            return

        file_id = None
        job_id = None
        task_url = None
        if isinstance(resp, dict):
            file_id = resp.get("file_id") or resp.get("id")
            job_id = resp.get("job_id")
            task_url = resp.get("task_url")
            if task_url and task_url.startswith("/"):
                backend_base = (final_config.get("backend_url") or final_config.get("api_url") or "http://localhost:5000").rstrip("/")
                task_url = backend_base + task_url

        def steps_percent(steps_dict):
            step_order = ["detector", "extractor", "reader"]
            if not isinstance(steps_dict, dict):
                return 0
            completed = sum(1 for s in step_order if steps_dict.get(s, {}).get("status") == "ok")
            # 每步各占 1/3
            return int((completed / len(step_order)) * 100)

        backend_base = (final_config.get("backend_url") or final_config.get("api_url") or "http://localhost:5000").rstrip("/")
        send_url = f"{backend_base}/api/send/{file_id}" if file_id else None

        # Poll task endpoint if available
        if task_url or job_id:
            status_msg.info("Job accepted, waiting for backend processing...")
            poll_url = task_url if task_url else f"{backend_base}/api/tasks/{job_id}"

            if not poll_url:
                status_msg.error("No poll URL available for backend job.")
                error_box.error("Cannot poll backend task (missing URL).")
                progress.progress(100)
                return

            max_attempts = 120
            delay = 1.0
            for attempt in range(1, max_attempts + 1):
                try:
                    r = requests.get(poll_url, timeout=6)
                except Exception:
                    status_msg.info(f"Waiting for task status... ({attempt}/{max_attempts})")
                    time.sleep(delay)
                    continue

                content_type = r.headers.get("content-type", "")
                j = None
                if "application/json" in content_type:
                    try:
                        j = r.json()
                    except Exception:
                        j = None

                if isinstance(j, dict):
                    # 更新进度
                    pct = steps_percent(j.get("steps", {}))
                    progress.progress(pct)
                    if j.get("status") == "done" or j.get("status") == "ok":
                        progress.progress(100)
                        status_msg.success("Processing complete")
                        # try fetch and display image
                        if file_id:
                            try:
                                rr = requests.get(f"{backend_base}/api/send/{file_id}", timeout=10)
                                ctype = rr.headers.get("content-type", "")
                                if rr.status_code == 200 and ctype.startswith("image/"):
                                    status_msg.info("Displaying result image")
                                    st.image(BytesIO(rr.content))
                                    return
                                else:
                                    # maybe send returned json error
                                    try:
                                        jj = rr.json()
                                        error_box.error(str(jj))
                                    except Exception:
                                        error_box.error("Processing finished but no image was returned.")
                                    return
                            except Exception as e:
                                error_box.error(f"Failed to fetch result image: {e}")
                                return
                        return

                    if j.get("status") in ("pending", "processing", "accepted"):
                        status_msg.info(f"Backend processing... ({attempt}/{max_attempts})")
                        time.sleep(delay)
                        continue

                # fallback wait
                time.sleep(delay)

            status_msg.error("Timed out waiting for backend task to finish.")
            error_box.error("Task did not finish in time. Please try again later.")
            progress.progress(100)
            return

        # If only file_id present (no job_id/task), poll /api/send/<file_id>
        if file_id:
            status_msg.info("Submitted, waiting for processing result...")
            max_attempts = 120
            delay = 1.0
            for attempt in range(1, max_attempts + 1):
                try:
                    r = requests.get(f"{backend_base}/api/send/{file_id}", timeout=8)
                except Exception:
                    status_msg.info(f"Waiting for result... ({attempt}/{max_attempts})")
                    time.sleep(delay)
                    continue

                content_type = r.headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        j = r.json()
                    except Exception:
                        j = None
                    if isinstance(j, dict):
                        if j.get("status") in ("pending", "processing"):
                            pct = steps_percent(j.get("steps", {}))
                            progress.progress(pct)
                            status_msg.info(f"Backend processing... ({attempt}/{max_attempts})")
                            time.sleep(delay)
                            continue
                        if j.get("status") in ("done", "ok"):
                            progress.progress(100)
                            status_msg.success("Processing complete")
                            # try to fetch image once more (api/send may now return image)
                            try:
                                rr = requests.get(f"{backend_base}/api/send/{file_id}", timeout=10)
                                ctype = rr.headers.get("content-type", "")
                                if rr.status_code == 200 and ctype.startswith("image/"):
                                    st.image(BytesIO(rr.content))
                                    return
                                else:
                                    error_box.error("Processing finished but no image available.")
                                    return
                            except Exception as e:
                                error_box.error(f"Failed to fetch result image: {e}")
                                return
                        status_msg.error("Processing failed")
                        error_box.error(str(j))
                        progress.progress(100)
                        return
                else:
                    # Direct image returned
                    if r.status_code == 200 and content_type.startswith("image/"):
                        progress.progress(100)
                        status_msg.success("Processing complete")
                        st.image(BytesIO(r.content))
                        return
                    else:
                        # unexpected non-json, non-image
                        status_msg.error("Unexpected response from backend")
                        error_box.error(f"Status {r.status_code}")
                        progress.progress(100)
                        return

                time.sleep(delay)

            status_msg.error("Timed out waiting for backend result.")
            error_box.error("Processing did not complete in time. Please try again later.")
            progress.progress(100)
            return

        # Fallback: resp indicates immediate success
        if isinstance(resp, dict) and resp.get("status") in ("ok", "done"):
            progress.progress(100)
            status_msg.success("Processing complete")
            # try fetch image if file_id present
            if file_id:
                try:
                    rr = requests.get(f"{backend_base}/api/send/{file_id}", timeout=10)
                    if rr.status_code == 200 and rr.headers.get("content-type","").startswith("image/"):
                        st.image(BytesIO(rr.content))
                except Exception:
                    pass
            return

        status_msg.error("Unexpected backend response")
        error_box.error(str(resp))
        progress.progress(100)
        return

    st.info("Upload an image and click 'Generate Recognition' to start processing.")
