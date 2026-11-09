"use strict";
const fs=require("fs"),vm=require("vm"),assert=require("assert"),cp=require("child_process");
const path=require("path"),root=path.resolve(__dirname,"..");
const output="/tmp/tree-roadmap-minimal-test.html";
cp.execFileSync("python3",[path.join(root,"roadmap-src/build_roadmap.py"),"--output",output]);
const html=fs.readFileSync(output,"utf8");
const data=JSON.parse(html.match(/<script id="rm-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements=new Map(),events={},storage=new Map([["roadmap-v1",JSON.stringify({bought:{"W1:0":true},done:{D3:true}})]]);
const old=storage.get("roadmap-v1");
const document={
 documentElement:{dataset:{}},
 getElementById(id){if(!elements.has(id))elements.set(id,{textContent:id==="rm-data"?JSON.stringify(data):"",innerHTML:"",scrollIntoView(){}});return elements.get(id);},
 addEventListener(name,cb){events[name]=cb;},
 body:{appendChild(){}},createElement(){return {click(){},remove(){}};}
};
const sandbox={document,localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v)},window:{scrollY:0,scrollTo(){}},fetch:()=>Promise.reject(new Error("offline test")),console,setTimeout,URL,Blob,navigator:{clipboard:{writeText:async()=>{}}},Intl};
vm.createContext(sandbox);vm.runInContext(script,sandbox);
const app=sandbox.window.MinimalWorkshop;
function click(dataset){events.click({target:{closest:()=>({dataset})},preventDefault(){}});}
function change(dataset,value,type="select-one"){events.change({target:{dataset,value,type,hasAttribute(){return false;}}});}
function plain(x){return JSON.parse(JSON.stringify(x));}
assert.deepStrictEqual(plain(app.dimensions(600,900,6.35)),{strut:769,xrail:766,yrail:1155,xbelt:949,ybelt:1355,belt:3659,tableX:891.7,tableY:1213});
assert.strictEqual(app.dimensions(1220,2440,6.35).belt,7359);
for(const tab of ["map","stages","shop","cnc","printer","wood","supply","sources"]){
 click({tab});assert(elements.get("main").innerHTML.length>1000,tab+" rendered");
 assert(!/\b(?:NaN|undefined)\b/.test(elements.get("main").innerHTML),tab+" has no invalid values");
}
function needed(id){return app.needed(data.items.find(i=>i.id===id));}
assert(needed("print-service"));assert(!needed("printer-ff"));assert(!needed("printer-p1"));assert(!needed("filament"));
change({setting:"printer"},"ff");assert(!needed("print-service"));assert(needed("printer-ff"));assert(needed("filament"));assert(!needed("printer-p1"));
change({setting:"printer"},"p1");assert(!needed("printer-ff"));assert(needed("printer-p1"));
change({setting:"motion"},"kit");assert(needed("motion-kit"));assert(!needed("motion-china"));assert(!needed("xz"));assert(needed("controller"));
change({setting:"motion"},"china");assert(!needed("motion-kit"));assert(needed("motion-china"));assert(needed("xz"));
const caliper=data.items.find(i=>i.id==="caliper"),prior=plain(app.total());
app.getInventory().caliper="have";assert(!needed("caliper"));
assert(Math.abs(app.total()[0]-(prior[0]-caliper.cost[0]))<1e-6);
change({status:"dust"},"ordered");assert(!needed("dust"));change({status:"dust"},"need");assert(needed("dust"));
change({price:"dust"},"250","number");assert.deepStrictEqual(plain(app.cost(data.items.find(i=>i.id==="dust"))),[250,250]);
change({price:"dust"},"","number");assert.deepStrictEqual(plain(app.cost(data.items.find(i=>i.id==="dust"))),[200,400]);
change({setting:"mask"},"keep");assert(!needed("mask-body"));assert(!needed("mask-filters"));
change({setting:"planer"},"service");assert(!needed("planer"));assert(!needed("chip-collector"));assert(!needed("planer-supports"));assert(needed("planer-service"));
const printer=data.items.find(i=>i.id==="printer-p1"),p0=app.cost(printer)[0];
change({setting:"fx"},"3070","number");assert(app.cost(printer)[0]<p0);assert.strictEqual(app.cost(printer)[0],1332755/3070+12);
click({size:"1220,2440"});assert.strictEqual(app.getState().sizeY,2440);
click({action:"wood-fixed"});assert(app.getState().wood.fixed>0);
change({wood:"yield"},"0","number");assert.strictEqual(app.woodCalc().usable,0);assert.strictEqual(app.woodCalc().unit,null);assert.strictEqual(app.woodCalc().breakEven,null);
assert.strictEqual(storage.get("roadmap-v1"),old,"Legacy marks preserved");
console.log("PASS: all 8 views render; dimensions, exclusive choices, inventory, statuses, overrides, currency, wood calculator, legacy preservation");

