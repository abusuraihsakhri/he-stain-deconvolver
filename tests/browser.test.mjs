import {test} from "node:test";
import assert from "node:assert/strict";
import {STAIN_VECTORS, buildStainMatrix, invert3, deconvolvePixels, MAX_PIXELS} from "../web/deconvolution.mjs";

function solid(r,g,b) {
  return {width: 2, height: 2, data: new Uint8ClampedArray([r,g,b,255,r,g,b,255,r,g,b,255,r,g,b,255])};
}

test("stain matrix inverts and normalizes", () => {
  for (const vectors of Object.values(STAIN_VECTORS)) {
    const matrix = buildStainMatrix(vectors);
    const inv = invert3(matrix);
    matrix.forEach((row, i) => {
      assert.ok(Math.abs(Math.hypot(...row)-1) < 1e-12);
      for (let k=0;k<3;k++) {
        const dot = row.reduce((sum,v,j)=>sum+v*inv[j][k],0);
        assert.ok(Math.abs(dot-(i===k?1:0))<1e-10);
      }
    });
  }
});
test("white image yields white channels and zero concentrations", () => {
  const result = deconvolvePixels(solid(255,255,255));
  for (const name of result.names) {
    assert.equal(result.statistics[name].mean_od, 0);
    assert.equal(result.statistics[name].percent_positive_area, 0);
  }
  for (const image of result.channels) assert.ok(image.every((v,i) => i%4===3 || v===255));
});
test("known pure hematoxylin concentration round-trips", () => {
  const matrix = buildStainMatrix(STAIN_VECTORS.HE);
  const rgb = matrix[0].map(v=>Math.floor(255*Math.pow(10,-v)));
  const result=deconvolvePixels(solid(...rgb));
  assert.ok(Math.abs(result.statistics.hematoxylin.mean_od-1)<0.03);
  assert.ok(Math.abs(result.statistics.eosin.mean_od)<0.03);
});
test("white balance maps background reference near white", () => {
  const result=deconvolvePixels(solid(200,200,200), {whiteRef:[200,200,200]});
  assert.equal(result.statistics.hematoxylin.mean_od, 0);
});
test("positive area threshold and grayscale output", () => {
  const result=deconvolvePixels(solid(40,60,80), {mode:"grayscale",threshold:0});
  assert.equal(result.channels.length, 3);
  assert.equal(result.channels[0][0],result.channels[0][1]);
  assert.ok(result.statistics.hematoxylin.percent_positive_area>=0);
});
test("invalid inputs rejected", () => {
  assert.throws(()=>buildStainMatrix([[1,0,0],[2,0,0]]));
  assert.throws(()=>buildStainMatrix([[NaN,0,0],[0,1,0]]));
  assert.throws(()=>deconvolvePixels({width:MAX_PIXELS+1,height:1,data:[]}));
  assert.throws(()=>deconvolvePixels(solid(1,2,3),{threshold:NaN}));
  assert.throws(()=>deconvolvePixels(solid(1,2,3),{whiteRef:[0,250,250]}));
});
