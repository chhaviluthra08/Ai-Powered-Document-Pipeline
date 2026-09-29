import streamlit as st
import sqlite3
import pandas as pd
import json
import base64
import os
from datetime import datetime, timezone
from dotenv import load_dotenv
from storage import get_connection, log_correction, log_audit, update_document, delete_document
from pipeline import process_document
from retrieval import add_example

load_dotenv()
st.set_page_config(page_title="AI Document Processing Platform", layout="wide")

def load_queue():
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT r.id as queue_id, r.document_id, r.reason, d.filename, r.added_at FROM review_queue r JOIN documents d ON r.document_id = d.id WHERE r.status = 'pending'",
            conn
        )

def load_completed_documents():
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT id, filename, status, document_type, confidence_score, ingestion_time FROM documents WHERE status = 'completed' ORDER BY ingestion_time DESC",
            conn
        )

def load_all_documents():
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT id, filename, status, document_type, confidence_score, ingestion_time FROM documents ORDER BY ingestion_time DESC",
            conn
        )

def load_extractions(doc_id):
    with get_connection() as conn:
        return pd.read_sql_query("SELECT field_name, extracted_value, confidence, is_valid FROM extractions WHERE document_id = ?", conn, params=(doc_id,))

def resolve_review(queue_id, doc_id, original_df, new_values):
    with get_connection() as conn:
        for idx, row in original_df.iterrows():
            field = row['field_name']
            orig_val = row['extracted_value']
            new_val = new_values.get(field)
            
            if str(orig_val) != str(new_val):
                log_correction(doc_id, field, str(orig_val), str(new_val), 'human')
                conn.execute(
                    "UPDATE extractions SET extracted_value = ?, confidence = 100, is_valid = 1 WHERE field_name = ? AND document_id = ?",
                    (str(new_val), field, doc_id)
                )
        
        conn.execute("UPDATE review_queue SET status = 'resolved' WHERE id = ?", (queue_id,))
        
    update_document(doc_id, status='completed')
    log_audit(doc_id, 'Review', 'Document reviewed and approved by human')

    try:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT raw_text, document_type FROM documents WHERE id = ?", (doc_id,))
            doc_res = cur.fetchone()

        if doc_res:
            raw_text, document_type = doc_res
            if raw_text and document_type:
                final_extractions_df = load_extractions(doc_id)
                final_extraction_dict = {}
                for _, row in final_extractions_df.iterrows():
                    fname = row['field_name']
                    val = row['extracted_value']
                    if fname == 'line_items' and isinstance(val, str):
                        try:
                            val = json.loads(val)
                        except Exception:
                            pass
                    conf = int(row['confidence']) if pd.notnull(row['confidence']) else 100
                    final_extraction_dict[fname] = {"value": val, "confidence_score": conf}

                add_example(document_type, raw_text, final_extraction_dict, doc_id)
    except Exception as e:
        print(f"Warning: failed to add example to RAG: {e}")

    st.success("Document approved and saved!")
    st.rerun()

def render_document_preview(doc_id):
    st.subheader("Document Preview")
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT file_path, raw_text FROM documents WHERE id = ?", (doc_id,))
        res = cur.fetchone()
        if res:
            file_path, raw_text = res
            try:
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                    st.image(file_path, use_container_width=True)
                elif file_path.lower().endswith('.pdf'):
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
                        st.markdown(pdf_display, unsafe_allow_html=True)
                    else:
                        st.warning(f"File not found on disk: {file_path}")
                        st.text_area("Raw Extracted Text", raw_text or "", height=600)
                else:
                    st.text_area("Raw Extracted Text", raw_text or "", height=600)
            except Exception as e:
                st.error(f"Could not load preview: {e}")
                st.text_area("Raw Extracted Text Fallback", raw_text or "", height=600)
        else:
            st.error("Document not found in DB.")

# Header
st.title("AI Document Processing Platform")

# Fetch data for live counts
queue_df = load_queue()
completed_df = load_completed_documents()
all_docs_df = load_all_documents()

# Tab setup
tab1, tab2, tab3 = st.tabs([
    f"Needs Review ({len(queue_df)})",
    f"Processed ({len(completed_df)})",
    f"Upload & Manage ({len(all_docs_df)})"
])

# ==========================================
# TAB 1: NEEDS REVIEW
# ==========================================
with tab1:
    if queue_df.empty:
        st.info("The review queue is currently empty. Great job!")
    else:
        st.sidebar.header("Pending Documents")
        doc_options = queue_df.apply(lambda x: f"{x['filename']} (ID: {x['document_id'][:8]})", axis=1).tolist()
        selected_option = st.sidebar.selectbox("Select a document to review", doc_options, key="queue_selectbox")
        
        selected_idx = doc_options.index(selected_option)
        selected_row = queue_df.iloc[selected_idx]
        
        doc_id = selected_row['document_id']
        queue_id = selected_row['queue_id']
        filename = selected_row['filename']
        reason = selected_row['reason']
        
        st.header(f"Reviewing: {filename}")
        st.warning(f"Flagged reason: {reason}")
        
        if st.button("Reprocess Document"):
            with st.spinner("Reprocessing document through pipeline..."):
                try:
                    with get_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("SELECT file_path FROM documents WHERE id = ?", (doc_id,))
                        res = cur.fetchone()
                    
                    if res and res[0] and os.path.exists(res[0]):
                        file_path = res[0]
                        process_document(file_path, metadata={"reprocessed": True}, force=True)
                        with get_connection() as conn:
                            conn.execute("UPDATE review_queue SET status = 'resolved' WHERE id = ?", (queue_id,))
                        st.success("Document reprocessed and review queue item marked as resolved!")
                        st.rerun()
                    else:
                        st.error(f"File not found on disk at: {res[0] if res else 'Unknown'}")
                except Exception as e:
                    st.error(f"Reprocessing error: {e}")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            render_document_preview(doc_id)

        with col2:
            st.subheader("Extracted Data")
            extractions_df = load_extractions(doc_id)
            
            with st.form("review_form"):
                new_values = {}
                for idx, row in extractions_df.iterrows():
                    field = row['field_name']
                    val = row['extracted_value']
                    conf = row['confidence']
                    
                    label = f"{field} (Confidence: {conf}%)"
                    if conf < 85:
                        label = "[Low Confidence] " + label
                        
                    new_values[field] = st.text_input(label, value=str(val) if val is not None else "", key=f"field_{field}_{doc_id}")
                    
                submitted = st.form_submit_button("Approve & Save")
                if submitted:
                    resolve_review(queue_id, doc_id, extractions_df, new_values)

