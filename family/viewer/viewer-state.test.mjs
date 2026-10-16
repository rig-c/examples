import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readViewState, writeViewState, defaultViewState, STORAGE_KEY } from './view-state.mjs';
import { fitCamera, cameraScale, worldToPanel, zoomAt, referenceFrame } from './viewport.mjs';
import { overlayGeometry } from './debug-overlay.mjs';

test('state round trip preserves every control and per-character camera; malformed storage falls back', () => {
  let raw;
  const storage = { getItem: () => raw, setItem: (key, value) => { assert.equal(key, STORAGE_KEY); raw=value; } };
  const state = { ...defaultViewState(), character:'nova', background:'magenta', paused:true, comparison:false,
    speed:2.1, gravity:-2, bones:true, mesh:true, meshOpacity:.7, cameras:{ nova:{ zoom:4, x:120, y:1900 } }, wind:{version:1,time:2} };
  assert.equal(writeViewState(storage,state),true);
  assert.deepEqual(readViewState(storage),state);
  raw='{'; assert.deepEqual(readViewState(storage),defaultViewState());
  raw=JSON.stringify({...state,speed:'2',gravity:1e300,cameras:{nova:{zoom:0,x:0,y:0}},character:'missing'});
  const restored=readViewState(storage);
  assert.equal(restored.speed,1); assert.equal(restored.gravity,0); assert.deepEqual(restored.cameras,{}); assert.equal(restored.character,'all5');
  assert.equal(writeViewState({setItem(){throw Error('denied');}},state),false);
});

test('camera shares actual displayed world scale across unequal panes and cursor anchored zoom', () => {
  const box={x:-400,y:0,width:800,height:2284};
  const panes=[{width:600,height:900},{width:450,height:900}];
  const camera=fitCamera(box,2.5), scale=cameraScale(box,panes,camera.zoom);
  for (const pane of panes) {
    const a=worldToPanel(-100,500,camera,scale,pane), b=worldToPanel(100,500,camera,scale,pane);
    assert.ok(Math.abs((b.x-a.x)-200*scale)<1e-10);
    const point={x:113,y:201};
    const world={x:camera.x+(point.x-pane.width/2)/scale,y:camera.y-(point.y-pane.height/2)/scale};
    const next=zoomAt(camera,scale,1.5,point,pane);
    const mapped=worldToPanel(world.x,world.y,next,scale*1.5,pane);
    assert.ok(Math.abs(mapped.x-point.x)<1e-10); assert.ok(Math.abs(mapped.y-point.y)<1e-10);
  }
});

test('outfit choice persists independently of scene and old v2 records keep controls', () => {
  const read = value => readViewState({ getItem: () => JSON.stringify(value) });
  const state = { ...defaultViewState(), character: 'nova', paused: true, speed: 1.7, outfits: { naru: 'homewear' }, cameras: { naru: { zoom: 3, x: 10, y: 1500 } } };
  assert.deepEqual(read(state), state);
  const { outfits, ...old } = state;
  assert.equal(read(old).outfits.naru, 'office'); assert.equal(read(old).speed, 1.7); assert.equal(read(old).paused, true);
  for (const value of ['../', null, 4]) assert.equal(read({ ...state, outfits: { naru: value } }).outfits.naru, 'office');
});

test('comparison registers half-resolution composite, individual and original 96px source margin', () => {
  const box={x:-400,y:0,width:800,height:2284};
  assert.deepEqual(referenceFrame('roa',box),box);
  const compact=referenceFrame('all5',box);
  assert.equal(compact.width/1358,2); assert.equal(compact.height/1142,2);
  assert.deepEqual(referenceFrame('composed',box),compact);
  const wide=referenceFrame('all5_wide',box);
  assert.equal(wide.x+96,-400); assert.equal(wide.width/4096,1);
  assert.equal(wide.height/2284,1);
});

test('mesh overlay follows actual deformed vertices and deduplicates shared edges; bone uses public world transform', () => {
  const vertices=[1,2,10,2,10,20,1,20];
  const player={posedFrame:()=>({order:[{kind:'mesh',slot:'hair',vertices,triangles:[0,1,2,0,2,3]}]}),
    bone: name=>({active:name!=='hidden',x:5,y:6,a:0,c:1})};
  const specs=[{name:'hair',length:10},{name:'hidden',length:100}];
  const before=overlayGeometry(player,specs,{mesh:true,bones:true});
  assert.equal(before.lines.filter(l=>l.kind==='mesh').length,5);
  assert.deepEqual(before.lines.find(l=>l.kind==='bone').points,[5,6,5,16]);
  assert.deepEqual(before.joints,[[5,6]]);
  vertices[0]=77;
  assert.equal(overlayGeometry(player,specs,{mesh:true,bones:false}).lines[0].points[0],77);
  assert.deepEqual(overlayGeometry(player,specs,{mesh:false,bones:false}),{lines:[],joints:[]});
});
