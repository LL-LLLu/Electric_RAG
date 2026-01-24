import streamlit as st
import requests
import os

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Documents", page_icon="", layout="wide")

st.title("Documents")

try:
    response = requests.get(f"{BACKEND_URL}/api/documents/", timeout=10)

    if response.status_code == 200:
        documents = response.json()

        if not documents:
            st.info("No documents uploaded yet. Go to Upload page to add documents.")
        else:
            for doc in documents:
                with st.expander(f"{doc.get('original_filename', doc['filename'])}"):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.markdown(f"**Filename:** {doc['filename']}")
                        st.markdown(f"**Pages:** {doc.get('page_count', 'N/A')}")

                    with col2:
                        status = doc.get('processed', 0)
                        status_map = {0: "Pending", 1: "Processing", 2: "Ready", -1: "Error"}
                        st.markdown(f"**Status:** {status_map.get(status, 'Unknown')}")
                        if doc.get('upload_date'):
                            st.markdown(f"**Uploaded:** {doc['upload_date'][:10]}")

                    with col3:
                        if doc.get('system'):
                            st.markdown(f"**System:** {doc['system']}")
                        if doc.get('area'):
                            st.markdown(f"**Area:** {doc['area']}")

                    if st.button("View Details", key=f"doc_details_{doc['id']}"):
                        detail_response = requests.get(f"{BACKEND_URL}/api/documents/{doc['id']}", timeout=10)
                        if detail_response.status_code == 200:
                            detail = detail_response.json()
                            st.markdown(f"**Equipment found:** {detail.get('equipment_count', 0)}")

                            if detail.get('pages'):
                                st.markdown("**Pages:**")
                                for page in detail['pages']:
                                    st.write(f"- Page {page['page_number']}: {page.get('equipment_count', 0)} equipment")

except requests.exceptions.ConnectionError:
    st.error("Could not connect to backend.")
except Exception as e:
    st.error(f"Error: {str(e)}")
