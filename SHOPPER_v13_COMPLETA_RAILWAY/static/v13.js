/* SHOPPER 13: wallet + recipe-to-basket; server-backed, no invented availability. */
'use strict';
const V13={cards:[],recipes:[],recipeId:null,detail:null,result:null,servings:2,placeId:null,loading:false,which:'Carrefour'};
const cardLogo=name=>({"Club DIA":"🔴","Club Carrefour":"🔵","Lidl Plus":"🟡","Club Alcampo":"🟢"}[name]||'▣');
const chainLogo=name=>({DIA:'🔴',Carrefour:'🔵'}[name]||'🛒');
const V13oldRender=render,V13oldAction=action,V13oldSubmit=submit;
render=function(){
 if(S.view==='cards'||S.view==='recipes'){
  $('#main').innerHTML=S.view==='cards'?cardsView():recipesView();
  $('#placeLabel').textContent=placeLabel(currentPlace());
  return;
 }
 V13oldRender();
 if(S.view==='home'){
  const target=$('#main .section-title');
  target?.insertAdjacentHTML('beforebegin',`<div class="v13-home-quick"><button class="v13-home-box" data-view="recipes"><span>🍳</span><strong>Receta → Cesta</strong><small>Pega ingredientes y compara cadenas</small></button><button class="v13-home-box" data-view="cards"><span>▣</span><strong>Mis tarjetas</strong><small>Todos tus programas, a mano</small></button></div>`);
 }
};
action=async function(type,el){if(type.startsWith('v13'))return v13Action(type,el);return V13oldAction(type,el)};
submit=async function(f){if(f.id.startsWith('v13'))return v13Submit(f);return V13oldSubmit(f)};
async function v13Load(view){
 if(view==='cards'){
  if(!S.user){render();return}
  try{V13.cards=(await api('/api/v13/cards')).items}catch(e){toast(e.message,true)}
 }else if(view==='recipes'){
  if(!S.user){render();return}
  try{V13.recipes=(await api('/api/v13/recipes')).items}catch(e){toast(e.message,true)}
 }
 if(S.view===view)render();
}
const v13auth=()=>!S.user?empty('🔒','Inicia sesión para guardar tus datos','Tus tarjetas y recetas son privadas. Puedes entrar desde cualquier dispositivo con tu cuenta.',`<button class="btn primary" data-action="register">Crear cuenta / entrar</button>`):null;
function cardsView(){
 if(!S.user)return `${headline('TU CARTERA','Todas tus tarjetas, un toque','Muestra tus códigos estáticos o abre la app oficial cuando el programa utiliza códigos dinámicos.')}${v13auth()}`;
 return `${headline('CARTERA DIGITAL','Mis tarjetas','Guarda las tarjetas de fidelización de tus supermercados, sin guardar contraseñas ni acceder a tus puntos.',`<button class="btn primary" data-action="v13NewCard">＋ Añadir tarjeta</button>`)}
 <div class="v13-banner"><span>🔐</span><div><b>Privado y a mano</b><p>Los códigos se guardan cifrados en el servidor y solo se revelan en tu sesión. En programas como Lidl Plus puede ser necesario utilizar el código dinámico de la app oficial.</p></div></div>
 ${V13.cards.length?`<div class="v13-card-grid">${V13.cards.map(c=>`<article class="v13-loyalty"><div class="v13-loyalty-symbol">${cardLogo(c.chain)}</div><div class="v13-loyalty-name">${E(c.chain)}</div><h3>${E(c.label)}</h3><p>${c.mode==='official'?'Acceso a la aplicación oficial':`${E(c.barcode_type)} · termina en •••• ${E(c.last_four)}`}</p><div class="v13-card-actions">${c.mode==='official'?`<a class="btn primary small" target="_blank" rel="noopener noreferrer" href="${E(c.official_url)}">↗ Abrir programa</a>`:`<button class="btn primary small" data-action="v13ShowCard" data-id="${c.id}">▥ Mostrar código</button>`}<button class="btn small" data-action="v13DeleteCard" data-id="${c.id}" aria-label="Eliminar tarjeta">Eliminar</button></div></article>`).join('')}</div>`:
 empty('▣','Tu cartera empieza aquí','Añade un programa y elige si quieres guardar un código estático o un acceso oficial.','<button class="btn primary" data-action="v13NewCard">Añadir mi primera tarjeta</button>')}
 <div class="v13-footnote">ℹ️ Algunas tarjetas requieren su aplicación original, identificación o un código temporal. SHOPPER no activa cupones, no simula descuentos de socio ni se conecta a cuentas ajenas.</div>`;
}
function recipesView(){
 if(!S.user)return `${headline('DE LA RECETA A LA COMPRA','Cocinar sin rehacer la lista','Pega los ingredientes y encuentra referencias comparables con precios web de muestra.')}${v13auth()}`;
 if(V13.recipeId&&V13.detail)return recipeDetailView();
 return `${headline('TU RECETARIO','De receta a cesta','Importa ingredientes, ajusta raciones y crea una lista de compra en segundos.',`<button class="btn primary" data-action="v13ImportRecipe">＋ Importar receta</button>`)}
 <section class="v13-feature"><div><span class="v13-overline">COMPARA ANTES DE COMPRAR</span><h2>¿Cuánto cuesta preparar<br>tu próxima receta?</h2><p>Una receta se convierte en ingredientes y en propuestas de productos por cadena. Si falta un ingrediente, lo indicamos; no inventamos un total.</p><button class="btn primary" data-action="v13ImportRecipe">🍳 Importar ingredientes</button></div><div class="v13-feature-art">🥘<small>1 receta<br>varios supermercados</small></div></section>
 <div class="section-title"><h2>📚 Recetas guardadas</h2><small>${V13.recipes.length} recetas</small></div>
 ${V13.recipes.length?`<div class="v13-recipes-grid">${V13.recipes.map((r,i)=>`<article class="v13-recipe-tile" tabindex="0"><span class="v13-recipe-image">${['🥘','🍳','🥗','🍝','🍚'][i%5]}</span><div><span class="v13-overline">${r.servings} raciones · ${r.ingredient_count} ingredientes</span><h3>${E(r.name)}</h3><div class="v13-card-actions"><button class="btn small primary" data-action="v13OpenRecipe" data-id="${r.id}">Ver comparación</button><button class="btn small" data-action="v13DeleteRecipe" data-id="${r.id}">Eliminar</button></div></div></article>`).join('')}</div>`:
 empty('🍝','Tu primera receta','Pega ingredientes de una receta o su JSON-LD Schema.org, y guárdala en tu recetario.','<button class="btn primary" data-action="v13ImportRecipe">Importar receta</button>')}
 <div class="v13-footnote">Los precios son históricos y de una muestra reducida. No conocemos las existencias, el precio actual de tu tienda física ni los cupones personales.</div>`;
}
function recipeDetailView(){
 const r=V13.detail,cp=V13.result;
 const places=S.boot?.places||[];
 return `${headline('RECETARIO',r.name,`${r.ingredients.length} ingredientes · ${r.servings} raciones de origen`,`<button class="btn" data-action="v13BackRecipes">← Volver</button>`)}
 <div class="v13-recipe-controls card"><label class="v13-label">Raciones <input class="input" id="v13Servings" type="number" min="1" max="100" value="${V13.servings}"></label><label class="v13-label">Comparar para <select class="select" id="v13Place"><option value="">Todas las cadenas de la muestra</option>${places.map(p=>`<option value="${p.id}" ${Number(V13.placeId)===p.id?'selected':''}>${E(p.name)}</option>`).join('')}</select></label><button class="btn primary" data-action="v13Compare">Recalcular</button></div>
 <div class="v13-ingredients card"><h2>📝 Ingredientes identificados</h2><p class="desc">Revisa cantidades, formatos y posibles errores antes de añadirlos a la compra.</p><div class="v13-pills">${r.ingredients.map((x,i)=>`<span>${E(x.raw)}</span>`).join('')}</div></div>
 ${cp?`${cp.comparisons.length?`<div class="section-title"><h2>Comparación por cadena</h2><span class="tag uncertain">Muestra fechada · no stock local</span></div><div class="v13-chain-results">${cp.comparisons.map(c=>`<section class="v13-chain card"><header><span class="v13-chain-icon">${chainLogo(c.chain)}</span><div><h3>${E(c.chain)}</h3><small>${c.covered}/${c.total} ingredientes con referencia</small></div><strong>${c.complete?euro(c.estimated_full_purchase_cents):'Incompleto'}</strong></header><div class="v13-progress"><span style="width:${c.total?Math.round(c.covered/c.total*100):0}%"></span></div><p class="v13-subtotal">${c.complete?'Precio de envases completos según la muestra':'Subtotal de productos encontrados: '+euro(c.known_subtotal_cents)}${!c.has_snapshot?' · sin datos de esta cadena':''}</p>${c.lines.map((line,i)=>`<div class="v13-ingredient-row"><div><b>${E(line.ingredient.name)}</b><small>${E(line.ingredient.amount)} ${E(line.ingredient.unit)}</small></div><div>${line.match?`<span class="v13-match-name">${E(line.match.name)}</span><small>${line.match.packs} envase(s) · ${euro(line.match.subtotal_cents)}</small><select data-v13-choice="1" data-recipe-id="${r.id}" data-chain="${E(c.chain)}" data-index="${i}" class="select v13-choice" aria-label="Elegir producto para ${E(line.ingredient.name)}">${[...line.options,...line.alternatives].map(op=>`<option value="${E(op.listing_id)}" ${op.listing_id===line.match.listing_id?'selected':''}>${op.requires_confirmation?'⚠️ Alternativa: ':''}${E(op.name)} — ${euro(op.subtotal_cents)}</option>`).join('')}</select>${line.match.requires_confirmation?'<small>⚠️ Sustitución elegida manualmente; comprueba alérgenos</small>':''}`:`<span class="v13-missing">Sin referencia</span><small>Se añadirá como pendiente a la cesta</small>${line.alternatives.length?`<select data-v13-choice="1" data-recipe-id="${r.id}" data-chain="${E(c.chain)}" data-index="${i}" class="select v13-choice"><option value="">Elegir alternativa (opcional)</option>${line.alternatives.map(op=>`<option value="${E(op.listing_id)}">⚠️ ${E(op.name)} — ${euro(op.subtotal_cents)}</option>`).join('')}</select>`:''}`}</div></div>`).join('')}<button class="btn primary" data-action="v13ToBasket" data-chain="${E(c.chain)}">＋ Convertir en cesta de ${E(c.chain)}</button></section>`).join('')}</div>`:'<p class="notice">No hay cadenas en este lugar.</p>'}<div class="v13-footnote">${E(cp.notice)}</div>`:'<div class="loading">Calculando referencias disponibles…</div>'}`;
}
function v13NewCardModal(){
 modal(`<div class="v13-modal-title"><span>▣</span><div><h2>Añadir tarjeta</h2><p class="desc">Tus tarjetas de supermercado, en un solo sitio.</p></div></div>
 <form id="v13CardForm"><label class="v13-label">Programa <select class="select" id="v13CardPreset"><option value="">Personalizado</option><option>Club DIA</option><option>Club Carrefour</option><option>Lidl Plus</option><option>Club Alcampo</option></select></label>
 <label class="v13-label">Nombre de la tarjeta <input name="label" class="input" required maxlength="80" placeholder="Mi tarjeta habitual"></label>
 <label class="v13-label">Tipo de acceso <select class="select" id="v13CardMode" name="mode"><option value="static">Código estático de mi tarjeta</option><option value="official">Abrir la app o web oficial</option></select></label>
 <div id="v13CodeFields"><label class="v13-label">Tipo de código <select class="select" name="barcode_type"><option value="EAN13">EAN-13 (13 cifras)</option><option value="CODE128">Code 128</option><option value="QR">QR fijo</option></select></label><label class="v13-label">Código <input name="code" class="input" autocomplete="off" placeholder="Número impreso en la tarjeta" maxlength="180"></label></div>
 <label id="v13UrlField" class="v13-label hidden">Enlace oficial HTTPS <input name="official_url" class="input" placeholder="https://..."></label>
 <label class="v13-label">Nota (opcional) <input name="notes" class="input" maxlength="200" placeholder="Por ejemplo: usar en caja"></label>
 <p class="mini">Nunca guardes contraseñas, PIN bancarios ni códigos de acceso de un solo uso. Programas dinámicos requieren su app.</p><button class="btn primary" type="submit">Guardar tarjeta</button></form>`);
}
function v13RecipeImportModal(){
 modal(`<div class="v13-modal-title"><span>🍳</span><div><h2>Importar una receta</h2><p class="desc">Pega ingredientes uno por línea o JSON-LD con <code>recipeIngredient</code>.</p></div></div>
 <form id="v13RecipeForm"><label class="v13-label">Nombre de la receta<input class="input" name="name" maxlength="100" required placeholder="Arroz con leche de casa"></label>
 <label class="v13-label">Raciones originales<input class="input" name="servings" type="number" value="2" min="1" max="100" required></label>
 <label class="v13-label">Lista de ingredientes<textarea class="input v13-textarea" name="ingredients_text" required maxlength="12000" placeholder="200 g arroz\n250 ml leche entera\n2 huevos\n50 g harina"></textarea></label>
 <label class="v13-label">Enlace a la receta (opcional, solo referencia)<input class="input" type="url" name="source_url" placeholder="https://..."> </label>
 <div class="button-row"><button type="button" class="btn" data-action="v13SampleRecipe">Probar ejemplo</button><button class="btn primary" type="submit">Analizar y guardar →</button></div>
 <p class="mini">Por seguridad y derechos de terceros, SHOPPER no descarga una web completa: copia sus ingredientes o el bloque de datos estructurados. Las unidades ambiguas requieren revisión.</p></form>`)
}
async function v13Action(type,el){
 switch(type){
 case 'v13NewCard':return v13NewCardModal();
 case 'v13ShowCard':{
  const cid=Number(el.dataset.id);const card=V13.cards.find(x=>x.id===cid);
  modal(`<div class="v13-code-display"><span class="v13-overline">TARJETA DE FIDELIZACIÓN</span><h2>${E(card.label)}</h2><p>${E(card.chain)}</p><img src="/api/v13/cards/${cid}/barcode.svg" alt="Código ${E(card.barcode_type)}" class="v13-barcode"><div id="v13Reveal">Código oculto</div><button class="btn" data-action="v13Reveal" data-id="${cid}">Mostrar número</button><p class="mini">Comprueba que esta cadena acepte códigos estáticos mostrados en pantalla. Mantén el brillo alto al escanear.</p></div>`);return}
 case 'v13Reveal':{const x=await api(`/api/v13/cards/${Number(el.dataset.id)}/reveal`);$('#v13Reveal').textContent=x.code;return}
 case 'v13DeleteCard':{if(!confirm('¿Eliminar esta tarjeta de SHOPPER?'))return;await api(`/api/v13/cards/${Number(el.dataset.id)}`,'DELETE');V13.cards=(await api('/api/v13/cards')).items;render();return}
 case 'v13ImportRecipe':return v13RecipeImportModal();
 case 'v13SampleRecipe':{const f=$('#v13RecipeForm');f.elements.name.value='Arroz cremoso con huevo';f.elements.ingredients_text.value='200 g arroz\n250 ml leche entera\n2 huevos\n50 g harina';f.elements.servings.value='2';return}
 case 'v13OpenRecipe':V13.recipeId=Number(el.dataset.id);V13.detail=await api(`/api/v13/recipes/${V13.recipeId}`);V13.servings=V13.detail.servings;V13.placeId=S.placeId;await v13CompareNow();render();return;
 case 'v13BackRecipes':V13.recipeId=null;V13.detail=null;V13.result=null;return render();
 case 'v13DeleteRecipe':{if(!confirm('¿Eliminar esta receta de tu biblioteca?'))return;await api(`/api/v13/recipes/${Number(el.dataset.id)}`,'DELETE');V13.recipes=(await api('/api/v13/recipes')).items;render();return}
 case 'v13Compare':V13.servings=Number($('#v13Servings').value);V13.placeId=Number($('#v13Place').value)||null;await v13CompareNow();render();return;
 case 'v13ToBasket':{const d=await api(`/api/v13/recipes/${V13.recipeId}/to-basket`,'POST',{chain:el.dataset.chain,servings:V13.servings,place_id:V13.placeId});await refresh();V13.recipeId=null;V13.detail=null;V13.result=null;S.basketId=d.basket_id;await readBasket();nav('basket');toast(`Nueva cesta: ${d.matched_lines} referencias y ${d.unmatched_lines} ingredientes pendientes`);return}
 }
}
async function v13CompareNow(){V13.result=await api(`/api/v13/recipes/${V13.recipeId}/compare`,'POST',{servings:V13.servings,place_id:V13.placeId})}
async function v13Submit(f){
 const d=Object.fromEntries(new FormData(f).entries());
 if(f.id==='v13CardForm'){
  let payload={chain:$('#v13CardPreset').value||'Otro supermercado',label:d.label,mode:d.mode,
    barcode_type:d.mode==='static'?d.barcode_type:null,code:d.mode==='static'?d.code:null,
    official_url:d.mode==='official'?d.official_url:null,notes:d.notes};
  await api('/api/v13/cards','POST',payload);closeModal();V13.cards=(await api('/api/v13/cards')).items;render();toast('Tarjeta guardada de forma privada');return;
 }
 if(f.id==='v13RecipeForm'){
  const x=await api('/api/v13/recipes','POST',{name:d.name,servings:Number(d.servings),ingredients_text:d.ingredients_text,source_url:d.source_url||null});
  V13.recipes=(await api('/api/v13/recipes')).items;
  V13.recipeId=x.id;V13.detail=await api(`/api/v13/recipes/${x.id}`);V13.servings=V13.detail.servings;V13.placeId=S.placeId;closeModal();await v13CompareNow();nav('recipes');toast('Receta analizada: comprueba los ingredientes y precios');return;
 }
}
document.addEventListener('click',async ev=>{
 const t=ev.target.closest('[data-view]');if(!t)return;
 if(['recipes','cards'].includes(t.dataset.view)){await v13Load(t.dataset.view)}
});
document.addEventListener('change',async ev=>{
 let t=ev.target;
 try{
 if(t.id==='v13CardPreset'){
  let chosen=t.value;let mode=$('#v13CardMode');let url=$('#v13UrlField input');
  if(chosen==='Lidl Plus')mode.value='official';
  if(['Club DIA','Club Carrefour','Lidl Plus','Club Alcampo'].includes(chosen)){
    const u={'Club DIA':'https://www.dia.es/','Club Carrefour':'https://www.carrefour.es/clubcarrefour/','Lidl Plus':'https://www.lidl.es/','Club Alcampo':'https://www.compraonline.alcampo.es/'};
    url.value=u[chosen];
  }
  v13SyncCardFields();
 }
 if(t.id==='v13CardMode')v13SyncCardFields();
 if(t.matches('[data-v13-choice]')){
  const source=V13.result?.comparisons?.find(x=>x.chain===t.dataset.chain)?.lines[Number(t.dataset.index)];
  const alt=source?.alternatives?.some(x=>x.listing_id===t.value);
  if(alt&&!confirm('Este producto no es equivalente exacto. ¿Has revisado los ingredientes, alérgenos y formato y quieres usarlo como alternativa?')){render();return}
  await api(`/api/v13/recipes/${t.dataset.recipeId}/choice`,'PUT',{chain:t.dataset.chain,ingredient_index:Number(t.dataset.index),listing_id:t.value||null,confirm_alternative:!!alt});
  await v13CompareNow();render();toast('Producto de referencia actualizado');
 }
 }catch(e){toast(e.message,true)}
});
function v13SyncCardFields(){const m=$('#v13CardMode')?.value;$('#v13CodeFields')?.classList.toggle('hidden',m!=='static');$('#v13UrlField')?.classList.toggle('hidden',m!=='official')}
