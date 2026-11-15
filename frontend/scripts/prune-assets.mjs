import { readFile, readdir, unlink } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve, dirname, basename } from 'node:path';

const root = fileURLToPath(new URL('../../app/components/lunar/', import.meta.url));
const assets = resolve(root, 'assets');
const html = await readFile(resolve(root, 'index.html'), 'utf8');
for (const entry of await readdir(assets, { withFileTypes: true })) {
  if (!entry.isFile() || !/^index-[\w-]+\.(js|css)$/.test(entry.name)) continue;
  const path = resolve(assets, entry.name);
  if (dirname(path) !== assets || html.includes(basename(path))) continue;
  await unlink(path);
}
