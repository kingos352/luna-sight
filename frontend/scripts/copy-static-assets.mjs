// Vercel (bağımsız web) dağıtımı için varlıkları çıktı dizinine kopyalar.
//
// Paket içindeki yol çözücü varlıkları `app/static/moon/<yol>` adresinden
// ister: Streamlit altında bu adres `enableStaticServing` ile sunulur,
// bağımsız dağıtımda ise site kökünden sunulmalı. Bu yüzden `data/` ve
// `textures/` çıktı dizinine aynı yol altına kopyalanır; kaynak ağaçta
// ikinci bir kopya tutulmaz.
import { cp, mkdir, readdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const repoRoot = fileURLToPath(new URL('../../', import.meta.url));
const outDir = process.env.LUNA_WEB_OUT_DIR ?? 'frontend/dist';
const target = resolve(repoRoot, outDir, 'app/static/moon');

await mkdir(target, { recursive: true });
for (const dir of ['data', 'textures']) {
  const from = resolve(repoRoot, 'app/static/moon', dir);
  await cp(from, resolve(target, dir), { recursive: true });
  const files = await readdir(resolve(target, dir));
  console.log(`[kopyalandi] ${dir}/ -> ${files.length} dosya`);
}
