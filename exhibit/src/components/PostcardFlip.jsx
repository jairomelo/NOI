import { useState } from 'react';
import { useLang } from '../i18n/useLang.js';
import { ui } from '../i18n/ui.js';

function storageKey(url, side) {
  return `rot:${side}:${url}`;
}

function loadRotation(url, side) {
  try {
    return parseInt(localStorage.getItem(storageKey(url, side)) ?? '0', 10) || 0;
  } catch {
    return 0;
  }
}

function saveRotation(url, side, angle) {
  try {
    localStorage.setItem(storageKey(url, side), String(angle));
  } catch {}
}

export default function PostcardFlip({ front, back, title }) {
  const lang = useLang();
  const t = ui[lang] ?? ui.en;
  const [flipped, setFlipped] = useState(false);
  const hasBack = Boolean(back);

  const [rotFront, setRotFront] = useState(() => loadRotation(front, 'front'));
  const [rotBack,  setRotBack]  = useState(() => loadRotation(back,  'back'));

  const currentRot = flipped ? rotBack : rotFront;

  function rotate() {
    const next = (currentRot + 90) % 360;
    if (flipped) {
      setRotBack(next);
      saveRotation(back, 'back', next);
    } else {
      setRotFront(next);
      saveRotation(front, 'front', next);
    }
  }

  return (
    <div>
      <div
        onClick={() => hasBack && setFlipped(f => !f)}
        style={{ cursor: hasBack ? 'pointer' : 'default', perspective: '1200px' }}
        title={hasBack ? (flipped ? t.flipTipFront : t.flipTipBack) : ''}
      >
        <div
          style={{
            position: 'relative',
            transformStyle: 'preserve-3d',
            transition: 'transform 0.55s cubic-bezier(0.4,0.2,0.2,1)',
            transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
          }}
        >
          {/* Front */}
          <img
            src={front}
            alt={title}
            style={{
              width: '100%',
              height: 'auto',
              display: 'block',
              borderRadius: '4px',
              backfaceVisibility: 'hidden',
              WebkitBackfaceVisibility: 'hidden',
              transform: `rotate(${rotFront}deg)`,
              transition: 'transform 0.3s ease',
            }}
          />
          {/* Back */}
          {hasBack && (
            <img
              src={back}
              alt={`${title} — ${lang === 'es' ? 'reverso' : 'back'}`}
              style={{
                position: 'absolute',
                inset: 0,
                width: '100%',
                height: '100%',
                objectFit: 'contain',
                background: '#1a1614',
                borderRadius: '4px',
                backfaceVisibility: 'hidden',
                WebkitBackfaceVisibility: 'hidden',
                transform: `rotateY(180deg) rotate(${rotBack}deg)`,
                transition: 'transform 0.3s ease',
              }}
            />
          )}
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.6rem' }}>
        {hasBack
          ? <p style={{ margin: 0, fontSize: '0.76rem', color: '#9a8c7e', letterSpacing: '0.05em', userSelect: 'none' }}>
              {flipped ? t.flipToFront : t.flipToBack}
            </p>
          : <span />
        }
        <button
          onClick={e => { e.stopPropagation(); rotate(); }}
          title="Rotate 90°"
          style={{
            background: 'none',
            border: '1px solid #555',
            borderRadius: '4px',
            color: '#9a8c7e',
            cursor: 'pointer',
            fontSize: '1rem',
            lineHeight: 1,
            padding: '3px 7px',
            userSelect: 'none',
          }}
        >
          ↻
        </button>
      </div>
    </div>
  );
}
