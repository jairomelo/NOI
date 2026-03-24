import { useState, useEffect, useRef } from 'react';

/**
 * StoryViewer — scrollytelling exhibit component.
 *
 * Layout: sticky image panel (left/top) + scrolling chapter cards (right/bottom).
 * The image zooms & pans to each chapter's `focus: { x, y, scale }` as cards enter view.
 * x and y are percentages (0–100) of the image; scale is a zoom multiplier.
 *
 * To author a new story, edit the JSON file in src/data/stories/ and adjust
 * the x/y/scale values per chapter.
 */
export default function StoryViewer({ chapters, base }) {
  const [activeIdx, setActiveIdx]   = useState(0);
  const [imgSrc, setImgSrc]         = useState(`${base}images/${chapters[0]?.image}`);
  const [imgFading, setImgFading]   = useState(false);
  const cardRefs = useRef([]);

  const active = chapters[activeIdx] ?? chapters[0];

  // ---- IntersectionObserver: activate chapter when its card is centred ----
  useEffect(() => {
    const observers = cardRefs.current.map((el, i) => {
      if (!el) return null;
      const obs = new IntersectionObserver(
        ([entry]) => { if (entry.isIntersecting) setActiveIdx(i); },
        { threshold: 0.55, rootMargin: '-10% 0px -10% 0px' }
      );
      obs.observe(el);
      return obs;
    });
    return () => observers.forEach(o => o?.disconnect());
  }, [chapters]);

  // ---- Crossfade when image source changes ----
  useEffect(() => {
    const newSrc = `${base}images/${active.image}`;
    if (newSrc === imgSrc) return;
    setImgFading(true);
    const t = setTimeout(() => {
      setImgSrc(newSrc);
      setImgFading(false);
    }, 280);
    return () => clearTimeout(t);
  }, [active.image]);

  const { x, y, scale } = active.focus ?? { x: 50, y: 50, scale: 1 };

  return (
    <div style={S.root}>
      {/* ===== Sticky image panel ===== */}
      <div style={S.imagePanel} className="story-image-panel">
        <div style={S.imageFrame}>
          {/* Zoom layer — the transform lives here so hotspots scale with it */}
          <div
            style={{
              ...S.zoomLayer,
              transform:       `scale(${scale})`,
              transformOrigin: `${x}% ${y}%`,
              transition:      'transform 0.75s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
          >
            <img
              src={imgSrc}
              alt=""
              style={{
                ...S.img,
                opacity:    imgFading ? 0 : 1,
                transition: 'opacity 0.28s ease',
              }}
            />

            {/* Hotspot markers (only for chapters sharing the current image) */}
            {chapters.map((ch, i) => {
              if (ch.image !== active.image) return null;
              const isActive = i === activeIdx;
              return (
                <button
                  key={i}
                  onClick={() => {
                    setActiveIdx(i);
                    cardRefs.current[i]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
                  }}
                  title={ch.title}
                  style={{
                    ...S.hotspot,
                    left:         `${ch.focus.x}%`,
                    top:          `${ch.focus.y}%`,
                    // counter-scale so dots stay visually the same size while zoomed
                    transform:    `translate(-50%, -50%) scale(${1 / scale})`,
                    background:   isActive ? '#c9964a' : 'rgba(20,18,16,0.75)',
                    borderColor:  isActive ? '#c9964a' : 'rgba(201,150,74,0.7)',
                    color:        isActive ? '#141210' : '#f0e8da',
                    boxShadow:    isActive ? '0 0 0 4px rgba(201,150,74,0.3)' : 'none',
                  }}
                >
                  {i + 1}
                </button>
              );
            })}
          </div>

          {/* Chapter counter overlay */}
          <div style={S.chapterCounter}>
            {activeIdx + 1} / {chapters.length}
          </div>
        </div>

        {/* Progress bar */}
        <div style={S.progressBar}>
          <div
            style={{
              ...S.progressFill,
              width: `${((activeIdx + 1) / chapters.length) * 100}%`,
            }}
          />
        </div>
      </div>

      {/* ===== Scrolling cards panel ===== */}
      <div style={S.cardsPanel} className="story-cards-panel">
        {/* Spacer so first card starts mid-viewport */}
        <div style={{ height: '30vh' }} />

        {chapters.map((ch, i) => (
          <div
            key={i}
            ref={el => { cardRefs.current[i] = el; }}
            style={{
              ...S.card,
              opacity:    i === activeIdx ? 1 : 0.4,
              transform:  i === activeIdx ? 'translateY(0)' : 'translateY(12px)',
              transition: 'opacity 0.4s ease, transform 0.4s ease',
            }}
          >
            {ch.eyebrow && <p style={S.eyebrow}>{ch.eyebrow}</p>}
            <h2 style={S.cardTitle}>{ch.title}</h2>
            <p style={S.cardBody}>{ch.body}</p>

            {/* Author annotation (hint for story authors tweaking the JSON) */}
            {ch.annotation && (
              <p style={S.annotation}>{ch.annotation}</p>
            )}

            {/* Chapter step indicator */}
            <div style={S.step}>
              {chapters.map((_, j) => (
                <span
                  key={j}
                  style={{
                    ...S.stepDot,
                    background: j === i ? '#c9964a' : '#3a342d',
                  }}
                />
              ))}
            </div>
          </div>
        ))}

        {/* Trailing scroll space */}
        <div style={{ height: '40vh' }} />
      </div>
    </div>
  );
}

// ---- styles ----

const S = {
  root: {
    display:        'flex',
    alignItems:     'flex-start',
    gap:            0,
    position:       'relative',
  },
  imagePanel: {
    position:       'sticky',
    top:            '52px',
    height:         'calc(100vh - 52px)',
    display:        'flex',
    flexDirection:  'column',
    flexShrink:     0,
    overflow:       'hidden',
    background:     '#0e0c0a',
  },
  imageFrame: {
    position:       'relative',
    flex:           1,
    overflow:       'hidden',
  },
  zoomLayer: {
    position:       'absolute',
    inset:          0,
  },
  img: {
    width:          '100%',
    height:         '100%',
    objectFit:      'cover',
    objectPosition: 'center',
    display:        'block',
    userSelect:     'none',
    pointerEvents:  'none',
  },
  hotspot: {
    position:       'absolute',
    width:          '26px',
    height:         '26px',
    borderRadius:   '50%',
    border:         '2px solid',
    fontSize:       '10px',
    fontWeight:     700,
    cursor:         'pointer',
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'center',
    lineHeight:     1,
    padding:        0,
    transition:     'background 0.3s, box-shadow 0.3s',
    zIndex:         10,
  },
  chapterCounter: {
    position:       'absolute',
    bottom:         '12px',
    right:          '14px',
    fontSize:       '0.68rem',
    color:          'rgba(240,232,218,0.5)',
    letterSpacing:  '0.08em',
    pointerEvents:  'none',
  },
  progressBar: {
    height:         '2px',
    background:     '#3a342d',
    flexShrink:     0,
  },
  progressFill: {
    height:         '100%',
    background:     '#c9964a',
    transition:     'width 0.4s ease',
  },
  cardsPanel: {
    flex:           1,
    minWidth:       0,
    overflowY:      'visible',
  },
  card: {
    padding:        '0 3rem',
    minHeight:      '80vh',
    display:        'flex',
    flexDirection:  'column',
    justifyContent: 'center',
    gap:            '0.75rem',
  },
  eyebrow: {
    fontSize:       '0.68rem',
    color:          '#c9964a',
    letterSpacing:  '0.14em',
    textTransform:  'uppercase',
    margin:         0,
  },
  cardTitle: {
    fontFamily:     'Georgia, "Times New Roman", serif',
    fontSize:       'clamp(1.3rem, 2.5vw, 1.9rem)',
    fontWeight:     400,
    lineHeight:     1.25,
    color:          '#f0e8da',
    margin:         0,
  },
  cardBody: {
    fontSize:       '0.97rem',
    lineHeight:     1.85,
    color:          '#c8beb2',
    margin:         0,
    maxWidth:       '52ch',
  },
  annotation: {
    fontSize:       '0.72rem',
    color:          '#c9964a',
    borderLeft:     '2px solid #c9964a',
    paddingLeft:    '0.75rem',
    fontStyle:      'italic',
    margin:         '0.25rem 0 0',
    opacity:        0.75,
  },
  step: {
    display:        'flex',
    gap:            '5px',
    marginTop:      '0.5rem',
  },
  stepDot: {
    width:          '6px',
    height:         '6px',
    borderRadius:   '50%',
  },
};
