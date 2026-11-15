// Browser verification against the actual hosted site and pinned external audio.
// Install Playwright separately; this is not a model-evaluation entry point.
import assert from 'node:assert/strict';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {metricLabel} from '../demo/data-utils.mjs';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE||'playwright');
const base=process.env.DEMO_URL||'http://127.0.0.1:8765/';
const out=process.env.DEMO_CHECK_OUTPUT||'.local/demo-check';await mkdir(out,{recursive:true});
const read=async name=>JSON.parse(await readFile(new URL('../demo/data/'+name,import.meta.url),'utf8'));
const index=await read('index.json'),registry=await read('baselines.json');
const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_EXECUTABLE?{executablePath:process.env.CHROMIUM_EXECUTABLE}:{}),args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1440,height:1100}});page.setDefaultTimeout(90000);
const errors=[],checks=[];page.on('pageerror',e=>errors.push(e.message));
async function open(qid){
  await page.goto(base+'?q='+qid);
  await page.waitForSelector('#scene-content:not([hidden])');
  assert.equal(await page.locator('.baseline').count(),12);
  assert.match(await page.locator('#question-id').innerText(),new RegExp(qid));
  const shard=JSON.parse(gunzipSync(await readFile(new URL('../demo/data/shards/'+qid.slice(0,2)+'.json.gz',import.meta.url))));
  const result=shard[qid],empty=index.empty_questions.includes(qid);
  for(const b of registry){
    const row=page.locator(`.baseline[data-model="${b.id}"]`),record=result.outputs[b.id];
    assert.equal(await row.locator('.metric>span').innerText(),metricLabel(result.metrics[b.id],result.task,empty)[0]);
    if(record){
      const detail=row.locator('details');await detail.evaluate(e=>e.open=true);
      const pre=detail.locator('pre');assert.equal(await pre.nth(0).textContent(),record.raw_text===null?'Raw text not archived':record.raw_text);
      assert.equal(await pre.nth(1).textContent(),JSON.stringify(record.output,null,2));
      assert.deepEqual(JSON.parse(await pre.nth(2).textContent()),record.scored);
      await detail.evaluate(e=>e.open=false);
    }else assert.equal(await row.locator('.status').textContent(),'Output not archived');
  }
  checks.push({question:qid,metrics:12,outputs:Object.keys(result.outputs).length});
}
try{
  for(const qid of ['00453216fc112c99fd735b2c','00afedbe599a7a8dfd77cd0d','00da58508b0fad2b736898a7','02951f24479cfd1f175dcff1']){
    await open(qid);
    if(qid==='00453216fc112c99fd735b2c'){
      await page.setViewportSize({width:1440,height:1700});await page.screenshot({path:out+'/desktop.png'});await page.setViewportSize({width:1440,height:1100});
    }
  }
  // Cursor changes the dynamic frame view without inventing prediction frames.
  await page.locator('#timeline').evaluate(e=>e.value='3.5');await page.locator('#timeline').dispatchEvent('input');
  assert.match(await page.locator('#clock').textContent(),/^3\.50/);
  await open(index.defaults.find(e=>e.label==='Multiple receivers').question);
  const receivers=await page.locator('#receiver option').evaluateAll(xs=>xs.map(x=>x.value));assert.ok(receivers.length>1);
  await page.click('#play');
  await page.waitForFunction(()=>/verified|unavailable/.test(document.querySelector('#audio-status').textContent),null,{timeout:180000});
  assert.match(await page.locator('#audio-status').textContent(),/SHA-256 verified/);
  await page.waitForFunction(()=>parseFloat(document.querySelector('#clock').value)>.2);
  await page.click('#play');
  await page.locator('#timeline').evaluate(e=>e.value='2.75');await page.locator('#timeline').dispatchEvent('input');
  await page.selectOption('#receiver',receivers[1]);
  await page.waitForFunction(()=>/verified|unavailable/.test(document.querySelector('#audio-status').textContent),null,{timeout:180000});
  assert.match(await page.locator('#audio-status').textContent(),/SHA-256 verified/);
  assert.match(await page.locator('#clock').textContent(),/^2\.75/);
  await page.click('#play');await page.waitForFunction(()=>parseFloat(document.querySelector('#clock').value)>3);
  await page.click('#play');checks.push({audio:'two real remote recordings verified, decoded and played',receiver_switch_time:2.75});
  await page.click('#results-tab');assert.equal(await page.locator('#result-tables tbody tr').count(),24);
  await page.click('#coverage-tab');assert.match(await page.locator('#availability').innerText(),/479,988/);
  const mobile=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});mobile.setDefaultTimeout(90000);mobile.on('pageerror',e=>errors.push(e.message));
  await mobile.goto(base+'?q=00453216fc112c99fd735b2c');await mobile.waitForSelector('#scene-content:not([hidden])');
  assert.equal(await mobile.locator('.baseline').count(),12);
  assert.ok(await mobile.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),'Mobile viewport must not overflow horizontally');
  await mobile.screenshot({path:out+'/mobile.png',fullPage:true});checks.push({mobile:'390px, all rows present, no horizontal overflow'});
  assert.deepEqual(errors,[]);
  await writeFile(out+'/verification.json',JSON.stringify({base,checked_at:new Date().toISOString(),checks,errors},null,2));
  console.log(JSON.stringify({passed:true,checks,errors},null,2));
}finally{await browser.close();}
