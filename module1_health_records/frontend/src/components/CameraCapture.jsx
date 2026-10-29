import { useEffect, useRef, useState } from 'react';
import { Alert, Button, Modal } from './ui.jsx';

// Live camera for computers (webcam). Phones use the native camera instead
// (see DocumentsPanel), which gives better photos and works without HTTPS.
export default function CameraCapture({ onCapture, onClose }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('The camera is not available in this browser or over this connection. Use "Choose file" instead.');
      return undefined;
    }
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 } }, audio: false })
      .then((stream) => {
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) videoRef.current.srcObject = stream;
        setReady(true);
      })
      .catch((err) => {
        setError(err.name === 'NotAllowedError'
          ? 'Camera permission was denied. Allow camera access in your browser, or use "Choose file".'
          : 'Could not start the camera. Use "Choose file" instead.');
      });
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  function capture() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    canvas.toBlob(
      (blob) => {
        if (!blob) { setError('Could not capture the photo. Try again.'); return; }
        onCapture(new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' }));
      },
      'image/jpeg',
      0.92
    );
  }

  return (
    <Modal title="Take a photo of the document" onClose={onClose}>
      <Alert>{error}</Alert>
      {!error && (
        <>
          <video ref={videoRef} playsInline muted autoPlay className="w-full rounded-xl bg-black" />
          <p className="mt-2 text-xs text-slate-400">Hold the page flat, fill the frame, and avoid glare and shadows.</p>
          <div className="mt-3 flex gap-2">
            <Button onClick={capture} disabled={!ready}>Capture</Button>
            <Button variant="secondary" onClick={onClose}>Cancel</Button>
          </div>
        </>
      )}
    </Modal>
  );
}
