import { useState, useEffect } from 'react';

/**
 * Returns the current UI language ('en' | 'es') and updates reactively
 * when the <html lang="..."> attribute changes (driven by the nav toggle).
 */
export function useLang() {
  const get = () =>
    typeof document !== 'undefined' ? (document.documentElement.lang || 'en') : 'en';

  const [lang, setLang] = useState(get);

  useEffect(() => {
    const obs = new MutationObserver(() =>
      setLang(document.documentElement.lang || 'en')
    );
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
    return () => obs.disconnect();
  }, []);

  return lang;
}
