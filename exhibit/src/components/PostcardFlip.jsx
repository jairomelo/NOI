import { useState } from 'react';

export default function PostcardFlip({ front, back, title }) {
  const [flipped, setFlipped] = useState(false);
  const hasBack = Boolean(back);

  return (
    <div>
      <div
        onClick={() => hasBack && setFlipped(f => !f)}
        style={{ cursor: hasBack ? 'pointer' : 'default', perspective: '1200px' }}
        title={hasBack ? (flipped ? 'Clic para ver el frente' : 'Clic para ver el reverso') : ''}
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
              alt={`${title} — reverso`}
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
          {flipped ? '↩ Clic para ver el frente' : '↩ Clic para ver el reverso'}
        </p>
      )}
    </div>
  );
}
