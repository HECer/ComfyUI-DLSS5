const { chromium } = require('../../test-output/pw-runtime/node_modules/playwright-core');
const path = require('path');

const base = 'http://127.0.0.1:8190';
const out = path.resolve(__dirname, '../docs/images');

async function openWorkflow(page, name, scale, offset) {
  await page.goto(base, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelector('canvas'));
  await page.evaluate(async ({ name, scale, offset }) => {
    const { app } = await import('/scripts/app.js');
    await app.vueAppReady;
    while (!app.rootGraphInternal || !app.canvas) await new Promise(r => setTimeout(r, 250));
    await new Promise(r => setTimeout(r, 5000));
    const response = await fetch(`/api/userdata/workflows%2FComfyUI-DLSS5%2F${name}.json`);
    if (!response.ok) throw new Error(`Workflow request failed: ${response.status}`);
    app.rootGraphInternal.configure(await response.json());
    app.canvas.setGraph(app.rootGraphInternal);
    app.canvas.ds.scale = scale;
    app.canvas.ds.offset = offset;
    app.canvas.setDirty(true, true);
  }, { name, scale, offset });
  await page.waitForTimeout(800);
  await page.addStyleTag({ content: `body > :not(#vue-app), .comfyui-menu, .comfyui-body-left,
    .comfyui-body-right, .p-toast, .p-dialog-mask { display: none !important; }
    canvas { background: #17191d !important; }` });
}

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe',
    headless: true,
  });
  const context = await browser.newContext({ viewport: { width: 1800, height: 1000 } });
  const page = await context.newPage();

  await openWorkflow(page, '04_video_vda_small_temporal_2x', 0.72, [40, 70]);
  await page.screenshot({ path: path.join(out, 'comfyui-vda-workflow.png') });
  await page.evaluate(async () => { const { app } = await import('/scripts/app.js'); app.canvas.ds.scale = 1.2; app.canvas.ds.offset = [-330, 120]; app.canvas.setDirty(true, true); });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(out, 'comfyui-vda-node-detail.png') });

  await openWorkflow(page, '05_video_flashdepth_highres_2x', 0.68, [45, 75]);
  await page.screenshot({ path: path.join(out, 'comfyui-flashdepth-workflow.png') });
  await page.evaluate(async () => { const { app } = await import('/scripts/app.js'); app.canvas.ds.scale = 1.15; app.canvas.ds.offset = [-325, 170]; app.canvas.setDirty(true, true); });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(out, 'comfyui-flashdepth-node-detail.png') });

  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
