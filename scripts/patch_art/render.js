// Renders build/*.svg to build/*.png at 960px. Needs Playwright and an Oswald Bold woff2 at build/oswald-700.woff2.
const {chromium}=require('playwright');const fs=require('fs');
const font=fs.readFileSync('build/oswald-700.woff2').toString('base64');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:960,height:960}});
for(const f of fs.readdirSync('build').filter(f=>f.endsWith('.svg'))){const svg=fs.readFileSync('build/'+f,'utf8').replace('width="480" height="480"','width="960" height="960"');
await p.setContent(`<html><head><style>@font-face{font-family:Oswald;font-weight:700;src:url(data:font/woff2;base64,${font}) format("woff2")}</style></head><body style="margin:0;background:transparent">${svg}</body></html>`);
await p.evaluate(()=>document.fonts.ready);await p.waitForTimeout(150);await p.screenshot({path:'build/'+f.replace('.svg','.png'),omitBackground:true,clip:{x:0,y:0,width:960,height:960}});}
await b.close();})();
