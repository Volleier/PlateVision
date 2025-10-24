import streamlit as st

def render_input_column():
    """
    Render the image input area and return the uploaded image file (UploadedFile or None).
    - Keep only the image upload method (supports drag & drop), show preview and basic info.
    - Will set st.session_state['generate_disabled']: True when no image, False when an image is present.
    """
    st.subheader("Upload Image")

    uploaded_image = st.file_uploader(
        "Drag and drop an image here or click to select",
        type=['png', 'jpg', 'jpeg', 'bmp', 'gif'],
        accept_multiple_files=False,
        key="image_uploader"
    )

    if uploaded_image is not None:
        try:
            st.image(uploaded_image, caption=f"Uploaded: {uploaded_image.name}", width="stretch")
            st.success(f"Image uploaded successfully: {uploaded_image.name}, size: {uploaded_image.size} bytes")
        except Exception:
            st.warning("Unable to preview the image, but it was uploaded successfully.")

    if 'generate_disabled' not in st.session_state:
        st.session_state['generate_disabled'] = True
    st.session_state['generate_disabled'] = False if uploaded_image is not None else True

    return uploaded_image