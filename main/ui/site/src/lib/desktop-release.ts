/** Only an operator-configured installer in the project's GitHub release assets. */
export function desktopReleaseUrl(value: string | undefined): string | null {
  if (!value || value !== value.trim()) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.hostname !== 'github.com' || url.port ||
        url.username || url.password || url.search || url.hash) return null;
    const parts = url.pathname.split('/');
    if (parts.length !== 7 || parts.slice(0, 5).join('/') !== '/gjones01/NullCS/releases/download') return null;
    const tag = decodeURIComponent(parts[5]);
    const asset = decodeURIComponent(parts[6]);
    if (!tag || !asset.endsWith('.exe') || asset.length <= 4 ||
        [tag, asset].some(part => /[\\/\x00-\x1f\x7f]/.test(part) || part === '.' || part === '..')) return null;
    return url.href;
  } catch { return null; }
}