# ==========================================
# TAB 2: PROCESSED
# ==========================================
with tab2:
    st.header("Completed / Processed Documents")
    if completed_df.empty:
        st.info("No completed documents yet.")
    else:
        st.dataframe(completed_df, use_container_width=True)
        st.markdown("---")
        
        proc_options = completed_df.apply(
            lambda r: f"{r['filename']} (ID: {r['id'][:8]}) - {r['document_type'] or 'Unclassified'}", axis=1
        ).tolist()
        
        selected_proc_str = st.selectbox("Select a processed document to view details", proc_options, key="proc_select")
        selected_proc_idx = proc_options.index(selected_proc_str)
        proc_doc_row = completed_df.iloc[selected_proc_idx]
        proc_doc_id = proc_doc_row['id']
        
        col1, col2 = st.columns([1, 1])
        with col1:
            render_document_preview(proc_doc_id)
            
        with col2:
            st.subheader("Read-only Extracted Data")
            proc_extractions = load_extractions(proc_doc_id)
            if proc_extractions.empty:
                st.info("No extraction fields found for this document.")
            else:
                st.dataframe(
                    proc_extractions[['field_name', 'extracted_value', 'confidence', 'is_valid']],
                    use_container_width=True
                )

# ==========================================
# TAB 3: UPLOAD & MANAGE
# ==========================================
with tab3:
    st.header("Upload New Documents")
    uploaded_files = st.file_uploader(
        "Select documents to upload and process",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        if st.button("Process Uploaded Files"):
            input_dir = "input_docs"
            os.makedirs(input_dir, exist_ok=True)
            
            for file_obj in uploaded_files:
                save_path = os.path.join(input_dir, file_obj.name)
                with open(save_path, "wb") as f:
                    f.write(file_obj.getbuffer())
                
                metadata = {
                    "sender": "web_upload@system.local",
                    "subject": f"Web Upload: {file_obj.name}",
                    "received_date": datetime.now(timezone.utc).isoformat()
                }
                
                with st.spinner(f"Processing {file_obj.name}..."):
                    try:
                        process_document(save_path, metadata)
                        
                        # Query database for final status
                        with get_connection() as conn:
                            cur = conn.cursor()
                            cur.execute(
                                "SELECT id, status FROM documents WHERE file_path = ? ORDER BY ingestion_time DESC LIMIT 1",
                                (save_path,)
                            )
                            doc_res = cur.fetchone()
                            
                            if doc_res:
                                doc_id_res, status_res = doc_res
                                if status_res == 'completed':
                                    st.success(f"Completed: **{file_obj.name}** - Processing completed successfully!")
                                elif status_res == 'review_required':
                                    cur.execute(
                                        "SELECT reason FROM review_queue WHERE document_id = ? ORDER BY id DESC LIMIT 1",
                                        (doc_id_res,)
                                    )
                                    q_res = cur.fetchone()
                                    reason_txt = q_res[0] if q_res else "Low confidence fields"
                                    st.warning(f"Routed to review: **{file_obj.name}** ({reason_txt})")
                                else:
                                    st.info(f"Status: **{file_obj.name}** - {status_res}")
                    except Exception as e:
                        st.error(f"Error processing {file_obj.name}: {e}")

    st.markdown("---")
    st.header("Manage Documents")
    
    if all_docs_df.empty:
        st.info("No documents found in the database.")
    else:
        st.dataframe(all_docs_df, use_container_width=True)
        
        st.subheader("Delete Document")
        doc_select_options = all_docs_df.apply(
            lambda r: f"{r['filename']} (ID: {r['id'][:8]}) - {r['status']}", axis=1
        ).tolist()
        
        selected_doc_str = st.selectbox("Select document to delete", doc_select_options, key="del_select")
        confirm_del = st.checkbox("Confirm deletion of selected document, its database entries, and file from disk", key="del_confirm")
        
        if st.button("Delete Selected Document"):
            if not confirm_del:
                st.error("Please check the confirmation box before deleting.")
            else:
                selected_idx = doc_select_options.index(selected_doc_str)
                target_doc_id = all_docs_df.iloc[selected_idx]['id']
                delete_document(target_doc_id)
                st.success(f"Document '{selected_doc_str}' deleted successfully!")
                st.rerun()
