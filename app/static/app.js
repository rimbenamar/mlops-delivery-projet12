'use strict';
const $=id=>document.getElementById(id);
const fields=['distance_km','weight_kg','price_brl','freight_brl','promised_days','item_count','purchase_weekday','purchase_month'];
const names=['Distance vendeur–client','Poids total','Prix des articles','Frais de transport','Délai annoncé','Nombre d’articles','Jour de commande','Mois de commande'];
const integers=new Set(fields.slice(4));
let refreshing=false,running=false,stop=false,examples=[],samples=[],trend=[];
const format=(v,suffix='',factor=1,digits=2)=>v==null||!Number.isFinite(v)?'—':(v*factor).toLocaleString('fr-FR',{maximumFractionDigits:digits})+suffix;
const labels={on_time:'Dans le délai estimé',late:'Retard probable'};
function toolLink(port,path='/'){
 const u=new URL(location.href);
 // Codespaces forwards each service on a separate HTTPS hostname.
 if(/-8000\./.test(u.hostname)&&u.hostname.endsWith('.github.dev'))u.hostname=u.hostname.replace(/-8000\./,`-${port}.`);
 else u.port=port;
 u.pathname=path;u.search='';u.hash='';return u.href;
}
for(const [name,port,path] of [['mlflow',5000,'/'],['grafana',3000,'/d/projet12'],['prometheus',9090,'/']])$('tool-'+name).href=toolLink(port,path);
async function api(path,options={}){
 const response=await fetch(path,{...options,signal:AbortSignal.timeout(12000)});
 if(!response.ok){let message;try{message=(await response.json()).detail}catch{}throw Error(typeof message==='string'?message:`Erreur HTTP ${response.status}. Vérifiez les données et les services.`)}
 return response.json();
}
function rowToPayload(row){return Object.fromEntries(fields.map((name,i)=>[name,integers.has(name)?Math.round(Number(row[i])):Number(row[i])]))}
const predict=payload=>api('/predict',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
function bar(label,value,max=1,suffix=' %',factor=100,warning=false){
 const container=document.createElement('div'),row=document.createElement('div'),text=document.createElement('span'),number=document.createElement('b'),track=document.createElement('div'),fill=document.createElement('i');
 row.className='prob-row';text.textContent=label;number.textContent=format(value,suffix,factor);row.append(text,number);track.className='bar'+(warning?' warn':'');fill.style.width=`${Math.max(0,Math.min((value||0)/max*100,100))}%`;track.append(fill);container.append(row,track);return container;
}
function renderResult(d){
 const box=document.createElement('div');box.className='result-box'+(d.class_id?' risk-high':'');
 const caption=document.createElement('small');caption.textContent=`ANALYSE DU MODÈLE · VERSION ${d.model_version}`;
 const head=document.createElement('div');head.className='risk-header';const title=document.createElement('h3');title.textContent=labels[d.class_name];const risk=document.createElement('strong');risk.className='risk-value';risk.textContent=format(d.delay_probability,' %',100,1);head.append(title,risk);
 const p=document.createElement('p');p.className='result-description';p.textContent=d.class_id?'Commande à examiner en priorité selon le modèle. Le risque dépasse le seuil choisi sur la validation.':'Le risque est inférieur au seuil choisi sur la validation. Cela ne garantit pas le respect du délai.';
 const foot=document.createElement('div');foot.className='result-footer';foot.textContent=`Score de retard non calibré · Seuil de décision : ${format(d.decision_threshold,' %',100,1)}`;
 box.append(caption,head,bar('Score de risque de retard',d.delay_probability),p,foot);$('result').replaceChildren(box);
}
function renderTrend(v){
 if(!Number.isFinite(v))return;
 trend.push(v);if(trend.length>60)trend.shift();if(trend.length<2)return;
 $('traffic-empty').hidden=true;$('traffic-chart').hidden=false;
 const max=Math.max(.1,...trend)*1.15;const pts=trend.map((n,i)=>[i/(trend.length-1)*496+2,105-n/max*95]);
 const path=pts.map(([x,y],i)=>`${i?'L':'M'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
 $('chart-line').setAttribute('d',path);$('chart-area').setAttribute('d',`${path} L498,109 L2,109 Z`);
}
function renderRecent(rows){
 if(!rows.length)return;
 $('recent').replaceChildren(...rows.map(r=>{const tr=document.createElement('tr');[r.time,format(r.distance_km,' km'),r.promised_days+' jours',format(r.risk,' %',100,1),labels[r.class_name]].forEach((value,i)=>{const td=document.createElement('td');td.textContent=value;if(i===4)td.className=r.class_name==='late'?'status-late':'status-ontime';tr.append(td)});return tr}));
}
async function refresh(){
 if(refreshing)return;refreshing=true;
 try{
 const d=await api('/dashboard/overview');$('connection').textContent='Connecté';$('connection').className='pill';
 $('services').replaceChildren(...Object.entries(d.services).map(([name,up])=>{const s=document.createElement('span'),dot=document.createElement('i');dot.className='dot '+(up?'up':'down');s.append(dot,`${name==='api'?'FastAPI':name.charAt(0).toUpperCase()+name.slice(1)} · ${up?'En ligne':'Indisponible'}`);return s}));
 $('total').textContent=format(d.predictions,'',1,0);$('rps').textContent=format(d.metrics.rps);$('p95').textContent=format(d.metrics.p95,' ms',1000);$('p99').textContent='P99 : '+format(d.metrics.p99,' ms',1000);$('errors').textContent=format(d.metrics.errors);$('version').textContent='v'+d.model.version;
 $('dataset-count').textContent=format(d.model.dataset.rows,'',1,0);
 const m=d.model.training_metrics;$('precision').textContent=format(m.precision_late,' %',100,1);$('recall').textContent=format(m.recall_late,' %',100,1);$('f1').textContent=format(m.f1_late,'',1,3);$('auc').textContent=format(m.roc_auc,'',1,3);$('threshold').textContent=format(d.model.threshold,' %',100,1);
 const splits=d.model.splits;if(splits.test){$('periods').textContent=`Entraînement : ${splits.train.rows.toLocaleString('fr-FR')} commandes · Validation : ${splits.validation.rows.toLocaleString('fr-FR')} · Test : ${splits.test.rows.toLocaleString('fr-FR')} (${splits.test.start.slice(0,10)} → ${splits.test.end.slice(0,10)}).`;}
 $('baseline').textContent=`Retards dans le test : ${format(m.late_rate_test,' %',100,1)}. Accuracy du modèle : ${format(m.accuracy,' %',100,1)}. Baseline « toujours à l’heure » : ${format(m.baseline_accuracy,' %',100,1)}. Privilégier le F1, le rappel et la précision des retards.`;
 const importances=Object.entries(d.model.feature_importance).sort((a,b)=>b[1]-a[1]);$('importance-bars').replaceChildren(...importances.map(([f,v])=>bar(names[fields.indexOf(f)]||f,v)));
 const drift=d.drift;$('drift-badge').textContent=drift.detected==null?'Collecte en cours':drift.detected?'Dérive détectée':'Aucun écart détecté';$('drift-badge').className='pill'+(drift.detected?' warning':'');$('samples').textContent=`${drift.samples} / 200 observations`;
 $('drift-bars').replaceChildren(...fields.map((f,i)=>bar(names[i],drift.scores[f],3,' σ',1,drift.scores[f]>1.5)));
 $('drift-note').textContent=drift.detected==null?'30 observations minimum sont nécessaires.':drift.detected?'Décalage de moyenne détecté. Examiner les nouvelles données avant de conclure à une baisse de performance.':'Aucune variable ne dépasse le seuil. Ce contrôle ne détecte pas toutes les formes de dérive.';
 renderRecent(d.recent);renderTrend(d.metrics.rps);$('updated').textContent='Actualisé à '+new Date().toLocaleTimeString('fr-FR')+' · toutes les 5 s';
 }catch(e){$('connection').textContent='Connexion interrompue';$('connection').className='pill warning';$('updated').textContent=e.message;$('services').textContent='État des services indisponible';['total','rps','p95','errors'].forEach(id=>$(id).textContent='—');$('p99').textContent='P99 : —';$('drift-note').textContent='Actualisation impossible : les données ci-dessus peuvent être anciennes.'}
 finally{refreshing=false}
}
async function loadExamples(){try{const d=await api('/model');examples=d.examples;document.querySelectorAll('[data-preset]').forEach(b=>b.disabled=false)}catch(e){$('demo-progress').textContent='Exemples indisponibles : '+e.message}}
document.querySelectorAll('[data-preset]').forEach(b=>b.addEventListener('click',()=>{const example=examples[Number(b.dataset.preset)];if(example)fields.forEach(f=>document.querySelector(`[name="${f}"]`).value=example.input[f])}));
$('predict-form').addEventListener('submit',async e=>{e.preventDefault();$('prediction-error').hidden=true;$('predict-button').disabled=true;try{const payload=Object.fromEntries(fields.map(f=>[f,Number(document.querySelector(`[name="${f}"]`).value)]));renderResult(await predict(payload));await refresh()}catch(error){$('prediction-error').textContent=error.message;$('prediction-error').hidden=false}finally{$('predict-button').disabled=false}});
async function demo(drift){
 if(running)return;running=true;stop=false;['normal-demo','drift-demo'].forEach(id=>$(id).disabled=true);$('stop-demo').hidden=false;
 try{
 if(!samples.length)samples=(await api('/dashboard/traffic-sample')).samples;
 for(let i=0;i<200&&!stop;i++){const row=[...samples[i%samples.length]];if(drift){row[0]=5000;row[1]=50;row[4]=3}await predict(rowToPayload(row));$('demo-progress').textContent=`${drift?'Scénario de dérive':'Trafic de référence'} : ${i+1} / 200 requêtes`;await new Promise(resolve=>setTimeout(resolve,120))}
 $('demo-progress').textContent=stop?'Simulation arrêtée.':'Simulation terminée. Patienter quelques secondes pour la collecte Prometheus.';
 }catch(e){$('demo-progress').textContent=e.message}
 finally{running=false;['normal-demo','drift-demo'].forEach(id=>$(id).disabled=false);$('stop-demo').hidden=true;await refresh()}
}
$('normal-demo').addEventListener('click',()=>demo(false));$('drift-demo').addEventListener('click',()=>demo(true));$('stop-demo').addEventListener('click',()=>stop=true);$('refresh').addEventListener('click',()=>{refresh();if(!examples.length)loadExamples()});refresh();loadExamples();setInterval(refresh,5000);
