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
for(const tab of ["map","stages","shop","cnc","printer","welding","wood","supply","sources"]){
 click({tab});assert(elements.get("main").innerHTML.length>1000,tab+" rendered");
 assert(!/\b(?:NaN|undefined)\b/.test(elements.get("main").innerHTML),tab+" has no invalid values");
}
function needed(id){return app.needed(data.items.find(i=>i.id===id));}
assert(!needed("print-service"));assert(!needed("printer-ff"));assert(!needed("printer-p1"));assert(needed("printer-k2"));assert(needed("filament"));assert.strictEqual(app.getState().sizeX,1250);assert.strictEqual(app.getState().sizeY,2500);assert.strictEqual(app.getState().budget,5000);assert(needed("cnc-table-steel"));assert(!needed("cnc-table"));
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
console.log("PASS: all 9 views render; dimensions, exclusive choices, inventory, statuses, overrides, currency, wood calculator, legacy preservation");


change({setting:"printer"},"k2");change({setting:"table"},"steel");change({setting:"welding"},"none");
change({setting:"fx"},"1535","number");change({setting:"mask"},"new");change({setting:"planer"},"own");
click({size:"1250,2500"});
const steel=data.items.find(i=>i.id==="cnc-table-steel"),baseSteel=app.cost(steel)[0];
change({setting:"table"},"wood");assert(needed("cnc-table"));assert(!needed("cnc-table-steel"));
change({setting:"table"},"steel");
change({setting:"motion"},"kit");assert(!needed("cnc-extra-belt"));
click({size:"1860,2660"});assert(needed("cnc-extra-belt"));assert(app.cost(steel)[0]>baseSteel);
click({size:"1250,2500"});assert(!needed("cnc-extra-belt"));assert.strictEqual(app.cost(steel)[0],baseSteel);
const priorState=JSON.stringify(app.getState());const withMig=app.scenarioCost({welding:"mig"},false),noMig=app.scenarioCost({},false);
assert(withMig[0]>noMig[0]);assert.strictEqual(JSON.stringify(app.getState()),priorState,"Scenario comparison leaves configuration unchanged");
change({setting:"welding"},"mig");
for(const id of ["weld-machine","weld-gas","weld-ppe","metal-grinder"])assert(needed(id));
change({setting:"welding"},"none");
for(const id of ["weld-machine","weld-gas","weld-ppe","metal-grinder"])assert(!needed(id));
const previousMarks=JSON.stringify({schema:2,printer:"service",sizeX:600,sizeY:900,status:{dust:"ordered"},prices:{dust:255}});
const memory2=new Map([["roadmap-minimal-v2",previousMarks],["roadmap-v1",old]]),nodes2=new Map();
const context2={...sandbox,window:{scrollY:0,scrollTo(){}},localStorage:{getItem:k=>memory2.get(k)||null,setItem:(k,v)=>memory2.set(k,v)},document:{...document,getElementById(id){if(!nodes2.has(id))nodes2.set(id,{textContent:id==="rm-data"?JSON.stringify(data):"",innerHTML:"",scrollIntoView(){}});return nodes2.get(id);},addEventListener(){}}};
vm.createContext(context2);vm.runInContext(script,context2);
const migrated=context2.window.MinimalWorkshop.getState();
assert.strictEqual(migrated.ownerRevision,3);assert.strictEqual(migrated.printer,"k2");assert.strictEqual(migrated.sizeX,1250);assert.strictEqual(migrated.status.dust,"ordered");assert.strictEqual(migrated.prices.dust,255);
console.log("PASS: owner migration preserves marks/prices; full-sheet materials scale; tables and MIG alternatives do not double count");
