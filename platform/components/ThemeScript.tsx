/**
 * Inline script injected into <head> BEFORE paint to set the correct theme,
 * preventing a flash of the wrong theme (FOUC). Reads localStorage, else
 * falls back to prefers-color-scheme, else dark (the product default).
 */
export function ThemeScript() {
  const code = `(function(){try{var t=localStorage.getItem('theme');if(t!=='light'&&t!=='dark'){t=window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';}document.documentElement.setAttribute('data-theme',t);}catch(e){document.documentElement.setAttribute('data-theme','dark');}})();`;
  return <script dangerouslySetInnerHTML={{ __html: code }} />;
}
