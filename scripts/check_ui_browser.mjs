import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';

const [debugUrl, baseUrl, source, screenshot] = process.argv.slice(2);
const pages = await (await fetch(debugUrl + '/json/list')).json();
const socket = new WebSocket(pages.find(page => page.type === 'page').webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, {once: true});
  socket.addEventListener('error', reject, {once: true});
});
let sequence = 0;
const pending = new Map();
const errors = [];
socket.addEventListener('message', event => {
  const message = JSON.parse(event.data);
  if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails);
  const request = pending.get(message.id);
  if (request) {
    pending.delete(message.id);
    clearTimeout(request.timer);
    message.error ? request.reject(new Error(JSON.stringify(message.error))) : request.resolve(message.result);
  }
});
function call(method, params = {}) {
  const id = ++sequence;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      pending.delete(id);
      reject(new Error('CDP request timed out: ' + method));
    }, 10000);
    pending.set(id, {resolve, reject, timer});
    socket.send(JSON.stringify({id, method, params}));
  });
}
async function evaluate(expression) {
  const result = await call('Runtime.evaluate', {expression, returnByValue: true, awaitPromise: true});
  assert.equal(result.exceptionDetails, undefined, JSON.stringify(result.exceptionDetails));
  return result.result.value;
}
async function until(expression) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('UI condition timed out: ' + expression + '\n' + await evaluate('document.body.innerText'));
}
try {
  await call('Runtime.enable');
  await call('Page.enable');
  await call('Emulation.setDeviceMetricsOverride', {width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false});
  await call('Page.navigate', {url: baseUrl});
  await until('document.querySelector("#run-count")?.textContent.includes("共 0")');
  await evaluate(`document.querySelector('#source').value=${JSON.stringify(source)}; document.querySelector('#inspect-form button').click()`);
  await until('Boolean(document.querySelector("input[aria-label=用户目标]"))');
  const standardRun = await evaluate('state.selected');
  await evaluate("document.querySelector('#scan-profile').value='expanded'; document.querySelector('#inspect-form button').click()");
  await until(`state.selected !== ${JSON.stringify(standardRun)} && document.querySelector('#action-status').textContent.includes('分析完成')`);
  const expandedPolicy = await evaluate("(async()=>{const data=await (await fetch('/api/runs/'+state.selected)).json(); return data.discovery.snapshot.scan_policy_id;})()");
  assert(expandedPolicy.startsWith('workspace-bounded-v1:'));
  await evaluate('document.querySelector("input[aria-label=用户目标]").value="inspect options"; document.querySelector("#detail form button").click()');
  await until('document.querySelector("#detail").textContent.includes("结果：STATIC_READY")');
  await evaluate(`const choice=document.querySelector('select[aria-label="选择命令或子命令"]'); choice.value='0'; choice.dispatchEvent(new Event('change')); document.querySelector('input[aria-label="参数 --output"]').value='result.json'; document.querySelector('input[aria-label="参数 --output"]').dispatchEvent(new Event('input')); document.querySelector('input[aria-label="预期结果"]').value='Review requested output'; document.querySelector('input[aria-label="用户目标"]').value='Bind output'; document.querySelector('#detail form button').click()`);
  await until('document.querySelector("#detail").textContent.includes("结果：STATIC_READY") && !document.querySelector("#detail form button").disabled');
  const downloaded = await evaluate(`(async () => {const link=Array.from(document.querySelectorAll('#detail a')).find(item=>item.textContent.includes('Download')); const result=await fetch(link.href); return {status:result.status,type:result.headers.get('Content-Type'),bytes:(await result.arrayBuffer()).byteLength};})()`);
  assert.equal(downloaded.status, 200);
  assert.equal(downloaded.type, 'application/zip');
  assert(downloaded.bytes > 100);
  await evaluate('Array.from(document.querySelectorAll("button")).find(button=>button.textContent.includes("加载前 100 条证据")).click()');
  await until('Boolean(document.querySelector(".evidence"))');
  if (screenshot) {
    const image = await call('Page.captureScreenshot', {format: 'png'});
    await writeFile(screenshot, Buffer.from(image.data, 'base64'));
  }
  await evaluate('document.querySelector("input[aria-label=用户目标]").value="deploy a Kubernetes cluster"; document.querySelector("#detail form button").click()');
  await until('document.querySelector("#detail").textContent.includes("结果：REVIEW_REQUIRED")');
  await evaluate('document.querySelector("#source").value="/"; document.querySelector("#inspect-form button").click()');
  await until('document.querySelector("#action-status").textContent.includes("UI_SOURCE_OUTSIDE_ALLOWED_ROOT")');
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({browser: await call('Browser.getVersion'), checks: [
    'empty state', 'static inspect', 'expanded scan creates distinct run', 'successful build', 'parameter binding', 'locked ZIP download', 'evidence view', 'unmatched goal', 'source boundary',
  ], javascriptExceptions: errors.length}));
} finally {
  socket.close();
}
