/** Component code has its own build; shared scientific data stays in the static directory. */
export function assetUrl(path: string): string {
  const streamlitUrl = new URLSearchParams(window.location.search).get('streamlitUrl');
  const application = new URL(streamlitUrl || `${window.location.origin}/`);
  if (!application.pathname.endsWith('/')) application.pathname += '/';
  application.search = ''; application.hash = '';
  return new URL(`app/static/moon/${path}`, application).href;
}
