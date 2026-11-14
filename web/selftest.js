import {frameDistance,dtw,rankTemplates,crossValidate,VisualRecognizer} from './recognizer.js';
const checks = [];
function check(name, passed) {checks.push({name,passed:!!passed});if(!passed)throw new Error(name);}
try {
  const a = [[0,1],[1,0],[0,1]], b = [[1,0],[0,1],[1,0]];
  check('identical frame has zero distance',frameDistance(a[0],a[0])===0);
  check('identical sequence has zero DTW',dtw(a,a)===0);
  check('empty clip is not a match',dtw([],a)===Infinity);
  check('different sequence has positive distance',dtw(a,b)>0);
  check('ranking uses visual data',rankTemplates(a,[{phrase:'A',frames:a},{phrase:'B',frames:b}])[0].phrase==='A');
  check('time warping handles stretched sequence',dtw(a,[a[0],a[0],a[1],a[2]])===0);
  check('evaluation refuses a single class',crossValidate([{id:'1',phrase:'A',frames:a},{id:'2',phrase:'A',frames:a}])===null);
  const samples=[{id:'1',phrase:'A',frames:a},{id:'2',phrase:'A',frames:a},{id:'3',phrase:'B',frames:b},{id:'4',phrase:'B',frames:b}];
  const result=crossValidate(samples);
  check('leave-one-out evaluates held-out examples',result.correct===4&&result.total===4);
  const recognizer=new VisualRecognizer();
  recognizer.samples=samples;
  check('classification returns matching class',recognizer.classify(a)[0].phrase==='A');
  let refused=false;
  try{recognizer.samples=[samples[0]];recognizer.classify(a);}catch{refused=true;}
  check('recognition refuses insufficient calibration',refused);
  document.getElementById('results').textContent=JSON.stringify({passed:checks.length,checks},null,2);
  window.testResults={passed:checks.length,checks};
} catch(error) {
  document.getElementById('results').textContent=error.stack;
  window.testResults={failed:error.message,checks};
}
