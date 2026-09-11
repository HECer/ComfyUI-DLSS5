const { chromium } = require('../../test-output/pw-runtime/node_modules/playwright-core');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const base = process.env.COMFYUI_SCREENSHOT_URL || 'http://127.0.0.1:8197';
const out = path.join(root, 'docs', 'images');
const reportPath = path.join(root, '..', 'test-output', 'production-ui', 'screenshot-report.json');
const workflowsDir = path.join(root, 'workflows');

const captures = [
  {
    workflow: '00_easy_one_node_2x.json',
    slug: 'easy',
    targets: ['DLSS5EasyPipeline'],
  },
  {
    workflow: '01_still_image_guided_2x.json',
    slug: 'advanced',
    targets: ['DLSS5FullPipeline'],
  },
  {
    workflow: '04_video_vda_small_temporal_2x.json',
    slug: 'vda',
    targets: ['DLSS5VideoDepthAnything', 'DLSS5FullPipeline'],
  },
  {
    workflow: '05_video_flashdepth_highres_2x.json',
    slug: 'flashdepth',
    targets: ['DLSS5FlashDepth'],
  },
  {
    workflow: '06_video_dlssg_24_to_48.json',
    slug: 'dlssg',
    targets: ['DLSSFrameGeneration'],
  },
];

function graphBounds(nodes) {
  const boxes = nodes.map((node) => {
    const pos = node.pos || [0, 0];
    const size = node.size || [200, 100];
    return { left: pos[0], top: pos[1], right: pos[0] + size[0], bottom: pos[1] + size[1] };
  });
  return boxes.reduce((acc, box) => ({
    left: Math.min(acc.left, box.left),
    top: Math.min(acc.top, box.top),
    right: Math.max(acc.right, box.right),
    bottom: Math.max(acc.bottom, box.bottom),
  }), { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity });
}

function fitGraph(nodes, canvasWidth, canvasHeight) {
  const bounds = graphBounds(nodes);
  const margin = { left: 90, right: 100, top: 80, bottom: 110 };
  const scale = Math.min(
    (canvasWidth - margin.left - margin.right) / Math.max(1, bounds.right - bounds.left),
    (canvasHeight - margin.top - margin.bottom) / Math.max(1, bounds.bottom - bounds.top),
    1.05,
  );
  const offset = [
    margin.left + ((canvasWidth - margin.left - margin.right) - (bounds.right - bounds.left) * scale) / 2 - bounds.left * scale,
    margin.top + ((canvasHeight - margin.top - margin.bottom) - (bounds.bottom - bounds.top) * scale) / 2 - bounds.top * scale,
  ];
  return { scale, offset };
}

function focusGraph(nodes, targets, canvasWidth, canvasHeight) {
  const selected = nodes.filter((node) => targets.includes(node.type));
  const bounds = graphBounds(selected.length ? selected : nodes);
  const scale = Math.min(1.38, Math.max(1.08, (canvasWidth - 180) / Math.max(1, bounds.right - bounds.left)));
  const centerX = (bounds.left + bounds.right) / 2;
  const centerY = (bounds.top + bounds.bottom) / 2;
  return {
    scale,
    offset: [canvasWidth / 2 - centerX * scale, canvasHeight / 2 - centerY * scale + 20],
  };
}

async function waitForCanvas(page) {
  await page.waitForFunction(() => !!window.comfyAPI?.app?.app?.graph && !!window.comfyAPI?.app?.app?.canvas, null, { timeout: 60000 });
  await page.waitForFunction(() => {
    const canvas = window.comfyAPI?.app?.app?.canvas?.canvas;
    return canvas?.isConnected && canvas.width > 0 && canvas.height > 0;
  }, null, { timeout: 60000 });
  await page.waitForTimeout(1800);
  await page.keyboard.press('Escape');
}

async function loadWorkflow(page, workflow, fit) {
  return page.evaluate(async ({ workflow, fit }) => {
    const { app } = await import('/scripts/app.js');
    await app.vueAppReady;
    app.graph.configure(workflow);
    app.canvas.setGraph(app.graph);
    app.canvas.ds.scale = fit.scale;
    app.canvas.ds.offset = fit.offset;
    app.canvas.setDirty(true, true);
    return app.graph._nodes.map((node) => ({
      id: node.id,
      type: node.type,
      title: node.title,
      pos: node.pos,
      size: node.size,
      widgets: (node.widgets || []).map((widget) => ({ name: widget.name, value: widget.value })),
    }));
  }, { workflow, fit });
}

(async () => {
  fs.mkdirSync(out, { recursive: true });
  fs.mkdirSync(path.dirname(reportPath), { recursive: true });
  const browser = await chromium.launch({
    executablePath: 'C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe',
    headless: true,
  });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  const response = await page.request.get(`${base}/object_info`);
  if (!response.ok()) throw new Error(`object_info returned ${response.status()}`);
  const definitions = await response.json();
  const report = { url: base, viewport: { width: 1920, height: 1080 }, captures: [], pageErrors };

  await page.goto(base, { waitUntil: 'domcontentloaded' });
  await waitForCanvas(page);
  await page.addStyleTag({ content: `
    .p-toast, .p-dialog-mask, .comfyui-menu, .comfyui-menu-container,
    #toast-container, [class*="toast"], [class*="Toast"], [role="alert"] { display: none !important; }
    canvas { background: #17191d !important; }
  ` });
  await page.evaluate(() => {
    for (const element of document.querySelectorAll('[class*="toast"], [class*="Toast"], [role="alert"]')) element.remove();
  });

  for (const item of captures) {
    const workflow = JSON.parse(fs.readFileSync(path.join(workflowsDir, item.workflow), 'utf8'));
    const nodeSpecs = workflow.nodes || [];
    const fit = fitGraph(nodeSpecs, 1920, 1080);
    const nodes = await loadWorkflow(page, workflow, fit);
    const missing = nodes.filter((node) => !definitions[node.type]);
    if (missing.length) throw new Error(`${item.workflow} has unknown nodes: ${missing.map((node) => node.type).join(', ')}`);
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(out, `comfyui-production-${item.slug}-workflow.png`), fullPage: true });

    const detailFit = focusGraph(nodeSpecs, item.targets, 1920, 1080);
    await page.evaluate(async (fit) => {
      const { app } = await import('/scripts/app.js');
      await app.vueAppReady;
      app.canvas.ds.scale = fit.scale;
      app.canvas.ds.offset = fit.offset;
      app.canvas.setDirty(true, true);
    }, detailFit);
    await page.waitForTimeout(700);
    await page.screenshot({ path: path.join(out, `comfyui-production-${item.slug}-node-detail.png`), fullPage: true });
    report.captures.push({
      workflow: item.workflow,
      slug: item.slug,
      nodeTypes: nodes.map((node) => node.type),
      workflowScale: fit.scale,
      detailScale: detailFit.scale,
    });
  }

  report.pageErrors = pageErrors;
  fs.writeFileSync(reportPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  await browser.close();
  if (pageErrors.length) throw new Error(`Browser page errors: ${pageErrors.join('; ')}`);
  console.log(`Captured ${report.captures.length * 2} production ComfyUI screenshots.`);
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
