import { useState } from 'react';
import { useLang } from '../i18n/useLang.js';
import { ui } from '../i18n/ui.js';

export default function PostcardFlip({ front, back, title }) {
  const lang = useLang();
  const t = ui[lang] ?? ui.en;
  const [flipped, setFlipped] = useState(false);
  const hasBack = Boolean(back);

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
                transform: 'rotateY(180deg)',
              }}
            />
          )}
        </div>
      </div>

      {hasBack && (
        <p
          style={{
            marginTop: '0.6rem',
            fontSize: '0.76rem',
            color: '#9a8c7e',
            textAlign: 'center',
            letterSpacing: '0.05em',
            userSelect: 'none',
          }}
        >
          {flipped ? t.flipToFront : t.flipToBack}
        </p>
      )}
    </div>
  );
}
