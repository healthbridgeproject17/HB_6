import { useEffect, useState } from 'react';
import { api } from '../api/client.js';

// Photos need the login token, so we fetch them as a blob. No photo (or a
// failed load) shows the initials as the fallback avatar.
export default function Avatar({ patientId, name = '', hasPhoto, version = 0, size = 64 }) {
  const [src, setSrc] = useState(null);

  useEffect(() => {
    let url = null;
    let alive = true;
    setSrc(null);
    if (hasPhoto && patientId) {
      api(`/patients/${patientId}/photo`, { raw: true })
        .then((blob) => { if (alive) { url = URL.createObjectURL(blob); setSrc(url); } })
        .catch(() => {});
    }
    return () => { alive = false; if (url) URL.revokeObjectURL(url); };
  }, [patientId, hasPhoto, version]);

  const initials = name.split(' ').filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join('') || '?';
  const style = { width: size, height: size };
  return src ? (
    <img src={src} alt={name} style={style} className="rounded-full object-cover ring-2 ring-white" />
  ) : (
    <div style={{ ...style, fontSize: size / 2.8 }} className="flex items-center justify-center rounded-full bg-teal-100 font-semibold text-teal-700 ring-2 ring-white">
      {initials}
    </div>
  );
}
