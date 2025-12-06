export interface UploadResponse {
  message: string;
  filename: string;
  original_filename: string;
  size: number;
  path: string;
}

export interface UploadError {
  detail: string;
}

export type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

export interface FileValidation {
  isValid: boolean;
  error?: string;
}
