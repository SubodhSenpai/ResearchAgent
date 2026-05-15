'use client';

import { useState, useEffect, useRef } from 'react';
import { uploadDocument, listDocuments, deleteDocument } from '@/lib/api';

export default function DocumentManager({ isOpen, onClose }) {
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(true);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const fileInputRef = useRef(null);
  const dragOverRef = useRef(false);

  useEffect(() => {
    if (isOpen) {
      loadDocuments();
    }
  }, [isOpen]);

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const data = await listDocuments();
      setDocuments(data.documents || []);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = async (file) => {
    if (!file) return;

    const allowedTypes = ['application/pdf', 'text/markdown', 'text/plain'];
    const allowedExtensions = ['.pdf', '.md', '.markdown', '.txt'];

    const hasValidType = allowedTypes.includes(file.type);
    const hasValidExt = allowedExtensions.some(ext => file.name.toLowerCase().endsWith(ext));

    if (!hasValidType && !hasValidExt) {
      setError('Only PDF, Markdown, and text files are supported');
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setError('File size must be less than 50MB');
      return;
    }

    setUploading(true);
    setError('');
    setSuccess('');

    try {
      const result = await uploadDocument(file);
      setSuccess(result.message);
      setDocuments(prev => [
        ...prev,
        {
          document_id: result.document_id,
          filename: result.filename,
          pageindex_doc_id: result.pageindex_doc_id,
          status: result.status,
          created_at: new Date().toISOString(),
        }
      ]);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteConfirm) return;
    try {
      await deleteDocument(deleteConfirm);
      setDocuments(prev => prev.filter(d => d.document_id !== deleteConfirm));
      setSuccess('Document deleted successfully');
      setDeleteConfirm(null);
    } catch (err) {
      setError(err.message);
    }
  };

  const formatDate = (iso) => {
    const d = new Date(iso);
    const now = new Date();
    const diff = now - d;
    if (diff < 60000) return 'Just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    dragOverRef.current = true;
  };

  const handleDragLeave = () => {
    dragOverRef.current = false;
  };

  const handleDrop = (e) => {
    e.preventDefault();
    dragOverRef.current = false;
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-bg-primary border border-border-subtle rounded-2xl w-full max-w-2xl max-h-[85vh] overflow-hidden flex flex-col shadow-2xl animate-fadeIn">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-border-subtle flex-shrink-0">
          <div>
            <h2 className="text-lg font-semibold text-text-primary">Knowledge Base</h2>
            <p className="text-sm text-text-secondary mt-0.5">Upload and manage your documents</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg text-text-secondary hover:text-text-primary hover:bg-bg-glass-hover transition-all cursor-pointer"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {/* Upload Section */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-text-primary mb-3">Upload Document</label>
            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all ${
                dragOverRef.current
                  ? 'border-accent bg-accent/5'
                  : 'border-border-subtle hover:border-accent/50 hover:bg-bg-glass-hover'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                onChange={(e) => handleFileSelect(e.target.files?.[0])}
                accept=".pdf,.md,.markdown,.txt"
                className="hidden"
                disabled={uploading}
              />
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mx-auto mb-3 text-accent/60">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
              <p className="text-sm font-medium text-text-primary">
                {uploading ? 'Uploading...' : 'Drop your file here or click to browse'}
              </p>
              <p className="text-xs text-text-secondary mt-1">
                PDF, Markdown, or text files (max 50MB)
              </p>
            </div>
          </div>

          {/* Messages */}
          {error && (
            <div className="mb-4 p-3 bg-danger-bg border border-danger/20 rounded-lg text-danger text-sm flex items-start gap-2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mt-0.5 flex-shrink-0">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="mb-4 p-3 bg-success-bg border border-success/20 rounded-lg text-success text-sm flex items-start gap-2">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="mt-0.5 flex-shrink-0">
                <polyline points="20 6 9 17 4 12" />
              </svg>
              <span>{success}</span>
            </div>
          )}

          {/* Documents List */}
          <div>
            <h3 className="text-sm font-medium text-text-primary mb-3">Your Documents</h3>
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-12 rounded-lg bg-gradient-to-r from-bg-glass via-bg-glass-hover to-bg-glass bg-[length:200%_100%] animate-[shimmer_1.5s_ease-in-out_infinite]" />
                ))}
              </div>
            ) : documents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-text-muted">
                <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-3 opacity-50">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                <p className="text-sm">No documents uploaded yet</p>
              </div>
            ) : (
              <div className="space-y-2">
                {documents.map(doc => (
                  <div key={doc.document_id} className="flex items-center justify-between p-3 bg-bg-glass border border-border-subtle rounded-lg hover:bg-bg-glass-hover transition-colors group">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 flex items-center justify-center rounded bg-accent/10 text-accent flex-shrink-0">
                        {doc.filename.endsWith('.pdf') ? (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M7 3h10l4 4v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z" /></svg>
                        ) : (
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /></svg>
                        )}
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-text-primary truncate">{doc.filename}</p>
                        <p className="text-xs text-text-muted">{formatDate(doc.created_at)}</p>
                      </div>
                    </div>
                    <button
                      onClick={() => setDeleteConfirm(doc.document_id)}
                      className="opacity-0 group-hover:opacity-100 p-2 rounded text-text-muted hover:text-danger hover:bg-danger-bg/20 transition-all flex-shrink-0 cursor-pointer"
                      title="Delete document"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Delete Confirmation Modal */}
        {deleteConfirm && (
          <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-bg-primary border border-border-subtle rounded-xl p-5 w-full max-w-sm shadow-2xl">
              <h3 className="font-semibold text-text-primary mb-2">Delete Document?</h3>
              <p className="text-sm text-text-secondary mb-4">This action cannot be undone.</p>
              <div className="flex gap-3">
                <button
                  onClick={() => setDeleteConfirm(null)}
                  className="flex-1 py-2 px-4 bg-bg-glass border border-border-subtle rounded-lg text-text-primary hover:bg-bg-glass-hover transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDelete}
                  className="flex-1 py-2 px-4 bg-danger text-white rounded-lg hover:bg-danger/90 transition-all cursor-pointer font-medium"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
