const { chromium } = require('../../test-output/pw-runtime/node_modules/playwright-core');
const fs = require('fs');
const path = require('path');

const base = 'http://127.0.0.1:8190';
const out = path.resolve(__dirname, '../docs/images');

async function openWorkflow(page, name, scale, offset) {
  const workflow = JSON.parse(fs.readFileSync(path.resolve(__dirname, `../workflows/${name}.json`), 'utf8'));
  await page.goto(base, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(() => document.querySelector('canvas'));
  await page.evaluate(async ({ workflow, scale, offset }) => {
    const { app } = await import('/scripts/app.js');
    await app.vueAppReady;
    while (!app.graph || !app.canvas) await new Promise(r => setTimeout(r, 250));
    await new Promise(r => setTimeout(r, 12000));
    app.graph.configure(workflow);
    app.canvas.setGraph(app.graph);
    app.canvas.ds.scale = scale;
    app.canvas.ds.offset = offset;
    app.canvas.setDirty(true, true);
  }, { workflow, scale, offset });
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

  await openWorkflow(page, '06_video_dlssg_24_to_48', 0.78, [45, 80]);
  await page.screenshot({ path: path.join(out, 'comfyui-dlssg-workflow.png') });
  await page.evaluate(async () => { const { app } = await import('/scripts/app.js'); app.canvas.ds.scale = 1.35; app.canvas.ds.offset = [-810, 105]; app.canvas.setDirty(true, true); });
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(out, 'comfyui-dlssg-node-detail.png') });

  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
