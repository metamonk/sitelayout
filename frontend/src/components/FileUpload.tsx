'use client';

import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import type { FileValidation, UploadStatus } from '@/types/upload';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Progress } from '@/components/ui/progress';

interface FileUploadProps {
  onUploadSuccess?: (filename: string) => void;
  onUploadError?: (error: string) => void;
}

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
const ALLOWED_EXTENSIONS = ['.kmz', '.kml'];
const ALLOWED_MIME_TYPES = [
  'application/vnd.google-earth.kmz',
  'application/vnd.google-earth.kml+xml',
  'application/octet-stream',
];

export default function FileUpload({ onUploadSuccess, onUploadError }: FileUploadProps) {
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string>('');
  const [uploadedFilename, setUploadedFilename] = useState<string>('');

  const validateFile = useCallback((file: File): FileValidation => {
    // Check file extension
    const fileName = file.name.toLowerCase();
    const hasValidExtension = ALLOWED_EXTENSIONS.some((ext) => fileName.endsWith(ext));

    if (!hasValidExtension) {
      return {
        isValid: false,
        error: `Invalid file type. Please upload a KMZ or KML file.`,
      };
    }

    // Check file size
    if (file.size > MAX_FILE_SIZE) {
      return {
        isValid: false,
        error: `File too large. Maximum size is ${MAX_FILE_SIZE / (1024 * 1024)}MB.`,
      };
    }

    if (file.size === 0) {
      return {
        isValid: false,
        error: 'File is empty.',
      };
    }

    return { isValid: true };
  }, []);

  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      setValidationError('');
      setUploadStatus('idle');

      if (acceptedFiles.length === 0) {
        return;
      }

      const file = acceptedFiles[0];
      const validation = validateFile(file);

      if (!validation.isValid) {
        setValidationError(validation.error || 'Invalid file');
        setSelectedFile(null);
        return;
      }

      setSelectedFile(file);
    },
    [validateFile]
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.google-earth.kmz': ['.kmz'],
      'application/vnd.google-earth.kml+xml': ['.kml'],
    },
    maxFiles: 1,
    multiple: false,
  });

  const handleUpload = async () => {
    if (!selectedFile) return;

    try {
      setUploadStatus('uploading');
      setUploadProgress(0);

      // Dynamic import to avoid server-side issues
      const { uploadFile } = await import('@/lib/api');

      const response = await uploadFile(selectedFile, (progress) => {
        setUploadProgress(progress);
      });

      setUploadStatus('success');
      setUploadedFilename(response.filename);
      onUploadSuccess?.(response.filename);
    } catch (error: any) {
      setUploadStatus('error');
      const errorMessage = error.response?.data?.detail || error.message || 'Upload failed';
      setValidationError(errorMessage);
      onUploadError?.(errorMessage);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setUploadStatus('idle');
    setUploadProgress(0);
    setValidationError('');
    setUploadedFilename('');
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <Card>
        <CardHeader>
          <CardTitle>Upload Site File</CardTitle>
          <CardDescription>
            Upload your KMZ or KML file to begin site analysis
          </CardDescription>
        </CardHeader>
        <CardContent>
          {uploadStatus === 'success' ? (
            <div className="text-center py-8 space-y-4">
              <div className="h-16 w-16 rounded-full bg-green-100 flex items-center justify-center mx-auto">
                <svg
                  className="h-8 w-8 text-green-600"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
              <div>
                <h3 className="text-xl font-semibold mb-2">Upload Successful!</h3>
                <p className="text-muted-foreground">
                  File <span className="font-medium text-foreground">{uploadedFilename}</span> has been uploaded successfully.
                </p>
              </div>
              <Button onClick={handleReset} size="lg">
                Upload Another File
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <div
                {...getRootProps()}
                className={`
                  border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-all
                  ${isDragActive && !isDragReject ? 'border-primary bg-primary/5' : ''}
                  ${isDragReject ? 'border-destructive bg-destructive/5' : ''}
                  ${!isDragActive && !selectedFile ? 'border-muted-foreground/25 hover:border-primary/50 hover:bg-accent/50' : ''}
                  ${selectedFile ? 'border-green-500 bg-green-50/50' : ''}
                `}
              >
                <input {...getInputProps()} />

                <div className="flex flex-col items-center space-y-2">
                  {selectedFile ? (
                    <>
                      <div className="h-12 w-12 rounded-full bg-green-100 flex items-center justify-center">
                        <svg
                          className="h-6 w-6 text-green-600"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                          />
                        </svg>
                      </div>
                      <p className="text-lg font-medium">
                        {selectedFile.name}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </>
                  ) : (
                    <>
                      <div className="h-12 w-12 rounded-full bg-primary/10 flex items-center justify-center">
                        <svg
                          className="h-6 w-6 text-primary"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                          />
                        </svg>
                      </div>
                      {isDragActive ? (
                        <p className="text-lg font-medium text-primary">Drop your file here</p>
                      ) : (
                        <>
                          <p className="text-lg font-medium">
                            Drag and drop your KMZ/KML file here
                          </p>
                          <p className="text-sm text-muted-foreground">or click to browse</p>
                          <p className="text-xs text-muted-foreground">
                            Supported formats: KMZ, KML (max 50MB)
                          </p>
                        </>
                      )}
                    </>
                  )}
                </div>
              </div>

              {validationError && (
                <Alert variant="destructive">
                  <svg
                    className="h-4 w-4"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                  >
                    <path
                      fillRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                      clipRule="evenodd"
                    />
                  </svg>
                  <AlertTitle>Error</AlertTitle>
                  <AlertDescription>{validationError}</AlertDescription>
                </Alert>
              )}

              {selectedFile && uploadStatus !== 'error' && (
                <div className="space-y-4">
                  {uploadStatus === 'uploading' && (
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Uploading...</span>
                        <span className="font-medium">{uploadProgress}%</span>
                      </div>
                      <Progress value={uploadProgress} />
                    </div>
                  )}

                  <div className="flex gap-3">
                    <Button
                      onClick={handleUpload}
                      disabled={uploadStatus === 'uploading'}
                      className="flex-1"
                      size="lg"
                    >
                      {uploadStatus === 'uploading' ? 'Uploading...' : 'Upload File'}
                    </Button>
                    <Button
                      onClick={handleReset}
                      disabled={uploadStatus === 'uploading'}
                      variant="outline"
                      size="lg"
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Alert className="mt-6">
        <svg
          className="h-4 w-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
        <AlertTitle>File Requirements</AlertTitle>
        <AlertDescription>
          <ul className="list-disc list-inside space-y-1 mt-2">
            <li>Accepted formats: KMZ or KML files</li>
            <li>Maximum file size: 50MB</li>
            <li>File must contain valid Google Earth data</li>
          </ul>
        </AlertDescription>
      </Alert>
    </div>
  );
}
