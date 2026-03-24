import { useState, useMemo } from 'react';
import { useLang } from '../i18n/useLang.js';
import { ui } from '../i18n/ui.js';

// LANG_NAMES now comes from the i18n dictionary (see t.langNames below)

function primaryLang(code) {
  if (!code) return null;
  return code.split(/[;,\s]/)[0].trim().toLowerCase();
}

export default function ObjectGrid({ postcards, base }) {
  const lang = useLang();
  const t = ui[lang] ?? ui.en;
  // ---- derived filter options (memoized once) ----
  const allSubjects = useMemo(() => {
    const s = new Set();
    postcards.forEach(p => p.subjects?.forEach(t => s.add(t)));
    return [...s].sort();
  }, [postcards]);

  const allLangs = useMemo(() => {
    const m = new Map();
    postcards.forEach(p => {
      const l = primaryLang(p.language);
      if (l) m.set(l, t.langNames[l] ?? l);
    });
    return [...m.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [postcards, lang]);

  // ---- filter / sort state ----
  const [activeSubject, setActiveSubject] = useState(null);
  const [activeLangs,   setActiveLangs]   = useState(new Set());
  const [sortMode,      setSortMode]      = useState('hue');
  const [cellSize,      setCellSize]      = useState(155); // px — drives grid column width

  // ---- filtered + sorted results ----
  const visible = useMemo(() => {
    let res = postcards;

    if (activeSubject)
      res = res.filter(p => p.subjects?.includes(activeSubject));

    if (activeLangs.size > 0)
      res = res.filter(p => activeLangs.has(primaryLang(p.language)));

    const sorted = [...res];
    if (sortMode === 'hue')
      sorted.sort((a, b) => (a.color_hue ?? 999) - (b.color_hue ?? 999));
    else if (sortMode === 'date')
      sorted.sort((a, b) => (a.date ?? '9999').localeCompare(b.date ?? '9999'));
    else if (sortMode === 'title')
      sorted.sort((a, b) => a.title.localeCompare(b.title));

    return sorted;
  }, [postcards, activeSubject, activeLangs, sortMode]);

  function toggleLang(code) {
    setActiveLangs(prev => {
      const next = new Set(prev);
      next.has(code) ? next.delete(code) : next.add(code);
      return next;
    });
  }

  // ---- styles (all inline to avoid Astro scoping issues in islands) ----
  const S = styles;

  return (
    <div>
      {/* ---- Controls bar ---- */}
      <div style={S.controls}>

        {/* Sort */}
        <div style={S.group}>
          <span style={S.label}>{t.sort}</span>
          <div style={S.segmented}>
            {[['hue', t.sortColor], ['date', t.sortDate], ['title', t.sortAZ]].map(([v, label]) => (
              <button
                key={v}
                onClick={() => setSortMode(v)}
                style={{ ...S.segBtn, ...(sortMode === v ? S.segBtnOn : {}) }}
              >{label}</button>
            ))}
          </div>
        </div>

        {/* Subject pills — temporarily hidden until subjects are better normalised
        <div style={S.group}>
          <span style={S.label}>Tema</span>
          <div style={S.pills}>
            <button
              onClick={() => setActiveSubject(null)}
              style={{ ...S.pill, ...(activeSubject === null ? S.pillOn : {}) }}
            >Todos</button>
            {allSubjects.map(s => (
              <button
                key={s}
                onClick={() => setActiveSubject(activeSubject === s ? null : s)}
                style={{ ...S.pill, ...(activeSubject === s ? S.pillOn : {}) }}
              >{s}</button>
            ))}
          </div>
        </div>
        */}

        {/* Language pills */}
        <div style={S.group}>
          <span style={S.label}>{t.language}</span>
          <div style={S.pills}>
            {allLangs.map(([code, label]) => (
              <button
                key={code}
                onClick={() => toggleLang(code)}
                style={{ ...S.pill, ...(activeLangs.has(code) ? S.pillOn : {}) }}
              >{label}</button>
            ))}
          </div>
        </div>

        {/* Grid size */}
        <div style={S.group}>
          <span style={S.label}>{t.size}</span>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <span style={{ ...S.label, minWidth: 'unset', fontSize: '0.65rem' }}>▪</span>
            <input
              type="range" min={5} max={250} step={5} value={cellSize}
              onChange={e => setCellSize(+e.target.value)}
              style={{ ...S.slider, width: '140px' }}
            />
            <span style={{ ...S.label, minWidth: 'unset', fontSize: '1rem' }}>▪</span>
          </div>
        </div>

        <span style={{ ...S.label, marginLeft: 'auto', alignSelf: 'center' }}>
          {t.postcards(visible.length)}
        </span>
      </div>

      {/* ---- Thumbnail grid ---- */}
      <style>{`
        .grid-flip-cell { perspective: 900px; }
        .grid-flip-inner {
          width: 100%; height: 100%;
          position: relative;
          transform-style: preserve-3d;
          transition: transform 0.55s cubic-bezier(0.22, 1, 0.36, 1);
          will-change: transform;
        }
        .grid-flip-cell:hover .grid-flip-inner { transform: rotateY(180deg); }
        .grid-flip-face {
          position: absolute; inset: 0;
          backface-visibility: hidden;
          -webkit-backface-visibility: hidden;
        }
        .grid-flip-back-face { transform: rotateY(180deg); }
      `}</style>
      <div style={{ ...S.grid, gridTemplateColumns: `repeat(auto-fill, minmax(${cellSize}px, 1fr))`, gap: `${Math.max(1, Math.round(cellSize / 60))}px` }}>
        {visible.map(card => {
          const backThumb = card.image_back ? `thumb_${card.image_back}` : null;
          return (
            <a
              key={card.objectid}
              href={`${base}detail/${card.objectid}`}
              className="grid-flip-cell"
              style={S.cell}
              title={card.title}
            >
              <div className="grid-flip-inner">
                {/* Front */}
                <div className="grid-flip-face">
                  {card.image_thumb
                    ? <img src={`${base}images/${card.image_thumb}`} alt={card.title} loading="lazy" style={S.thumb} />
                    : <div style={S.noImg}>?</div>
                  }
                </div>
                {/* Back */}
                <div className="grid-flip-face grid-flip-back-face">
                  {backThumb
                    ? <img src={`${base}images/${backThumb}`} alt={t.cardBack(card.title)} loading="lazy" style={S.thumb} />
                    : <div style={S.noImg}>∅</div>
                  }
                </div>
              </div>
              {card.color_hex && (
                <div style={{ ...S.colorBar, background: card.color_hex }} />
              )}
            </a>
          );
        })}
      </div>
    </div>
  );
}

const styles = {
  controls: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.85rem',
    padding: '1rem 1.25rem',
    background: '#1f1c19',
    border: '1px solid #3a342d',
    borderRadius: '6px',
    marginBottom: '1.25rem',
  },
  group: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
  label: {
    fontSize: '0.7rem', color: '#9a8c7e',
    textTransform: 'uppercase', letterSpacing: '0.09em',
    minWidth: '68px', flexShrink: 0,
  },
  segmented: {
    display: 'flex',
    border: '1px solid #3a342d',
    borderRadius: '4px',
    overflow: 'hidden',
  },
  segBtn: {
    padding: '0.28rem 0.7rem',
    fontSize: '0.78rem',
    background: 'transparent',
    border: 'none',
    borderRight: '1px solid #3a342d',
    color: '#9a8c7e',
    cursor: 'pointer',
  },
  segBtnOn: { background: '#c9964a', color: '#141210', fontWeight: 600 },
  pills: { display: 'flex', flexWrap: 'wrap', gap: '0.3rem' },
  pill: {
    padding: '0.18rem 0.55rem',
    fontSize: '0.73rem',
    background: 'transparent',
    border: '1px solid #3a342d',
    borderRadius: '999px',
    color: '#9a8c7e',
    cursor: 'pointer',
  },
  pillOn: { background: '#c9964a', borderColor: '#c9964a', color: '#141210' },
  slider: {
    WebkitAppearance: 'none',
    appearance: 'none',
    width: '110px', height: '3px',
    background: '#3a342d', borderRadius: '2px',
    outline: 'none', cursor: 'pointer',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(155px, 1fr))',
    gap: '3px',
  },
  cell: {
    display: 'block',
    aspectRatio: '4/3',
    overflow: 'hidden',
    position: 'relative',
    background: '#1f1c19',
    textDecoration: 'none',
  },
  thumb: {
    width: '100%', height: '100%',
    objectFit: 'cover',
    transition: 'transform 0.3s',
    display: 'block',
  },
  noImg: {
    width: '100%', height: '100%',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#3a342d', fontSize: '1.5rem',
  },
  colorBar: {
    position: 'absolute',
    bottom: 0, left: 0, right: 0,
    height: '3px',
  },
};
