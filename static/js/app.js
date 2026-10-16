'use strict';

const paths = {
  search:'<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  cart:'<path d="M2 3h3l2.6 12h12.8l2-9H6"/><circle cx="9" cy="20" r="1"/><circle cx="19" cy="20" r="1"/>',
  user:'<circle cx="12" cy="8" r="4"/><path d="M4 22v-2a8 8 0 0 1 16 0v2"/>',
  users:'<circle cx="9" cy="7" r="3"/><path d="M2 21v-2a7 7 0 0 1 14 0v2m1-17a3 3 0 0 1 0 6m2 4a6 6 0 0 1 3 5v2"/>',
  bell:'<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M9 21h6"/>',
  help:'<circle cx="12" cy="12" r="9"/><path d="M9 9a3 3 0 0 1 6 0c0 2-3 2-3 5m0 3h.01"/>',
  heart:'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0l-1 1-1-1a5.5 5.5 0 1 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z"/>',
  home:'<path d="m3 10 9-8 9 8v11H3zM9 21v-8h6v8"/>',
  pin:'<path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>',
  truck:'<path d="M1 4h13v13H1zm13 5h5l4 5v3h-9"/><circle cx="5" cy="19" r="2"/><circle cx="18" cy="19" r="2"/>',
  shield:'<path d="m12 2 9 4v6c0 6-9 10-9 10S3 18 3 12V6z"/><path d="m8 12 3 3 5-6"/>',
  return:'<path d="M4 10a8 8 0 1 1 2 8M4 3v7h7"/>',
  sparkles:'<path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5zM21 2v4m-2-2h4"/>',
  arrow:'<path d="M3 12h18m-6-6 6 6-6 6"/>',
  laptop:'<rect x="4" y="3" width="16" height="13" rx="1"/><path d="m4 16-3 5h22l-3-5M9 19h6"/>',
  headphones:'<path d="M3 14v-3a9 9 0 0 1 18 0v3"/><rect x="2" y="12" width="5" height="9" rx="2"/><rect x="17" y="12" width="5" height="9" rx="2"/>',
  shirt:'<path d="m8 3-6 4 3 6 3-2v11h8V11l3 2 3-6-6-4a4 4 0 0 1-8 0Z"/>',
  dress:'<path d="M8 2v5l2 3-6 12h16l-6-12 2-3V2M8 5h8M10 10h4"/>',
  shoe:'<path d="M3 6h5l2 6 6 3 5 1 1 5H2V11zM2 18h20m-11-5 2-2m1 4 2-2"/>',
  appliance:'<rect x="4" y="3" width="16" height="19" rx="3"/><path d="M4 8h16m-9-3h2"/><circle cx="12" cy="15" r="4"/>',
  beauty:'<path d="M6 10h7v12H6zM7 10V4l5-2v8m5 3h5v9h-5zm1-3h3v3"/>',
  watch:'<rect x="5" y="6" width="14" height="12" rx="4"/><path d="m8 6 1-5h6l1 5m-8 12 1 5h6l1-5m-4-8v3l2 1"/>',
  ticket:'<path d="M2 5h20v5a2 2 0 0 0 0 4v5H2v-5a2 2 0 0 0 0-4zM8 5v3m0 3v2m0 3v3"/><path d="m12 15 6-6m-6 0h.01m6 6h.01"/>',
  bag:'<path d="M4 7h16l2 15H2zM8 8V5a4 4 0 0 1 8 0v3"/>',
  close:'<path d="m5 5 14 14M5 19 19 5"/>',
  trash:'<path d="M3 6h18M9 6V3h6v3M5 6l1 16h12l1-16M10 10v8m4-8v8"/>',
  check:'<circle cx="12" cy="12" r="10"/><path d="m7 12 3 3 7-7"/>',
  logout:'<path d="M9 3H3v18h6m7-15 6 6-6 6M8 12h14"/>',
  lock:'<rect x="4" y="10" width="16" height="12" rx="2"/><path d="M8 10V6a4 4 0 0 1 8 0v4"/>',
  filter:'<path d="M3 5h18l-7 8v7l-4 2v-9z"/>',
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
  code:'<path d="m8 5-7 7 7 7m8-14 7 7-7 7m-3-17-2 20"/>'
};
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true">${paths[name] || paths.bag}</svg>`;
const e = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const money = value => new Intl.NumberFormat('vi-VN').format(Number(value)||0)+'₫';
const compact = value => value>=1000 ? (value/1000).toFixed(1).replace('.0','')+'k' : String(value||0);
const nameOf = name => (name||'').replace(/\s*\(Model #\d+\)/g,'').replace(/\s*\(#\d+\)/g,'');
const shortProvince = name => (name||'Việt Nam').replace('Thành phố Hồ Chí Minh','TP. Hồ Chí Minh').replace('Thành phố ','');
const date = value => new Date(String(value).includes('T') ? value : value+'Z').toLocaleString('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',hour:'2-digit',minute:'2-digit',day:'2-digit',month:'2-digit',year:'numeric'});
const $ = selector => document.querySelector(selector);
const state = {user:null,demo:false,profiles:[],categories:[],provinces:[],wishlist:new Set(),cart:[],notices:[],
  debug:false,debugInfo:null,labResult:null,recommendations:null,recommendationContexts:{},products:null,route:'home',
  routeVersion:0,modalVersion:0,authMode:'login',selectedProduct:null,quantity:1,checkout:{address_id:null,voucher_code:'',use_coins:false,payment_method:'COD'},
  checkoutKey:null,quote:null,quoteVersion:0,busy:false,addingProduct:false,switching:false,pendingIntent:null,userVersion:0,recsVersion:0,debugVersion:0,orderTab:'Tất cả',hero:0,homeLimit:24,demoInterest:null,demoComparison:null,demoLoading:false,lastInteraction:null};

async function api(path,options={}) {
  path=storeRecommendationPath(path);
  let response;
  try{
    response=await fetch('/api'+path,{credentials:'same-origin',...options,signal:options.signal||AbortSignal.timeout(state.native&&path.startsWith('/recommendations')?30000:15000),headers:{'Content-Type':'application/json',...(options.headers||{})}});
  }catch{
    throw new Error('Kết nối mất quá nhiều thời gian. Vui lòng thử lại.');
  }
  let data;try{data=await response.json();}catch{throw new Error('Kết nối bị gián đoạn. Vui lòng thử lại.');}
  if(!response.ok) {
    const detail=data.detail;
    const message=typeof detail==='string'?detail:Array.isArray(detail)?detail.map(x=>x.loc.at(-1)+': '+x.msg).join('; '):'Có lỗi xảy ra. Vui lòng thử lại.';
    const error=new Error(message);error.status=response.status;throw error;
  }
  return data;
}
const post=(path,data={})=>api(path,{method:'POST',body:JSON.stringify(data)});
const put=(path,data={})=>api(path,{method:'PUT',body:JSON.stringify(data)});
function toast(message,error=false){const holder=$('#toasts');while(holder.children.length>=3)holder.firstElementChild.remove();const el=document.createElement('div');el.className='toast'+(error?' error':'');el.textContent=message;holder.append(el);setTimeout(()=>el.remove(),4200);}
function updateIcons(root=document){root.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=icon(el.dataset.icon);el.removeAttribute('data-icon');});}
function placeholder(root=document){root.querySelectorAll('img').forEach(img=>{img.addEventListener('error',()=>{if(!img.src.endsWith('/placeholder.svg'))img.src='/static/images/placeholder.svg';},{once:true});});}
function hydrate(){updateIcons();placeholder();document.querySelectorAll('.mobile-nav button').forEach(b=>b.classList.toggle('active',b.dataset.action===state.route));}
function appHTML(html){$('#app').innerHTML=html;hydrate();}
function empty(title,text,action='home',label='Khám phá ngay',symbol='bag'){return `<div class="empty-state">${icon(symbol)}<h3>${e(title)}</h3><p>${e(text)}</p><button class="primary" data-action="${action}">${e(label)} ${icon('arrow')}</button></div>`;}
function breadcrumb(title){return `<div class="breadcrumb"><button data-action="home">Trang chủ</button><span>›</span><span>${e(title)}</span></div>`;}
function openModal(title,html,small=false){const modal=$('#modal');modal.classList.toggle('modal-small',small);$('#modal-content').innerHTML=`<div class="modal-header"><h2 id="modal-title">${e(title)}</h2><button class="close-button" data-action="close-modal" aria-label="Đóng">${icon('close')}</button></div><div class="modal-body">${html}</div>`;if(!modal.open)modal.showModal();hydrate();}
function closeModal(){state.modalVersion++;$('#modal').close();}
function requireLogin(){if(state.user)return true;openAuth();return false;}
function navigate(route,params={}){if(state.busy){toast('Đang xử lý đơn hàng. Vui lòng chờ kết quả.');return;}state.pendingIntent=null;closeModal();const query=new URLSearchParams(params).toString();const next='#/'+route+(query?'?'+query:'');if(location.hash===next)renderRoute();else location.hash=next;}
function routeParams(){return new URLSearchParams(location.hash.split('?')[1]||'');}
function refreshHeader(){
  $('#account-nav').innerHTML=icon('user')+e(state.user?nameOf(state.user.full_name):'Đăng nhập');
  $('#cart-count').textContent=state.cart.reduce((n,x)=>n+x.quantity,0);
  const count=state.notices.filter(n=>!n.is_read).length;$('#notice-count').textContent=count;$('#notice-count').hidden=!count;
  $('#demo-strip').hidden=!state.demo;$('#demo-toolbar').hidden=!state.demo;
  $('#debug-toggle').checked=state.debug;$('#profile-switch').value=state.user&&state.profiles.some(p=>p.id===state.user.id)?state.user.id:'';
}
async function refreshUser(){
  const version=++state.userVersion;
  const current=await api('/auth/me');if(version!==state.userVersion)return;
  if(current.user){const results=await Promise.all([api('/cart'),api('/account/notifications'),api('/account/wishlist')]);if(version!==state.userVersion)return;state.cart=results[0].items;state.notices=results[1];state.wishlist=new Set(results[2].map(x=>x.id));}
  else{state.cart=[];state.notices=[];state.wishlist=new Set();}
  state.user=current.user;state.demo=current.demo_mode;refreshHeader();
}
function labScoresHTML(){
  const result=state.labResult||state.recommendations;
  if(!result?.items?.length)return '';
  return `<div class="container lab-results"><h3>Điểm gốc của lần gợi ý gần nhất · ${e(result.meta.touchpoint)}</h3><p class="debug-note">${state.native?'Điểm checkpoint giữ nguyên. Bản commerce có bộ lọc loại hàng và bỏ thẻ trùng ảnh; thứ tự giảm dần trong tập còn lại. presentation_policy=original trả danh sách ID gốc.':'Thứ tự hiển thị kết hợp điểm model, hành vi gần đây và quy tắc thương mại.'} P(click) và cosine không được quy đổi thành phần trăm phù hợp. Thay đổi danh sách sau chọn nhu cầu không phải phép đo độ chính xác.</p><div class="lab-table-scroll"><table class="lab-score-table"><thead><tr><th>Vị trí</th><th>Sản phẩm</th><th>Raw item ID</th><th>P(click) / cosine</th></tr></thead><tbody>${result.items.slice(0,6).map((p,index)=>`<tr><td>${index+1}</td><td>${e(nameOf(p.name))}</td><td><code>${e(p.raw_item_id)}</code></td><td class="product-score">${p.p_click!=null?p.p_click.toFixed(7):p.similarity!=null?p.similarity.toFixed(6):'Popularity fallback'}</td></tr>`).join('')}</tbody></table></div></div>`;
}
const percent = value => new Intl.NumberFormat('vi-VN',{maximumFractionDigits:2}).format(value)+'%';
function recommendationExplanation(result,compact=false){
  if(state.native)return nativeExplanation(result,compact);
  state.recommendationContexts[result.meta.touchpoint]=result;
  return '';
}
function aiInfo(el){
  if(state.native)return nativeAIInfo(el);
  const context=el?.closest('.ai-explanation')?.dataset.touchpoint;
  const result=state.recommendationContexts[context]||state.recommendations,quality=result?.quality;
  openModal('AI gợi ý như thế nào?',`<div class="help-prose"><h3>Học từ hoạt động mua sắm</h3><p>Khi bạn đăng nhập, hệ thống dùng mô hình AI để xếp hạng sản phẩm dựa trên lịch sử xem, yêu thích và giỏ hàng. Sở thích vừa chọn cùng các điều kiện về danh mục, giá, tồn kho và vận chuyển cũng ảnh hưởng đến danh sách cuối cùng.</p><h3>Kết quả kiểm thử</h3>${quality?.available?`<p>Trên <b>${new Intl.NumberFormat('vi-VN').format(quality.sample_size)} lượt hiển thị</b> lấy mẫu từ ${quality.sampled_shards} phần dữ liệu thử nghiệm gốc, mô hình xếp món được nhấp cao hơn món không được nhấp trong <b>${percent(quality.pairwise_ranking_percent)}</b> cặp so sánh (cặp bằng điểm được tính một nửa).</p><p>Con số này đo khả năng xếp hạng trên dữ liệu thử nghiệm; không có nghĩa là ${percent(quality.pairwise_ranking_percent)} sản phẩm phù hợp với mọi người hoặc chắc chắn sẽ được nhấp.</p>`:'<p>Chưa có kết quả đánh giá phù hợp với phiên bản AI đang dùng trong lần gợi ý này. Hệ thống không hiển thị phần trăm ước đoán.</p>'}<h3>Hiểu đúng bản trải nghiệm</h3><p>Dữ liệu thử nghiệm là dữ liệu mua sắm gốc. Tên, ảnh và ngành hàng tiếng Việt ở đây phục vụ minh họa. Chưa có nhãn phản hồi mua sắm tiếng Việt để xác định tỷ lệ gợi ý đúng trên danh mục này.</p><p>Nếu AI tạm thời không khả dụng, bạn vẫn nhận được gợi ý theo danh mục và sản phẩm nổi bật; trạng thái này được ghi rõ ngay tại khu vực gợi ý.</p></div>`,true);
}
function labEvaluationHTML(report){
  if(!report?.metrics)return '<p class="debug-note">Chưa có đánh giá hợp lệ cho checkpoint và mã suy luận hiện tại. Chạy scripts/evaluate_recommender.py để đo lại.</p>';
  const m=report.metrics;
  const value=x=>x==null?'—':Number(x).toFixed(6);
  return `<div class="container lab-evaluation"><h3>Đánh giá lại checkpoint · ${e(date(report.evaluated_at))}</h3><div class="debug-metrics"><div><span>AUC / GAUC</span>${value(m.auc)} / ${value(m.gauc)}</div><div><span>TEST IMPRESSIONS / USERS</span>${m.sample_size} / ${m.users}</div><div><span>LOG LOSS / CTR BASELINE</span>${value(m.log_loss)} / ${value(m.constant_ctr_log_loss)}</div><div><span>ACCURACY @0.5 / NO-CLICK BASELINE</span>${percent(m.accuracy*100)} / ${percent(m.always_no_click_accuracy*100)}</div><div><span>PRECISION / RECALL @0.5</span>${percent(m.precision*100)} / ${percent(m.recall*100)}</div><div><span>BALANCED ACCURACY / P@10 LIFT</span>${percent(m.balanced_accuracy*100)} / ${m.precision_at_10_lift==null?'—':m.precision_at_10_lift.toFixed(2)+'×'}</div></div><p class="debug-note">Lấy mẫu ${report.sampling.shards.length} test shards, seed ${report.sampling.seed}; dùng nhãn và lịch sử gốc, không dùng hành vi web hay ưu tiên danh mục demo. AUC là khả năng xếp thứ tự cặp, không phải tỷ lệ gợi ý đúng trên phiên mua sắm thực tế. GAUC chỉ gồm ${m.gauc_eligible_users} user có cả hai nhãn; P@10 chỉ gồm ${m.precision_at_10_eligible_users} user có ít nhất 20 ứng viên. Chưa đánh giá toàn tập test hoặc toàn bộ lớp xếp hạng thương mại.</p></div>`;
}
async function refreshDebug(meta){
  const version=++state.debugVersion,userId=state.user?.id;const panel=$('#debug-panel');panel.hidden=!(state.debug&&state.demo);
  if(panel.hidden){panel.replaceChildren();return;}
  if(!state.user){panel.innerHTML='<div class="container">MUSE Lab / Chọn một hồ sơ demo để xem chuỗi hành vi và kết quả suy luận.</div>';return;}
  try{
    const info=await api('/recommendations/debug');if(version!==state.debugVersion||userId!==state.user?.id||!state.debug)return;state.debugInfo=info;
    const m=meta||info.last_metrics||{};
    panel.innerHTML=`<div class="container"><div class="debug-top"><strong>● MUSE INFERENCE CONSOLE <span class="badge">${info.ready?'CHECKPOINT LOADED':'FALLBACK'}</span></strong><div class="debug-actions"><button data-action="muse-info">${icon('sparkles')} Kiến trúc mô hình</button><button data-action="history">${icon('code')} Soi lịch sử chuỗi 1K</button></div></div><div class="debug-metrics"><div><span>ACTIVE USER / RAW TAOBAO ID</span>#${e(info.user_id)} / ${e(info.raw_user_id||'Cold start')}</div><div><span>HISTORY / GSU</span>${e(m.history_length??Math.min(info.history_count,1000))} hành vi · top-${e(info.gsu_top_k||'—')}</div><div><span>INFERENCE / SERVICE</span>${e(m.inference_ms??'—')} ms / ${e(m.latency_ms??'—')} ms</div><div><span>CANDIDATES / SCL COVERAGE</span>${e(m.candidate_count??'—')} / ${m.scl_coverage!=null?Math.round(m.scl_coverage*100)+'%':'—'}</div><div><span>ENGINE</span>${e(m.engine||info.engine)}</div></div><p class="debug-note">${e(m.strategy||'GSU → SimTier + SA-TA → ESU')} · Lọc ngữ cảnh: ${e(m.context_policy||'—')} · ${state.native?'Điểm MUSE giữ nguyên; commerce lọc loại hàng và bỏ ảnh trùng':'Giãn thẻ trùng ảnh/ngành hàng; giữ nguyên điểm model'} · Raw ID được giữ dạng chuỗi 64-bit.</p><p class="debug-note">${state.native?'ID, nhóm và chuỗi lịch sử lấy từ Taobao gốc. Tên, ảnh, ngành hàng và giá minh họa từ DummyJSON được gắn riêng; không phục hồi metadata Taobao hay xác nhận độ phù hợp ngữ nghĩa.':'Tên tiếng Việt, ngành hàng, giá và ảnh là dữ liệu thương mại minh họa; không phải metadata gốc Taobao.'} Báo cáo huấn luyện cũ: AUC 0.644728 / GAUC 0.614794; kết quả đo lại nằm bên dưới. ${info.error?e(info.error):''}</p></div>`;panel.insertAdjacentHTML('beforeend',labEvaluationHTML(info.evaluation)+labScoresHTML());hydrate();
  }catch(err){if(version===state.debugVersion&&userId===state.user?.id)panel.textContent=err.message;}
}
function productCard(p,rank=null){
  if(state.native)return nativeProductCard(p,rank);
  const rankLabel='';
  const aiBadge='';
  const labBadge=(state.debug&&state.demo)?`<div class="lab-item-badge" style="margin:4px 8px 2px;padding:3px 6px;background:#f8fafc;border:1px dashed #94a3b8;border-radius:4px;font-family:monospace;font-size:11px;color:#334155;text-align:left;line-height:1.3;"><div><b style="color:#2563eb;">Mã ID:</b> ${e(p.raw_item_id||p.id)}</div>${p.p_click!==undefined?`<div><b style="color:#059669;">P(click):</b> ${p.p_click.toFixed(4)}</div>`:p.similarity!==undefined?`<div><b style="color:#d97706;">Cosine:</b> ${p.similarity.toFixed(4)}</div>`:''}</div>`:'';
  return `<article class="product-card " data-category="${p.category_id}"><button class="heart-button ${state.wishlist.has(p.id)?'saved':''}" data-action="favorite" data-id="${p.id}" aria-label="${state.wishlist.has(p.id)?'Bỏ yêu thích':'Yêu thích sản phẩm'}">${icon('heart')}</button><button class="product-card-main" data-action="product" data-id="${p.id}"><div class="product-image"><img loading="lazy" src="${e(p.image_url)}" alt="${e(nameOf(p.name))}">${p.is_mall?'<span class="mall-tag">Mall</span>':''}<span class="discount">−${e(p.discount_percent)}%</span>${rankLabel}${aiBadge}</div><div class="product-info"><h3 class="product-name">${e(nameOf(p.name))}</h3><div class="product-promos">${p.is_freeship?'<span class="free-tag">Freeship Xtra</span>':''}<span>${p.price_tier_match?'Hợp túi tiền':'Giá tốt mỗi ngày'}</span></div><div class="product-prices"><span class="price"><small>₫</small>${money(p.price).replace('₫','')}</span><span class="old-price">${compact(p.original_price)}</span></div><div class="product-meta"><span><span class="stars">★</span> ${e(p.rating_star)}</span><span>Đã bán ${compact(p.sold_count)}</span></div><div class="product-location">${icon('pin')}${e(shortProvince(p.province_name))}</div></div></button>${labBadge}${(state.debug&&state.demo)&&p.recommendation_reason?`<p class="recommendation-reason">${icon('sparkles')} ${e(p.recommendation_reason)}</p>`:''}<button class="quick-add" data-action="quick-add" data-id="${p.id}">${icon('cart')} Thêm vào giỏ</button></article>`;
}
function productGrid(items,ranked=false){return `<div class="product-grid">${items.map((p,index)=>productCard(p,ranked?index+1:null)).join('')}</div>`;}


function homeCategoryTabsHTML(){
  const activeCat=state.homeCategoryFilter||0;
  return `<div class="muse-feed-tabs" role="tablist" aria-label="Lọc gợi ý theo ngành hàng"><button type="button" class="muse-feed-tab ${!activeCat?'active':''}" data-action="home-cat-tab" data-category-id="">Tất cả</button>${state.categories.map((c,i)=>`<button type="button" class="muse-feed-tab ${activeCat===c.id?'active':''}" data-action="home-cat-tab" data-category-id="${c.id}">${icon(categoryIcons[c.id-1]||categoryIcons[i]||'sparkles')} ${e(categoryNames[c.id-1]||c.name)}</button>`).join('')}</div>`;
}

const categoryIcons=['laptop','headphones','shirt','dress','shoe','appliance','beauty','watch','laptop','sparkles','shoe'];
const categoryNames=['Laptop & Máy tính','Âm thanh & Phụ kiện','Thời trang nam','Thời trang nữ','Giày dép','Nhà cửa & Đời sống','Sắc đẹp','Phụ kiện & Đồng hồ','Điện thoại & Tablet','Đồ chơi & Mẹ bé','Thể thao & Dã ngoại'];
const heroes=[
  {eye:'EVERYDAY, A LITTLE MORE YOU',title:'Mua sắm dễ dàng.<br><em>Ưu đãi mỗi ngày.</em>',copy:'Khám phá những lựa chọn mới cho công nghệ, thời trang và cuộc sống.',img:'/static/images/catalog/50867512f65f1c41.jpg',search:'tai nghe',sticker:'ĐẾN',amount:'50%',button:'Khám phá ngay'},
  {eye:'YOUR NEW EVERYDAY ESSENTIALS',title:'Phong cách của bạn.<br><em>Cảm hứng bất tận.</em>',copy:'Làm mới tủ đồ với những lựa chọn vừa vặn cho mỗi khoảnh khắc.',img:'/static/images/catalog/c05ce10bc673f2bd.jpg',search:'giày',sticker:'ƯU ĐÃI',amount:'40%',button:'Tìm phong cách mới'},
  {eye:'MAKE ROOM FOR LITTLE JOYS',title:'Nhà thêm ấm.<br><em>Ngày thêm vui.</em>',copy:'Những món đồ nhỏ làm nên một không gian sống đầy cảm hứng.',img:'/static/images/catalog/1d2b90e9593ea950.jpg',search:'máy',sticker:'TIẾT KIỆM',amount:'35%',button:'Khám phá tổ ấm'}
];
function heroHTML(){const h=heroes[state.hero];return `<div class="hero-copy"><div class="eyebrow">${h.eye}</div><h1>${h.title}</h1><p>${h.copy}</p><button class="primary" data-search="${e(h.search)}">${h.button} ${icon('arrow')}</button></div><div class="hero-art"><div class="hero-circle"></div><img src="${h.img}" alt="Cảm hứng mua sắm"><div class="hero-sticker">${h.sticker}<b>${h.amount}</b></div></div><div class="hero-pagination">${heroes.map((_,i)=>`<button class="${i===state.hero?'active':''}" data-action="hero" data-index="${i}" aria-label="Ưu đãi ${i+1}"></button>`).join('')}</div>`;}
async function renderHome(version){
  if(state.native)return renderNativeHome(version);
  appHTML(`<div class="container page"><div class="welcome-line"><span>${icon('sparkles')} ${state.user?`Chào ${e(nameOf(state.user.full_name).split(' ').slice(-1))}, <b>hôm nay bạn muốn tìm gì?</b>`:'Mỗi ngày một khám phá. <b>Mỗi lựa chọn đều là bạn.</b>'}</span><small>CHỌN ĐIỀU BẠN YÊU · MUA ĐIỀU BẠN THÍCH</small></div><div class="hero-layout"><section class="hero" id="hero">${heroHTML()}</section><div class="side-promos"><article class="promo promo-one"><div><small>HOME, SWEET HOME</small><h3>Chút mới mẻ.<br>Nhiều an yên.</h3><p>Góc nhà nhỏ, cảm hứng lớn.</p><button data-category="6">Khám phá ${icon('arrow')}</button></div><img src="/static/images/catalog/1d2b90e9593ea950.jpg" alt="Cà phê cho không gian sống"></article><article class="promo promo-two"><div><small>LOVE YOUR EVERYDAY</small><h3>Đẹp theo cách<br>của riêng bạn.</h3><p>Chăm chút những điều nhỏ.</p><button data-category="7">Yêu chiều bản thân ${icon('arrow')}</button></div><img src="/static/images/catalog/42b2f8a7cabd17ed.jpg" alt="Chăm sóc da mỗi ngày"></article></div></div><div class="benefit-strip"><div class="benefit">${icon('truck')}<div><strong>Miễn phí vận chuyển</strong><small>Từ 150.000₫ tại mỗi shop</small></div></div><div class="benefit">${icon('shield')}<div><strong>Yên tâm mua sắm</strong><small>Thông tin đơn hàng minh bạch</small></div></div><div class="benefit">${icon('ticket')}<div><strong>Ưu đãi mỗi ngày</strong><small>Voucher dành riêng cho bạn</small></div></div><div class="benefit">${icon('sparkles')}<div><strong>Gợi ý dành cho bạn</strong><small>Theo sở thích mua sắm của bạn</small></div></div></div><section class="section"><div class="section-title"><h2>Khám phá theo danh mục</h2><button data-action="catalog">Tất cả danh mục ${icon('arrow')}</button></div><div class="category-list">${state.categories.map((c,i)=>`<button class="category" data-category="${c.id}"><span class="category-icon">${icon(categoryIcons[c.id-1]||categoryIcons[i]||'sparkles')}</span><span>${categoryNames[c.id-1]||c.name}</span><small>${compact(c.product_count)} sản phẩm</small></button>`).join('')}</div></section><section class="section flash"><div class="section-title"><div class="flash-heading"><h2>⚡ FLASH SALE</h2><p>Ưu đãi đang giảm giá, ưu tiên những nhóm hàng bạn hay xem</p></div><button data-action="flash">Xem tất cả ưu đãi ${icon('arrow')}</button></div><div class="flash-grid" id="flash-grid"></div></section><section class="section" id="discovery"><div class="section-title recommend-title"><div><h2>Gợi ý hôm nay</h2><p>${state.user?'Sản phẩm gợi ý theo sở thích mua sắm của bạn':'Đăng nhập để khám phá gợi ý phù hợp nhất với bạn'}</p></div></div><div id="home-cat-tabs">${homeCategoryTabsHTML()}</div><div id="home-products"><div class="skeleton-grid">${Array(6).fill('<div class="skeleton"></div>').join('')}</div></div><div class="load-more"><button data-action="home-more">Xem thêm gợi ý ${icon('arrow')}</button></div></section><div class="quick-vouchers"><button class="mini-voucher" data-action="vouchers">${icon('truck')}<span><strong>Freeship đến 50.000₫</strong><small>Lưu mã, thêm niềm vui mua sắm</small></span><span>›</span></button><button class="mini-voucher" data-action="vouchers">${icon('ticket')}<span><strong>Voucher giảm đến 20%</strong><small>Ưu đãi dành cho thành viên</small></span><span>›</span></button><button class="mini-voucher" data-action="vouchers">${icon('bag')}<span><strong>Chào bạn mới · Giảm 30k</strong><small>Khởi đầu nhỏ, ưu đãi lớn</small></span><span>›</span></button></div></div>`);
  const catParam=state.homeCategoryFilter?'&category_id='+state.homeCategoryFilter:'';
  const [deals,recs]=await Promise.all([
    api('/recommendations/deals?limit=6').catch(()=>api('/offers')),
    api('/recommendations?limit='+state.homeLimit+catParam)
  ]);
  if(version!==state.routeVersion)return;
  const flashItems=(deals&&deals.items&&deals.items.length)?deals.items:[];
  $('#flash-grid').innerHTML=flashItems.slice(0,6).map((p,i)=>`<article class="flash-card"><button class="product-card-main" data-action="product" data-id="${p.id}" aria-label="${e(nameOf(p.name))}"><div class="flash-img"><img loading="lazy" src="${e(p.image_url)}" alt="${e(nameOf(p.name))}"><span class="discount">−${p.discount_percent}%</span></div><strong class="price">${money(p.price)}</strong><div class="sale-progress"><span>Đã bán ${compact(p.sold_count)} · chính hãng</span></div></button></article>`).join('');
  state.recommendations=recs;state.labResult=recs;
  $('#home-products').innerHTML=productGrid(recs.items,true);updateRecommendationLabel(recs.meta);
  hydrate();refreshDebug(recs.meta);
}
function updateRecommendationLabel(meta){
  if(state.native)return nativeRecommendationLabel(meta);
  const title=$('#discovery .recommend-title p');
  const catFilterName=state.homeCategoryFilter?(categoryNames[state.homeCategoryFilter-1]||''):'';
  if(title)title.textContent=catFilterName?`Sản phẩm nổi bật trong ${catFilterName}`:state.user?'Được sắp xếp theo hoạt động mua sắm gần đây của bạn':'Khám phá những sản phẩm nổi bật trong cửa hàng';
  const tabs=$('#home-cat-tabs');if(tabs)tabs.innerHTML=homeCategoryTabsHTML();
  const more=$('[data-action="home-more"]');if(more)more.hidden=!meta.has_more||state.homeLimit>=60;
}
async function renderCatalog(version){
  if(state.native)return renderNativeCatalog(version);
  const params=routeParams();const category=Number(params.get('category_id'));const q=params.get('q')||'';
  const title=q?`Kết quả cho “${q}”`:category?(categoryNames[category-1]||'Khám phá sản phẩm'):'Khám phá sản phẩm';
  const sort=params.get('sort')||(q?'relevance':'popular');const page=Number(params.get('page')||1);
  appHTML(`<div class="container page">${breadcrumb(title)}<h1 class="page-title">${e(title)}</h1><p class="page-subtitle">Tìm món đồ phù hợp, theo cách của bạn.</p><div class="catalog-layout"><aside class="filter-panel"><h3>${icon('filter')} Bộ lọc tìm kiếm</h3><div class="filter-categories"><button data-action="catalog" class="${!category?'active':''}">Tất cả sản phẩm</button>${state.categories.map((c,i)=>`<button data-category="${c.id}" class="${category===c.id?'active':''}">${categoryNames[c.id-1]||c.name}</button>`).join('')}</div><form id="filter-form"><div class="filter-group"><label>Khoảng giá (₫)</label><input type="number" name="min_price" min="0" placeholder="Từ" aria-label="Giá từ" value="${e(params.get('min_price')||'')}"><input type="number" name="max_price" min="0" placeholder="Đến" aria-label="Giá đến" value="${e(params.get('max_price')||'')}"></div><div class="filter-group"><label for="province-filter">Nơi bán</label><select id="province-filter" name="province_id"><option value="">Tất cả tỉnh thành</option>${provinceOptions(params.get('province_id'))}</select><button class="primary" type="submit">Áp dụng bộ lọc</button></div></form><button class="auth-link" data-action="clear-filter">Xóa bộ lọc</button></aside><div><div class="sort-bar"><span>Sắp xếp theo</span>${[['relevance','Phù hợp nhất'],['popular','Phổ biến'],['newest','Mới nhất'],['sold','Bán chạy'],['discount','Ưu đãi']].map(([s,t])=>`<button class="${s===sort?'active':''}" data-sort="${s}">${t}</button>`).join('')}<select id="price-sort" aria-label="Sắp xếp theo giá"><option value="">Giá</option><option value="price_asc" ${sort==='price_asc'?'selected':''}>Thấp đến cao</option><option value="price_desc" ${sort==='price_desc'?'selected':''}>Cao đến thấp</option></select><small class="result-count" id="result-count"></small></div><div id="catalog-ai-banner"></div><div id="catalog-products"><div class="skeleton-grid">${Array(6).fill('<div class="skeleton"></div>').join('')}</div></div><div class="pagination" id="pagination"></div><section class="section" id="catalog-ai-expansion" hidden style="margin-top:32px"><div class="section-title"><div><h2>Có thể bạn cũng thích</h2></div></div><div id="catalog-expansion-grid"></div></section></div></div></div>`);
  const query=new URLSearchParams(params);query.set('page_size','24');if(!params.has('sort'))query.set('sort',sort);
  const result=await api('/products?'+query);if(version!==state.routeVersion)return;state.products=result;
  if(false&&result.personalized&&$('#catalog-ai-banner')){
    $('#catalog-ai-banner').innerHTML=`<div class="ai-explanation compact" data-ai-used="true"><span class="ai-explanation-icon">${icon('sparkles')}</span><div><strong>Kết quả được sắp xếp theo sở thích của bạn</strong><p>Các sản phẩm khớp từ khóa được ưu tiên dựa trên lịch sử xem và mua của bạn.</p></div></div>`;
  }
  $('#catalog-products').innerHTML=result.items.length?productGrid(result.items):empty('Chưa tìm thấy sản phẩm','Thử từ khóa khác hoặc điều chỉnh bộ lọc.','catalog','Xem tất cả sản phẩm','search');
  $('#result-count').textContent=result.total.toLocaleString('vi-VN')+' kết quả';
  const first=Math.max(1,Math.min(page-2,result.pages-4));const pages=Array.from({length:Math.min(5,result.pages)},(_,i)=>first+i);
  $('#pagination').innerHTML=result.pages>1?`<button data-page="${page-1}" ${page<=1?'disabled':''} aria-label="Trang trước">‹</button>${pages.map(p=>`<button data-page="${p}" class="${p===page?'active':''}">${p}</button>`).join('')}<button data-page="${page+1}" ${page>=result.pages?'disabled':''} aria-label="Trang sau">›</button>`:'';hydrate();
}
function updateCatalogParams(changes){const params=routeParams();for(const [key,value] of Object.entries(changes)){if(value==null||value==='')params.delete(key);else params.set(key,value);}if(!('page'in changes))params.delete('page');navigate('catalog',Object.fromEntries(params));}
function provinceOptions(selected){return state.provinces.map(p=>`<option value="${p.id}" ${Number(selected)===p.id?'selected':''}>${e(p.name)}</option>`).join('');}
async function openProduct(id){
  if(state.native)return openNativeProduct(id);
  const version=++state.modalVersion;openModal('Chi tiết sản phẩm','<div class="loading-screen"><div class="spinner"></div></div>');
  const p=await api('/products/'+id);if(version!==state.modalVersion)return;state.selectedProduct=p;state.quantity=1;
  openModal('Chi tiết sản phẩm',`<div class="product-detail"><div><div class="detail-image"><img src="${e(p.image_url)}" alt="${e(nameOf(p.name))}"></div><div class="detail-thumbs"><img src="${e(p.image_url)}" alt="Ảnh sản phẩm"></div></div><div><h1 class="detail-title">${p.is_mall?'<span class="badge">Mall</span>':''}${e(nameOf(p.name))}</h1><div class="detail-rating"><span class="stars">★ ${p.rating_star}</span><span>${compact(p.rating_count)} đánh giá mẫu</span><span>${compact(p.sold_count)} đã bán mẫu</span></div><div class="detail-pricing"><span class="old-price">${money(p.original_price)}</span><strong class="price">${money(p.price)}</strong><span class="badge">GIẢM ${p.discount_percent}%</span></div><div class="detail-line"><span>Ưu đãi</span><div>${p.is_freeship?'<span class="badge">Freeship Xtra</span><p>Từ 150.000₫ tại shop khi tất cả món đã chọn hỗ trợ.</p>':'<p>Phí vận chuyển theo địa chỉ nhận hàng.</p>'}</div></div><div class="detail-line"><span>Vận chuyển</span><div>${icon('truck')} Gửi từ ${e(shortProvince(p.province_name))}<p>Phí giao hàng được tính khi chọn địa chỉ.</p></div></div><div class="detail-line"><span>Số lượng</span><div><div class="quantity"><button data-action="detail-minus" aria-label="Giảm số lượng">−</button><input id="detail-quantity" type="number" min="1" max="${Math.min(p.stock,99)}" value="1" aria-label="Số lượng mua"><button data-action="detail-plus" aria-label="Tăng số lượng">+</button></div><p>${p.stock} sản phẩm có sẵn</p></div></div><div class="detail-actions"><button class="outline" data-action="add-product" ${p.stock<=0?'disabled':''}>${icon('cart')} Thêm vào giỏ hàng</button><button class="primary" data-action="buy-product" ${p.stock<=0?'disabled':''}>${p.stock<=0?'Đã hết hàng':'Mua ngay'}</button></div><div class="detail-guarantee">${icon('shield')} Kiểm tra thông tin và tổng tiền trước khi đặt hàng</div></div></div><div class="detail-shop"><div><strong>${e(p.shop_name)}</strong><small>Gian hàng minh họa · ${e(shortProvince(p.province_name))}</small></div><button class="soft-button" data-shop="${e(p.shop_name)}">Xem cửa hàng ${icon('arrow')}</button></div><div class="detail-description"><h3>Thông tin sản phẩm</h3><p>${e(p.description||`${nameOf(p.name)}. Vui lòng kiểm tra thông tin sản phẩm và số lượng trước khi đặt hàng. Sản phẩm thuộc danh mục ${p.category_name}.`)}</p><p>Mã sản phẩm: SP${String(p.id).padStart(5,'0')} · Tồn kho và giá được kiểm tra lại khi đặt hàng.</p></div><div class="detail-description"><h3>Đánh giá từ người mua (${p.reviews.length})</h3>${p.reviews.length?p.reviews.map(r=>`<p><span class="stars">${'★'.repeat(r.rating)}</span> ${e(nameOf(r.full_name))} · ${e(date(r.created_at))}<br>${e(r.content)}</p>`).join(''):'<p>Chưa có đánh giá mua hàng xác thực. Các chỉ số đánh giá trên danh mục là dữ liệu mẫu.</p>'}</div><section class="detail-similar"><div class="detail-rec-header"><h3>Sản phẩm tương tự</h3></div><div id="similar-products"><div class="spinner"></div></div></section><section class="detail-similar" style="margin-top:24px"><div class="detail-rec-header"><h3>Có thể bạn cũng thích</h3></div><div id="complementary-products"><div class="spinner"></div></div></section>`);
  const infoParagraphs=document.querySelectorAll('#modal .detail-description p');if(infoParagraphs.length>1)infoParagraphs[1].remove();
  if(p.image_is_illustrative)$('#modal .detail-description').insertAdjacentHTML('beforeend','<p>Ảnh minh họa loại sản phẩm; vui lòng kiểm tra đúng mẫu, màu và phiên bản trước khi chọn mua.</p>');
  const detailHeadings=document.querySelectorAll('#modal .detail-rec-header h3');if(detailHeadings[1])detailHeadings[1].textContent='Mua kèm tiện hơn';
  if(state.user){await post('/recommendations/behavior/'+id);if(version!==state.modalVersion)return;state.lastInteraction={category_name:p.category_name,product_name:nameOf(p.name)};}
  const [relatedResult,compResult]=await Promise.allSettled([
    api('/recommendations?touchpoint=similar&product_id='+id+'&limit=6'),
    api('/recommendations?touchpoint=complementary&product_id='+id+'&limit=6')
  ]);
  if(version!==state.modalVersion)return;
  const related=relatedResult.status==='fulfilled'?relatedResult.value:null;
  const comp=compResult.status==='fulfilled'?compResult.value:null;
  const retry=`<p class="page-subtitle" role="alert">Chưa tải được sản phẩm. <button class="auth-link" data-action="product" data-id="${id}">Thử lại</button></p>`;
  const target=$('#similar-products');if(target){if(related)state.labResult=related;target.innerHTML=related?recommendationExplanation(related,true)+(related.items.length?productGrid(related.items):'<p class="page-subtitle">Chưa có mẫu khác cùng loại trong khoảng giá phù hợp.</p>'):retry;}
  const compTarget=$('#complementary-products');if(compTarget){compTarget.innerHTML=comp?recommendationExplanation(comp,true)+(comp.items.length?productGrid(comp.items):'<p class="page-subtitle">Chưa có phụ kiện phù hợp cho sản phẩm này.</p>'):retry;}
  hydrate();refreshDebug(related?.meta||comp?.meta);
}
async function refreshHomeRecommendations(){
  if(state.route!=='home')return;
  const version=state.routeVersion,userId=state.user?.id,request=++state.recsVersion;
  const before=state.recommendations?.items||[];
  if(state.native){if(state.nativeChange?.failed){state.nativeChange.failed=false;state.nativeChange.pending=true;renderNativeContext();}nativeUpdating(true);}
  const catParam=(!state.native&&state.homeCategoryFilter)?'&category_id='+state.homeCategoryFilter:'';
  let result;try{result=await api('/recommendations?limit='+state.homeLimit+catParam+(state.native&&state.homeGroup?'&category_id='+state.homeGroup:'')+(state.storefront&&state.homeDisplayCategory?'&display_category='+encodeURIComponent(state.homeDisplayCategory):''));}catch(error){if(version===state.routeVersion&&userId===state.user?.id&&request===state.recsVersion&&state.native){if(state.nativeChange?.pending){state.nativeChange.pending=false;state.nativeChange.failed=true;renderNativeContext();}if(state.storefront)state.storeRecFailure=true;nativeUpdating(false);updateRecommendationLabel(state.recommendations?.meta||{});}throw error;}
  if(version!==state.routeVersion||userId!==state.user?.id||request!==state.recsVersion)return;
  if(state.storefront)state.storeRecFailure=false;
  if(state.native)finishNativeComparison(result);
  state.recommendations=result;state.labResult=result;const target=$('#home-products');
  if(target){target.innerHTML=result.items.length?productGrid(result.items,true):state.storefront?storeEmptyProducts(result):empty('Chưa có mẫu khả dụng','Chọn nhóm khác để tiếp tục khám phá.','home','Xem mọi mẫu');updateRecommendationLabel(result.meta);hydrate();}
  if(state.native){nativeUpdating(false);refreshNativeEvidence();}
  await refreshDebug(result.meta);
}

async function addProduct(buy=false){
  if(state.addingProduct)return;const p=state.selectedProduct;if(!p)return;
  const quantity=Number($('#detail-quantity')?.value||state.quantity);
  if(!Number.isInteger(quantity)||quantity<1||quantity>Math.min(p.stock,99))throw new Error('Vui lòng chọn số lượng hợp lệ.');
  if(!state.user){state.pendingIntent={product_id:p.id,quantity,buy};openAuth();return;}
  if(buy){state.checkoutKey=null;navigate('checkout',{product_id:p.id,quantity});return;}
  state.addingProduct=true;
  try{if(state.native)captureNativeInteraction(p,'add_to_cart');await post('/cart',{product_id:p.id,quantity});await refreshUser();toast('Đã thêm sản phẩm vào giỏ hàng.');}
  finally{state.addingProduct=false;}
}
function accountSidebar(active){return `<aside class="account-sidebar"><div class="account-avatar">${state.user.avatar_url?`<img src="${e(state.user.avatar_url)}" alt="Ảnh đại diện">`:`<span class="avatar-letter">${e(nameOf(state.user.full_name).at(0))}</span>`}<div><strong>${e(nameOf(state.user.full_name))}</strong><small>Hạng ${e(state.user.member_tier)}</small></div></div>${[['account','user','Hồ sơ của tôi'],['orders','bag','Đơn mua'],['addresses','pin','Sổ địa chỉ'],['vouchers','ticket','Kho voucher'],['wishlist','heart','Đã yêu thích'],['notifications','bell','Thông báo'],['password','lock','Đổi mật khẩu'],['logout','logout','Đăng xuất']].map(([r,i,t])=>`<button class="${active===r?'active':''}" data-action="${r}">${icon(i)}${t}</button>`).join('')}</aside>`;}
function accountPage(title,subtitle,html,active){return `<div class="container page">${breadcrumb(title)}<div class="account-layout">${accountSidebar(active)}<div class="content-card"><div class="card-title"><div><h2>${e(title)}</h2><p>${e(subtitle)}</p></div>${active==='addresses'?'<button class="primary" data-action="new-address">+ Thêm địa chỉ</button>':''}</div>${html}</div></div></div>`;}
async function renderAccount(version){
  const u=state.user;const avatars=await api('/account/avatar-options');if(version!==state.routeVersion)return;appHTML(accountPage('Hồ sơ của tôi','Quản lý thông tin để mua sắm thuận tiện hơn.',`<div class="wallet-grid"><div class="wallet-card"><span>${state.demo?'Ví trải nghiệm · MÔ PHỎNG':'Số dư ví'}</span><strong>${money(u.wallet_balance)}</strong><small>${state.demo?'Số dư mô phỏng, không có giá trị thanh toán thật.':'Kết nối ví thanh toán chưa được cấu hình.'}</small></div><div class="wallet-card"><span>Xu trải nghiệm</span><strong>${new Intl.NumberFormat('vi-VN').format(u.shopee_coins)} Xu</strong><small>Sử dụng tối đa 25.000 Xu cho mỗi đơn demo.</small></div></div><form id="profile-form" class="profile-form"><div class="field"><label for="profile-avatar">Ảnh đại diện</label><select id="profile-avatar" name="avatar_url"><option value="${e(u.avatar_url||'')}">Giữ ảnh hiện tại</option>${avatars.map(a=>`<option value="${e(a.url)}">${e(a.label)}</option>`).join('')}</select></div><div class="field"><label>Email</label><input type="email" value="${e(u.email)}" disabled></div><div class="field"><label for="profile-name">Họ và tên</label><input id="profile-name" name="full_name" value="${e(u.full_name)}" required minlength="2" maxlength="100"></div><div class="field"><label for="profile-phone">Số điện thoại</label><input id="profile-phone" name="phone" value="${e(u.phone)}" required pattern="0[0-9]{9}" inputmode="tel"></div><div class="field-row"><div class="field"><label for="profile-gender">Giới tính</label><select id="profile-gender" name="gender">${['Nam','Nữ','Khác'].map(s=>`<option ${u.gender===s?'selected':''}>${s}</option>`).join('')}</select></div><div class="field"><label for="profile-year">Năm sinh</label><input id="profile-year" name="birth_year" type="number" min="1900" max="2026" value="${e(u.birth_year||'')}"></div></div><button class="primary" type="submit">Lưu thay đổi</button></form>`,'account'));
}
async function renderAddresses(version){const rows=await api('/account/addresses');if(version!==state.routeVersion)return;state.addresses=rows;appHTML(accountPage('Địa chỉ của tôi','Chọn địa chỉ mặc định cho lần mua hàng tiếp theo.',rows.length?rows.map(a=>`<article class="address-card"><div><h3>${e(a.recipient_name)} <span class="old-price">|</span> ${e(a.phone)}</h3><p>${e(a.detail)}<br>${e(a.province_name)}</p>${a.is_default?'<span class="default-tag">Mặc định</span>':''}</div><div class="address-actions"><button data-action="edit-address" data-id="${a.id}">Cập nhật</button><button data-action="delete-address" data-id="${a.id}">Xóa</button></div></article>`).join(''):empty('Thêm địa chỉ đầu tiên','Lưu địa chỉ để thanh toán nhanh hơn.','new-address','Thêm địa chỉ','pin'),'addresses'));}
async function openAddress(id=null){
  if(!requireLogin())return;const addresses=await api('/account/addresses');const a=addresses.find(x=>x.id===Number(id))||{};
  openModal(id?'Cập nhật địa chỉ':'Địa chỉ mới',`<form id="address-form" data-id="${a.id||''}"><div class="field"><label for="address-name">Họ và tên người nhận</label><input id="address-name" name="recipient_name" required minlength="2" maxlength="100" value="${e(a.recipient_name||state.user.full_name)}" autocomplete="name"></div><div class="field"><label for="address-phone">Số điện thoại</label><input id="address-phone" name="phone" required pattern="0[0-9]{9}" inputmode="tel" value="${e(a.phone||state.user.phone)}" autocomplete="tel"></div><div class="field"><label for="address-province">Tỉnh / Thành phố</label><select id="address-province" name="province_id" required><option value="">Chọn tỉnh thành</option>${provinceOptions(a.province_id)}</select></div><div class="field"><label for="address-detail">Địa chỉ cụ thể</label><textarea id="address-detail" name="detail" required minlength="8" maxlength="300" placeholder="Số nhà, tên đường, phường / xã" autocomplete="street-address">${e(a.detail||'')}</textarea></div><div class="field"><label for="address-label">Loại địa chỉ</label><select id="address-label" name="label"><option ${a.label==='Nhà riêng'?'selected':''}>Nhà riêng</option><option ${a.label==='Văn phòng'?'selected':''}>Văn phòng</option></select></div><label class="check-label"><input type="checkbox" name="is_default" ${a.is_default||!addresses.length?'checked':''}> Đặt làm địa chỉ mặc định</label><p class="error-text" id="form-error"></p><button class="primary" type="submit">${id?'Lưu thay đổi':'Thêm địa chỉ'}</button></form>`,true);
}
async function renderVouchers(version){const rows=await api('/vouchers');if(version!==state.routeVersion)return;appHTML(accountPage('Kho voucher','Lưu ưu đãi yêu thích và sử dụng khi thanh toán.',`<div class="voucher-grid">${rows.map(v=>`<article class="voucher-card"><div class="voucher-value">${icon(v.discount_type==='freeship'?'truck':'ticket')}<b>${v.discount_type==='percentage'?v.discount_value+'%':compact(v.discount_value)}</b></div><div class="voucher-detail"><strong>${e(v.title)}</strong><p>${e(v.description)}</p><p>HSD: ${e(v.end_date)} · ${e(v.code)}</p><button data-action="claim-voucher" data-id="${v.id}" ${v.status!=='unclaimed'?'disabled':''}>${v.status==='unclaimed'?'Lưu ngay':v.status==='used'?'Đã sử dụng':'Đã lưu'}</button></div></article>`).join('')}</div>`,'vouchers'));}
async function renderWishlist(version){const rows=await api('/account/wishlist');if(version!==state.routeVersion)return;appHTML(accountPage('Sản phẩm yêu thích','Những món đồ bạn muốn quay lại khám phá.',rows.length?productGrid(rows):empty('Chưa có sản phẩm yêu thích','Chạm vào trái tim trên sản phẩm để lưu lại.','catalog','Khám phá sản phẩm','heart'),'wishlist'));}
async function renderNotifications(version){const rows=await api('/account/notifications');if(version!==state.routeVersion)return;appHTML(accountPage('Thông báo của bạn','Đơn hàng và ưu đãi mới, tất cả ở một nơi.',rows.length?`<button class="auth-link" data-action="read-notifications">Đánh dấu tất cả đã đọc</button>${rows.map(n=>`<article class="notification ${n.is_read?'':'unread'}"><div class="notification-icon">${icon(n.type==='order'?'bag':n.type==='system'?'bell':'sparkles')}</div><div><h3>${e(n.title)}</h3><p>${e(n.content)}</p><time>${e(date(n.created_at))}</time></div></article>`).join('')}`:empty('Bạn đã cập nhật tất cả','Thông báo mới sẽ xuất hiện tại đây.','home','Tiếp tục khám phá','bell'),'notifications'));}
function renderPassword(){appHTML(accountPage('Đổi mật khẩu','Chọn mật khẩu từ 8 ký tự. Các phiên đăng nhập khác sẽ được kết thúc.',`<form id="password-form" class="profile-form"><div class="field"><label for="current-password">Mật khẩu hiện tại</label><input id="current-password" name="current_password" type="password" required autocomplete="current-password" maxlength="128"></div><div class="field"><label for="new-password">Mật khẩu mới</label><input id="new-password" name="new_password" type="password" required minlength="8" maxlength="128" autocomplete="new-password"></div><div class="field"><label for="confirm-password">Nhập lại mật khẩu mới</label><input id="confirm-password" name="confirm_password" type="password" required minlength="8" maxlength="128" autocomplete="new-password"></div><button class="primary" type="submit">Cập nhật mật khẩu</button></form>`,'password'));}
async function renderOrders(version){
  if(!state.user){
    requireLogin();
    appHTML(accountPage('Đơn mua','Theo dõi hành trình của những món đồ bạn yêu thích.',empty('Vui lòng đăng nhập','Đăng nhập để xem danh sách đơn mua của bạn.','login','Đăng nhập ngay','user'),'orders'));
    return;
  }
  const rows=await api('/orders');if(version!==state.routeVersion)return;state.orders=rows;
  const filtered=state.orderTab==='Tất cả'?rows:rows.filter(o=>o.order_status===state.orderTab);
  const latestItemName = (rows.length && rows[0].items && rows[0].items.length) ? nameOf(rows[0].items[0].product_name) : '';
  const recsHtml=rows.length?`<section class="section" id="order-recs-section" style="margin-top:28px"><div class="section-title"><div><h2>Phụ kiện & Đồ bổ trợ gợi ý <span class="badge">ĐI KÈM ĐƠN MUA</span></h2><p>${latestItemName ? `Phụ kiện và đồ dùng kèm phù hợp cho <strong>${e(latestItemName)}</strong> bạn vừa đặt mua:` : 'Chọn theo đơn mua gần đây và thói quen mua sắm của bạn.'}</p></div></div><div id="order-recommendations"><div class="spinner"></div></div></section>`:'';
  const html=`<div class="order-tabs">${['Tất cả','Chờ xác nhận','Đang giao','Đã giao','Đã hủy'].map(s=>`<button data-tab="${s}" class="${state.orderTab===s?'active':''}">${s}</button>`).join('')}</div>${filtered.length?filtered.map(o=>`<article class="order-card"><div class="order-card-top"><span>${e(o.order_code)} · ${e(date(o.created_at))}</span><strong>${e(o.order_status).toUpperCase()}</strong></div>${o.items.map(i=>`<div class="order-item"><img loading="lazy" src="${e(i.image_url||'/static/images/placeholder.svg')}" alt="${e(nameOf(i.product_name))}"><div><button data-action="product" data-id="${i.product_id}">${e(nameOf(i.product_name||'Sản phẩm #'+i.product_id))}</button><p>${e(i.shop_name)} · x${i.quantity}</p></div><span>${money(i.unit_price*i.quantity)}</span></div>`).join('')}<p class="form-help">Giao đến: ${e(o.recipient_name)}, ${e(o.shipping_address)}</p><div class="order-total">Thành tiền (${e(o.payment_method)}): <strong>${money(o.final_payment_amount)}</strong></div><div class="order-buttons">${o.order_status==='Chờ xác nhận'?`<button class="soft-button" data-action="cancel-order" data-id="${o.id}">Hủy đơn hàng</button>`:''}${state.demo&&['Chờ xác nhận','Đang giao'].includes(o.order_status)?`<button class="outline" data-action="advance-order" data-id="${o.id}">[Demo] ${o.order_status==='Chờ xác nhận'?'Chuyển sang đang giao':'Xác nhận đã giao'}</button>`:''}${o.order_status==='Đã giao'?`<button class="outline" data-action="review" data-id="${o.id}">Đánh giá</button>`:''}<button class="primary" data-action="reorder" data-id="${o.id}">Mua lại</button></div></article>`).join(''):empty('Chưa có đơn hàng ở đây','Lựa chọn đầu tiên của bạn đang chờ được khám phá.','catalog','Bắt đầu mua sắm','bag')}${recsHtml}`;
  appHTML(accountPage('Đơn mua','Theo dõi hành trình của những món đồ bạn yêu thích.',html,'orders'));
  if(rows.length&&rows[0].items&&rows[0].items.length){
    const targetPid=rows[0].items[0].product_id;
    await fillOptionalRecommendations('/recommendations?touchpoint=complementary&product_id='+targetPid+'&limit=18','#order-recommendations',version);
  }
}
async function renderCart(version){
  const result=await api('/cart');if(version!==state.routeVersion)return;state.cart=result.items;refreshHeader();
  if(!state.cart.length){appHTML(`<div class="container page">${breadcrumb('Giỏ hàng')}<h1 class="page-title">Giỏ hàng của bạn</h1><p class="page-subtitle">Thêm một chút niềm vui vào ngày mới.</p>${empty('Giỏ hàng đang chờ bạn','Khám phá những món đồ phù hợp với sở thích của bạn.','catalog','Tiếp tục mua sắm','cart')}</div>`);return;}
  const groups=Object.groupBy?Object.groupBy(state.cart,x=>x.shop_name):state.cart.reduce((a,x)=>{(a[x.shop_name]??=[]).push(x);return a;},{});
  const shipping=result.shipping_groups;
  appHTML(`<div class="container page">${breadcrumb('Giỏ hàng')}<h1 class="page-title">Giỏ hàng của bạn <span class="badge">${result.count} SẢN PHẨM</span></h1><p class="page-subtitle">Những lựa chọn nhỏ. Niềm vui thật lớn.</p><div class="cart-layout"><div><div class="content-card" style="padding:0"><label class="cart-select-all"><input id="cart-select-all" type="checkbox" ${state.cart.every(x=>x.is_selected)?'checked':''}>Chọn tất cả (${state.cart.length})</label>${Object.entries(groups).map(([shop,items])=>`<div class="cart-shop">${items.every(i=>i.is_mall)?'<span class="badge">Mall</span>':''}${e(shop)}</div>${items.map(i=>`<article class="cart-line"><input type="checkbox" data-cart-select="${i.cart_item_id}" ${i.is_selected?'checked':''} aria-label="Chọn ${e(nameOf(i.name))}"><img src="${e(i.image_url)}" alt="${e(nameOf(i.name))}"><div><button data-action="product" data-id="${i.id}"><h3>${e(nameOf(i.name))}</h3></button><p>Kho: ${e(shortProvince(i.province_name))}</p>${i.stock<i.quantity?`<p class="error-text">${i.stock?'Chỉ còn '+i.stock+' sản phẩm':'Đã hết hàng'} · Giảm số lượng hoặc bỏ chọn</p>`:''}</div><strong class="price">${money(i.price)}</strong><div class="quantity"><button data-action="cart-minus" data-id="${i.cart_item_id}" ${i.quantity<=1||i.stock<=0?'disabled':''} aria-label="Giảm số lượng">−</button><span>${i.quantity}</span><button data-action="cart-plus" data-id="${i.cart_item_id}" ${i.quantity>=Math.min(i.stock,99)?'disabled':''} aria-label="Tăng số lượng">+</button></div><button class="remove-button" data-action="cart-remove" data-id="${i.cart_item_id}" aria-label="Xóa sản phẩm">${icon('trash')}</button></article>`).join('')}`).join('')}</div><div class="shipping-progress">${shipping.length?shipping.map(g=>`<p><strong>${e(g.shop_name)}</strong> · ${g.remaining===null?'Có sản phẩm không hỗ trợ miễn cước.':g.remaining?'Còn '+money(g.remaining)+' để đạt mốc miễn cước tại shop này.':'Đã đủ điều kiện miễn cước tiêu chuẩn.'}</p>`).join(''):'Chọn sản phẩm để xem ưu đãi vận chuyển theo shop.'}</div><section class="section"><div class="section-title"><div><h2>Có thể bạn cần thêm</h2><p>Phụ kiện và sản phẩm phù hợp với những món trong giỏ.</p></div></div><div id="cart-recommendations"><div class="spinner"></div></div></section></div><aside class="content-card checkout-summary"><h3>Tóm tắt giỏ hàng</h3><div class="summary-row"><span>Tiền hàng đã chọn</span><strong>${money(result.subtotal)}</strong></div><div class="summary-row"><span>Vận chuyển & ưu đãi</span><strong>Tính ở bước sau</strong></div><div class="summary-row total"><span>Tạm tính</span><strong>${money(result.subtotal)}</strong></div><button class="primary" data-action="checkout" ${!result.subtotal||state.cart.some(i=>i.is_selected&&i.quantity>i.stock)?'disabled':''}>Mua hàng (${state.cart.filter(i=>i.is_selected).reduce((n,i)=>n+i.quantity,0)}) ${icon('arrow')}</button><small>Chỉ thanh toán các sản phẩm đã chọn.</small></aside></div></div>`);
  const crossSell=$('#cart-recommendations').closest('section');crossSell.classList.add('cart-crosssell');$('.cart-layout').append(crossSell);
  const recs=await fillOptionalRecommendations('/recommendations?touchpoint=cart&limit=18','#cart-recommendations',version);
  if(recs&&version===state.routeVersion){$('#cart-recommendations').closest('section').hidden=!recs.items.length;refreshDebug(recs.meta);}
}
async function fillOptionalRecommendations(path,selector,version){
  const userId=state.user?.id;
  try{
    const recs=await api(path);
    if(version!==state.routeVersion||userId!==state.user?.id)return null;
    const area=$(selector);if(area){state.labResult=recs;area.innerHTML=(state.storefront?'':recommendationExplanation(recs,true))+productGrid(recs.items);hydrate();}
    return recs;
  }catch{
    if(version===state.routeVersion&&userId===state.user?.id){const area=$(selector);if(area)area.innerHTML='<p class="page-subtitle">Gợi ý tạm thời chưa tải được. Bạn vẫn có thể tiếp tục các thao tác trên trang.</p>';}
    return null;
  }
}
function summaryHTML(bill){return `<details class="shipping-breakdown"><summary>Vận chuyển theo từng shop</summary>${bill.shipping_groups.map(g=>`<p>${e(g.shop_name)}: ${money(g.shipping_fee-g.shipping_discount)}${g.remaining===0?' · Đủ mốc miễn cước':g.remaining?' · Còn '+money(g.remaining)+' đến mốc miễn cước':''}</p>`).join('')}</details><div class="summary-row"><span>Tổng tiền hàng</span><strong>${money(bill.subtotal)}</strong></div><div class="summary-row"><span>Phí vận chuyển (${bill.shop_count} shop)</span><strong>${money(bill.shipping_fee)}</strong></div>${bill.shipping_discount?`<div class="summary-row discount-row"><span>Ưu đãi vận chuyển</span><strong>−${money(bill.shipping_discount)}</strong></div>`:''}${bill.voucher_discount?`<div class="summary-row discount-row"><span>Voucher giảm giá</span><strong>−${money(bill.voucher_discount)}</strong></div>`:''}${bill.coin_discount?`<div class="summary-row discount-row"><span>Xu trải nghiệm</span><strong>−${money(bill.coin_discount)}</strong></div>`:''}<div class="summary-row total"><span>Tổng thanh toán</span><strong>${money(bill.total)}</strong></div>`;}
async function renderCheckout(version){
  const params=routeParams();const direct=params.has('product_id');
  state.checkout.buy_now=direct?{product_id:Number(params.get('product_id')),quantity:Number(params.get('quantity')||1)}:null;
  const [addresses,vouchers,basket]=await Promise.all([api('/account/addresses'),api('/vouchers'),direct?api('/products/'+state.checkout.buy_now.product_id):api('/cart')]);if(version!==state.routeVersion)return;
  const cart=direct?{items:[{...basket,quantity:state.checkout.buy_now.quantity,is_selected:true}]}:basket;
  if(!cart.items.some(x=>x.is_selected)){navigate('cart');return;}
  if(!addresses.some(a=>a.id===state.checkout.address_id))state.checkout.address_id=addresses.find(a=>a.is_default)?.id||addresses[0]?.id||null;
  const available=vouchers.filter(v=>v.status==='available');if(!available.some(v=>v.code===state.checkout.voucher_code))state.checkout.voucher_code='';
  state.quote=null;state.checkoutKey=state.checkoutKey||crypto.randomUUID();
  appHTML(`<div class="container page">${breadcrumb('Thanh toán')}<h1 class="page-title">Chỉ một bước nữa thôi.</h1><p class="page-subtitle">Kiểm tra thông tin và chờ đón món đồ yêu thích.</p>${state.demo?'<div class="alert">Đây là đơn hàng demo. Ví trải nghiệm và quá trình giao hàng được mô phỏng; không phát sinh thanh toán thật.</div>':''}<div class="cart-layout"><div><section class="content-card checkout-section"><h3>${icon('pin')} Địa chỉ nhận hàng</h3>${addresses.length?addresses.map(a=>`<label class="address-option"><input type="radio" name="checkout_address" value="${a.id}" ${state.checkout.address_id===a.id?'checked':''}><div><strong>${e(a.recipient_name)} · ${e(a.phone)}</strong><p>${e(a.detail)}, ${e(a.province_name)}</p>${a.is_default?'<span class="default-tag">Mặc định</span>':''}</div></label>`).join(''):'<p class="page-subtitle">Bạn chưa có địa chỉ nhận hàng.</p>'}<button class="auth-link" data-action="new-address">+ Thêm địa chỉ mới</button></section><section class="content-card checkout-section"><h3>${icon('bag')} ${direct?'Mua ngay':'Sản phẩm đã chọn'}</h3><div id="checkout-items">${cart.items.filter(i=>i.is_selected).map(i=>`<div class="order-item"><img src="${e(i.image_url)}" alt="${e(nameOf(i.name))}"><div>${e(nameOf(i.name))}<p>${e(i.shop_name)} · x${i.quantity}</p></div><span>${money(i.price*i.quantity)}</span></div>`).join('')}</div></section><section class="content-card checkout-section"><h3>${icon('ticket')} Ưu đãi của bạn</h3><select id="checkout-voucher" aria-label="Chọn voucher"><option value="">Không dùng voucher</option>${available.map(v=>`<option value="${e(v.code)}" ${state.checkout.voucher_code===v.code?'selected':''}>${e(v.code)} · ${e(v.title)} (từ ${money(v.min_order_value)})</option>`).join('')}</select><label class="coin-option"><input id="checkout-coins" type="checkbox" ${state.checkout.use_coins?'checked':''} ${!state.user.shopee_coins?'disabled':''}> Dùng tối đa ${money(Math.min(state.user.shopee_coins,25000))} từ ${compact(state.user.shopee_coins)} Xu trải nghiệm</label><button class="auth-link" data-action="vouchers">Xem kho voucher để lưu thêm ưu đãi</button></section><section class="content-card checkout-section"><h3>${icon('shield')} Phương thức thanh toán</h3><label class="address-option"><input name="payment" type="radio" value="COD" ${state.checkout.payment_method==='COD'?'checked':''}><div><strong>Thanh toán khi nhận hàng (COD)</strong><p>Thanh toán cho đơn vị vận chuyển khi nhận hàng.</p></div></label>${state.demo?`<label class="address-option"><input name="payment" type="radio" value="ShopeePay" ${state.checkout.payment_method==='ShopeePay'?'checked':''}><div><strong>Ví trải nghiệm · MÔ PHỎNG</strong><p>Số dư mô phỏng: ${money(state.user.wallet_balance)}</p></div></label>`:''}</section></div><aside class="content-card checkout-summary"><h3>Chi tiết thanh toán</h3><div id="checkout-bill"><p class="page-subtitle">${addresses.length?'Đang tính tổng tiền…':'Thêm địa chỉ để xem tổng thanh toán.'}</p></div><p class="error-text" id="checkout-error"></p><button class="primary" id="place-order" data-action="place-order" disabled>Đặt hàng ngay ${icon('arrow')}</button><small>Giá, tồn kho và ưu đãi được kiểm tra lại tại server.</small></aside></div></div>`);
  if(addresses.length)await updateQuote();
}
async function updateQuote(){
  const version=++state.quoteVersion,routeVersion=state.routeVersion;state.quote=null;
  const button=$('#place-order');if(button)button.disabled=true;
  if(!state.checkout.address_id)return;
  $('#checkout-bill').innerHTML='<p class="page-subtitle">Đang cập nhật báo giá…</p>';
  try{
    const bill=await post('/checkout/quote',state.checkout);
    if(version!==state.quoteVersion||routeVersion!==state.routeVersion||state.route!=='checkout')return;
    state.quote=bill;$('#checkout-bill').innerHTML=summaryHTML(bill);
    const selectedAddress=document.querySelector('input[name="checkout_address"]:checked')?.closest('label')?.querySelector('div');
    if(selectedAddress)selectedAddress.innerHTML=`<strong>${e(bill.address.recipient_name)} · ${e(bill.address.phone)}</strong><p>${e(bill.address.detail)}, ${e(bill.address.province_name)}</p>${bill.address.is_default?'<span class="default-tag">Mặc định</span>':''}`;
    $('#checkout-items').innerHTML=bill.items.map(i=>`<div class="order-item"><img src="${e(i.image_url)}" alt="${e(nameOf(i.name))}"><div>${e(nameOf(i.name))}<p>${e(i.shop_name)} · x${i.quantity}</p></div><span>${money(i.price*i.quantity)}</span></div>`).join('');
    $('#checkout-voucher').innerHTML='<option value="">Không dùng voucher</option>'+bill.available_vouchers.map(v=>`<option value="${e(v.code)}" ${state.checkout.voucher_code===v.code?'selected':''} ${v.eligible?'':'disabled'}>${e(v.code)} · ${e(v.title)}${v.reason?' — '+e(v.reason):''}</option>`).join('');
    const insufficient=state.checkout.payment_method==='ShopeePay'&&bill.wallet_balance<bill.total;
    $('#checkout-error').textContent=insufficient?'Số dư ví demo không đủ. Vui lòng chọn COD.':'';
    $('#place-order').disabled=insufficient||state.busy;hydrate();
  }catch(error){
    if(version!==state.quoteVersion||routeVersion!==state.routeVersion||state.route!=='checkout')return;
    $('#checkout-bill').innerHTML='<p class="page-subtitle">Chưa có báo giá hợp lệ.</p>';$('#checkout-error').textContent=error.message;
  }
}
async function placeOrder(){
  if(state.busy||!state.quote)return;state.busy=true;
  const button=$('#place-order');button.disabled=true;button.textContent='Đang đặt hàng…';
  const locked=[...document.querySelectorAll('.checkout-section input,.checkout-section select,.checkout-section button,#profile-switch')].filter(el=>!el.disabled);
  locked.forEach(el=>el.disabled=true);
  const payload={...state.checkout,idempotency_key:state.checkoutKey,expected_total:state.quote.total,quote_token:state.quote.quote_token};
  try{
    const order=await post('/orders',payload);
    state.checkoutKey=null;state.checkout.voucher_code='';state.checkout.use_coins=false;state.checkout.buy_now=null;
    await refreshUser();closeModal();state.route='success';state.routeVersion++;state.quoteVersion++;
    history.replaceState(null,'','#/orders');
    appHTML(`<div class="container page"><div class="content-card success-state">${icon('check')}<h1>Đặt hàng thành công!</h1><p>Cảm ơn bạn. Đơn hàng đã được gửi và đang chờ xác nhận.</p><div class="success-code">${e(order.order_code)}</div><p>Tổng thanh toán: <strong>${money(order.final_payment_amount)}</strong></p><p>${state.demo?'Giao dịch mô phỏng':''}</p><button class="primary" data-action="orders">Theo dõi đơn hàng ${icon('arrow')}</button><button class="auth-link" data-action="home">Tiếp tục mua sắm</button></div><section class="section" id="success-recs-section" style="margin-top:28px"><div class="section-title"><div><h2>Có thể bạn cũng thích</h2><p>${state.native?'Tiếp nối khám phá từ lịch sử và hoạt động của bạn.':'Những sản phẩm phù hợp với đơn hàng vừa đặt.'}</p></div></div><div id="success-recs"><div class="spinner"></div></div></section></div>`);
    window.scrollTo({top:0,behavior:'smooth'});
    if(order.items&&order.items.length)loadSuccessRecommendations(order,state.routeVersion,state.user?.id);
  }catch(error){
    toast(error.message,true);
    if(error.status===409){state.checkoutKey=crypto.randomUUID();await updateQuote();}
    else if($('#place-order'))$('#place-order').innerHTML='Thử đặt hàng lại '+icon('arrow');
  }finally{
    state.busy=false;locked.forEach(el=>el.disabled=false);
    if($('#place-order')){$('#place-order').disabled=!state.quote||(state.checkout.payment_method==='ShopeePay'&&state.quote.wallet_balance<state.quote.total);$('#place-order').innerHTML='Đặt hàng ngay '+icon('arrow');}
  }
}
async function loadSuccessRecommendations(order,version,userId){
  try{
    const recs=await api('/recommendations?touchpoint=complementary&product_id='+order.items[0].product_id+'&limit=12');
    if(version!==state.routeVersion||userId!==state.user?.id||state.route!=='success')return;
    const area=$('#success-recs');if(area){state.labResult=recs;area.innerHTML=(state.storefront?'':recommendationExplanation(recs,true))+productGrid(recs.items);hydrate();}
  }catch{
    if(version===state.routeVersion&&userId===state.user?.id){const area=$('#success-recs');if(area)area.innerHTML='<p class="page-subtitle">Bạn có thể tiếp tục khám phá trên trang chủ.</p>';}
  }
}
function openAuth(mode='login'){
  state.authMode=mode;
  const titles={login:'Chào bạn, mừng bạn trở lại.',register:'Bắt đầu hành trình của bạn.',forgot:'Tìm lại tài khoản của bạn.',reset:'Tạo mật khẩu mới.'};
  let fields='';
  if(mode==='register')fields+=`<div class="field"><label for="auth-name">Họ và tên</label><input id="auth-name" name="full_name" required minlength="2" maxlength="100" autocomplete="name"></div><div class="field"><label for="auth-phone">Số điện thoại</label><input id="auth-phone" name="phone" required pattern="0[0-9]{9}" inputmode="tel" autocomplete="tel"></div><div class="field-row"><div class="field"><label for="auth-gender">Giới tính</label><select id="auth-gender" name="gender"><option value="Nam">Nam</option><option value="Nữ">Nữ</option><option value="Khác">Khác</option></select></div><div class="field"><label for="auth-year">Năm sinh</label><input id="auth-year" name="birth_year" type="number" min="1900" max="2026" placeholder="VD: 2002"></div></div>`;
  if(mode!=='reset')fields+=`<div class="field"><label for="auth-email">Email</label><input id="auth-email" name="email" type="email" required maxlength="254" autocomplete="email"></div>`;
  if(mode==='reset')fields+=`<div class="alert">Mã OTP demo: <strong>888999</strong> · Hiệu lực 5 phút, tối đa 5 lần thử.</div><div class="field"><label for="auth-code">Mã OTP</label><input id="auth-code" name="code" required inputmode="numeric" pattern="[0-9]{6}" autocomplete="one-time-code"></div>`;
  if(mode!=='forgot')fields+=`<div class="field"><label for="auth-password">${mode==='reset'?'Mật khẩu mới':'Mật khẩu'}</label><input id="auth-password" name="password" type="password" required minlength="${mode==='login'?1:8}" maxlength="128" autocomplete="${mode==='login'?'current-password':'new-password'}"></div>`;
  const profiles=state.demo&&(mode==='login'||mode==='register')?`<div class="demo-auth"><p>CHỌN HỒ SƠ MUA SẮM MẪU</p><div class="demo-profile-grid">${state.profiles.map(p=>`<button data-action="demo-login" data-id="${p.id}">${p.avatar_url?`<img src="${e(p.avatar_url)}" alt="">`:''}${e(nameOf(p.full_name))}</button>`).join('')}</div></div>`:'';
  openModal(titles[mode],`${mode==='login'||mode==='register'?`<div class="auth-tabs"><button data-auth="login" class="${mode==='login'?'active':''}">Đăng nhập</button><button data-auth="register" class="${mode==='register'?'active':''}">Đăng ký</button></div>`:''}<form id="auth-form" class="auth-form">${fields}<p class="error-text" id="form-error"></p><button class="primary" type="submit">${{login:'Đăng nhập',register:'Tạo tài khoản',forgot:'Gửi mã khôi phục',reset:'Đặt lại mật khẩu'}[mode]}</button>${mode==='login'?'<button class="auth-link" type="button" data-auth="forgot">Quên mật khẩu?</button>':''}${mode==='forgot'||mode==='reset'?'<button class="auth-link" type="button" data-auth="login">Quay lại đăng nhập</button>':''}</form>${profiles}`,true);
}
async function loginDemo(id){
  if(state.switching||state.busy)return;state.switching=true;$('#profile-switch').disabled=true;state.routeVersion++;state.recsVersion++;state.debugVersion++;
  $('#app').inert=true;$('#app').setAttribute('aria-busy','true');$('#search').disabled=true;$('#search-form button').disabled=true;closeSearchDropdown();
  try{await post('/auth/demo-login',{user_id:Number(id)});resetCheckout();await refreshUser();closeModal();toast('Đã chuyển hồ sơ: '+nameOf(state.user.full_name));await resumeShopping();}
  finally{state.switching=false;$('#profile-switch').disabled=false;$('#app').inert=false;$('#app').removeAttribute('aria-busy');$('#search').disabled=false;$('#search-form button').disabled=false;}
}
function resetCheckout(){state.storeRecFailure=false;state.storeFocusProductId=null;state.storeBrowse=false;state.nativeChange=null;state.nativeExperience=null;state.nativeNeighbours=null;state.nativeEvidenceVersion=(state.nativeEvidenceVersion||0)+1;state.homeGroup=null;state.homeCategoryFilter=null;state.homeDisplayCategory='';state.homeLimit=24;state.checkout={address_id:null,voucher_code:'',use_coins:false,payment_method:'COD',buy_now:null};state.checkoutKey=null;state.quote=null;state.quoteVersion++;state.recommendations=null;state.labResult=null;state.recommendationContexts={};state.debugInfo=null;state.lastInteraction=null;}
async function resumeShopping(){
  const intent=state.pendingIntent;state.pendingIntent=null;await renderRoute();
  if(intent){await openProduct(intent.product_id);const input=$('#detail-quantity');if(input)input.value=intent.quantity;await addProduct(intent.buy);}
}
async function renderRoute(){
  state.quoteVersion++;const route=(location.hash.replace(/^#\//,'').split('?')[0]||'home');state.route=route;const version=++state.routeVersion;window.scrollTo(0,0);if(route==='home')$('#search').value='';else if(route==='catalog')$('#search').value=routeParams().get('q')||'';
  if(['account','orders','addresses','vouchers','wishlist','notifications','password','cart','checkout'].includes(route)&&!state.user){appHTML(`<div class="container page">${empty('Mua sắm dành riêng cho bạn','Đăng nhập để lưu lựa chọn và tiếp tục mua sắm.','login','Đăng nhập ngay','user')}</div>`);openAuth();return;}
  if(route!=='home'&&route!=='catalog')appHTML('<div class="container loading-screen"><div class="spinner"></div><p>Đang tải…</p></div>');
  try{switch(route){case'home':await renderHome(version);break;case'catalog':await renderCatalog(version);break;case'account':await renderAccount(version);break;case'addresses':await renderAddresses(version);break;case'vouchers':await renderVouchers(version);break;case'wishlist':await renderWishlist(version);break;case'notifications':await renderNotifications(version);break;case'orders':await renderOrders(version);break;case'password':renderPassword();break;case'cart':await renderCart(version);break;case'checkout':await renderCheckout(version);break;default:navigate('home');}}
  catch(error){if(version===state.routeVersion)appHTML(`<div class="container page">${empty('Chưa tải được nội dung',error.message,'retry','Thử lại','return')}</div>`);}
  hydrate();refreshDebug();
}
async function confirmAction(title,text,action,id){openModal(title,`<p class="page-subtitle">${e(text)}</p><button class="primary" data-action="${action}" data-id="${id}">Xác nhận</button><button class="soft-button" data-action="close-modal">Quay lại</button>`,true);}
function museInfo(){
  if(state.native)return nativeLabInfo();
  if(!(state.demo&&state.debug))return;
  openModal('MUSE Lab · Kiến trúc và cách xếp hạng',`<div class="help-prose"><h3>Suy luận từ checkpoint</h3><p>Alibaba MUSE kết hợp ID sản phẩm và vector SCL 128 chiều. GSU chọn hành vi liên quan; SimTier và SA-TA tổng hợp tín hiệu để dự đoán xác suất click.</p><h3>Thứ tự khách hàng nhìn thấy</h3><p>Trang chủ kết hợp thứ hạng model với ngành hàng vừa xem, thêm giỏ, mua hàng và nhu cầu được chọn. Lựa chọn nhu cầu được lưu dưới dạng demo_interest và đưa vào lịch sử model. Lớp xếp hạng theo nhu cầu cùng quy tắc giãn ảnh/ngành hàng giúp quan sát thay đổi; P(click) gốc được giữ nguyên.</p><h3>Giới hạn của bản trình diễn</h3><p>Raw ID và checkpoint là dữ liệu thật. Tên tiếng Việt, ngành hàng, giá và ảnh là dữ liệu minh họa, chưa đủ để kết luận chất lượng gợi ý trên hàng hóa tiếng Việt. Kết quả đo lại nằm trong bảng đánh giá của Lab; chỉ áp dụng cho dữ liệu thử nghiệm gốc và checkpoint được ghi trong báo cáo.</p><p><a href="https://github.com/alimama-tech/MUSE" target="_blank" rel="noopener">Mã nguồn MUSE chính thức ↗</a></p></div>`,true);
}
async function handleAction(action,el){
  const id=Number(el?.dataset.id);
  switch(action){
    case'home':case'catalog':case'cart':case'checkout':case'account':case'orders':case'addresses':case'vouchers':case'wishlist':case'notifications':case'password':navigate(action);break;
    case'login':openAuth();break;
    case'retry':await renderRoute();break;
    case'close-modal':state.pendingIntent=null;closeModal();break;
    case'product':closeSearchDropdown();await openProduct(id);break;
    case'demo-login':await loginDemo(id);break;
    case'logout':if(state.busy)return;await post('/auth/logout');resetCheckout();state.pendingIntent=null;await refreshUser();navigate('home');toast('Đã đăng xuất.');break;
    case'hero':state.hero=Number(el.dataset.index);$('#hero').innerHTML=heroHTML();hydrate();break;
    case'flash':case'flash-all':navigate('catalog',{sort:'discount'});break;
    case'home-cat-tab':state.homeCategoryFilter=Number(el.dataset.categoryId)||null;state.homeLimit=24;await refreshHomeRecommendations();break;
    case'store-home-category':state.storeBrowse=true;state.storeFocusProductId=null;state.nativeChange=null;state.homeDisplayCategory=el.dataset.value||'';state.homeLimit=24;await refreshHomeRecommendations();break;
    case'store-all-categories':state.storeBrowse=true;state.storeFocusProductId=null;state.nativeChange=null;state.homeDisplayCategory='';state.homeLimit=24;await refreshHomeRecommendations();break;
    case'native-refresh':await refreshHomeRecommendations();break;
    case'native-result':if(state.route!=='home')navigate('home');else{closeModal();$('#native-context')?.scrollIntoView({behavior:'smooth',block:'center'});}break;
    case'native-compare-profiles':if(state.demo&&state.debug)openNativeProfileComparison();break;
    case'native-profile':$('#profile-switch').focus();window.scrollTo({top:0,behavior:'smooth'});break;
    case'native-group':state.nativeChange=null;state.homeGroup=Number(el.dataset.group)||null;state.homeLimit=24;await refreshHomeRecommendations();break;
    case'native-ai-info':if(state.demo&&state.debug)nativeAIInfo();break;
    case'store-original-ranking':await storeOriginalRanking();break;
    case'home-more':state.homeLimit=Math.min(60,Math.max(36,state.homeLimit)+12);await refreshHomeRecommendations();if(state.homeLimit===60)el.hidden=true;break;
    case'muse-info':if(state.demo&&state.debug)museInfo();break;
    case'ai-info':if(state.demo&&state.debug)aiInfo(el);break;
    case'favorite':if(requireLogin()){const favoriteUserId=state.user.id;const result=await put('/account/wishlist/'+id);if(favoriteUserId!==state.user?.id)break;if(result.saved){if(state.native)captureNativeInteraction(state.selectedProduct?.id===id?state.selectedProduct:state.recommendations?.items.find(p=>p.id===id),'favorite');state.wishlist.add(id);}else state.wishlist.delete(id);document.querySelectorAll(`.heart-button[data-id="${id}"]`).forEach(b=>{b.classList.toggle('saved',result.saved);b.setAttribute('aria-label',result.saved?'Bỏ yêu thích':'Yêu thích sản phẩm');});if(state.native&&state.selectedProduct?.id===id&&$('#modal').open){const save=$('#modal [data-action="favorite"]');if(save)save.innerHTML=icon('heart')+(result.saved?' Đã lưu':' Yêu thích');}toast(result.saved?(state.native?'Đã lưu sản phẩm yêu thích.':'Đã lưu vào danh sách yêu thích.'):'Đã bỏ khỏi yêu thích.');if(state.route==='wishlist')await renderRoute();}break;
    case'detail-minus':case'detail-plus':{const input=$('#detail-quantity');input.value=Math.max(1,Math.min(Math.min(state.selectedProduct.stock,99),Number(input.value)+(action==='detail-plus'?1:-1)));break;}
    case'add-product':await addProduct();break;
    case'buy-product':await addProduct(true);break;
    case'cart-minus':case'cart-plus':{const item=state.cart.find(x=>x.cart_item_id===id);await put('/cart/'+id,{quantity:action==='cart-plus'?item.quantity+1:Math.min(item.quantity-1,item.stock),is_selected:!!item.is_selected});await renderRoute();break;}
    case'cart-remove':await api('/cart/'+id,{method:'DELETE'});await renderRoute();toast('Đã xóa khỏi giỏ hàng.');break;
    case'place-order':await placeOrder();break;
    case'quick-add':{if(!state.user){state.pendingIntent={product_id:id,quantity:1,buy:false};openAuth();break;}const item=state.recommendations?.items.find(p=>p.id===id)||state.products?.items.find(p=>p.id===id);if(state.native&&item)captureNativeInteraction(item,'add_to_cart');await post('/cart',{product_id:id,quantity:1});await refreshUser();if(state.route==='cart')await renderRoute();toast('Đã thêm sản phẩm vào giỏ hàng.');break;}
    case'clear-filter':navigate('catalog');break;
    case'new-address':await openAddress();break;
    case'edit-address':await openAddress(id);break;
    case'delete-address':await confirmAction('Xóa địa chỉ?','Bạn có thể thêm lại địa chỉ này bất kỳ lúc nào.','confirm-delete-address',id);break;
    case'confirm-delete-address':await api('/account/addresses/'+id,{method:'DELETE'});closeModal();await renderRoute();toast('Đã xóa địa chỉ.');break;
    case'claim-voucher':await post('/vouchers/'+id+'/claim');await renderRoute();toast('Đã lưu voucher vào kho.');break;
    case'read-notifications':await post('/account/notifications/read');await refreshUser();await renderRoute();break;
    case'cancel-order':await confirmAction('Hủy đơn hàng?','Tiền ví demo, Xu và voucher sẽ được hoàn lại nếu đã sử dụng.','confirm-cancel-order',id);break;
    case'confirm-cancel-order':await post('/orders/'+id+'/cancel');closeModal();await refreshUser();await renderRoute();toast('Đã hủy đơn và hoàn lại quyền lợi.');break;
    case'advance-order':await post('/orders/'+id+'/demo-advance');await refreshUser();await renderRoute();toast('Đã cập nhật trạng thái mô phỏng.');break;
    case'reorder':{await post('/orders/'+id+'/reorder');await refreshUser();navigate('cart');toast('Đã thêm các sản phẩm vào giỏ.');break;}
    case'review':{const order=state.orders.find(o=>o.id===id);openModal('Chia sẻ trải nghiệm của bạn',`<form id="review-form"><div class="field"><label for="review-product">Sản phẩm</label><select id="review-product" name="product_id">${order.items.map(i=>`<option value="${i.product_id}">${e(nameOf(i.product_name))}</option>`).join('')}</select></div><div class="field"><label for="review-rating">Đánh giá</label><select id="review-rating" name="rating">${[5,4,3,2,1].map(r=>`<option value="${r}">${'★'.repeat(r)} (${r}/5)</option>`).join('')}</select></div><div class="field"><label for="review-content">Nội dung đánh giá</label><textarea id="review-content" name="content" required minlength="10" maxlength="1000" placeholder="Điều bạn yêu thích về sản phẩm này…"></textarea></div><p id="form-error" class="error-text"></p><button class="primary" type="submit">Gửi đánh giá</button></form>`,true);break;}
    case'history':{if(!(state.demo&&state.debug))break;const rows=await api('/recommendations/history?limit=1000');if(!(state.demo&&state.debug))break;const actLabels={imported_click:'Lịch sử Taobao gốc',click:'Xem sản phẩm',favorite:'Đã lưu yêu thích',add_to_cart:'Thêm vào giỏ',purchase:'Đã mua hàng',demo_interest:'Quan tâm'};openModal('MUSE Lab · Chuỗi tương tác hành vi',`<p class="page-subtitle">${rows.length} tương tác trong chuỗi lịch sử · hiển thị tên sản phẩm, hình ảnh và danh mục rõ ràng.</p><div class="history-list">${rows.map((h,i)=>`<div class="history-row"><span class="history-index">${i+1}</span>${h.image_url?`<img src="${e(h.image_url)}" class="history-thumb" alt="" style="width:40px;height:40px;object-fit:cover;border-radius:6px;margin:0 10px;flex-shrink:0;">`:''}<div style="flex:1;min-width:0;"><strong style="font-size:14px;display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${e(h.product_name||'Sản phẩm Taobao')}</strong><span style="font-size:12px;color:var(--text-muted);">${h.category_name?e(h.category_name)+' · ':''}<code>ID: ${e(h.raw_item_id)}</code></span></div><small style="text-align:right;white-space:nowrap;margin-left:12px;"><b style="color:var(--primary);">${e(actLabels[h.action_type]||h.action_type)}</b><br><span style="color:var(--text-muted);">${e(date(h.created_at))}</span></small></div>`).join('')}</div>`);break;}
    case'help':openModal('Mua sắm dễ dàng hơn',`<div class="help-prose"><h3>Đặt hàng</h3><p>Chọn sản phẩm → thêm vào giỏ → chọn địa chỉ, voucher và phương thức thanh toán → kiểm tra tổng tiền → đặt hàng.</p><h3>Vận chuyển & ưu đãi</h3><p>Cước vận chuyển được tính theo tỉnh nhận hàng và từng gian hàng. Mỗi đơn dùng một voucher và tối đa 25.000 Xu.</p><h3>Quản lý đơn hàng</h3><p>Vào Đơn mua để theo dõi và hủy đơn đang chờ xác nhận. Bạn có thể đánh giá sản phẩm sau khi đơn được đánh dấu đã giao.</p></div>`,true);break;
    case'about':openModal('Về Lumi',`<div class="help-prose"><p>Lumi là cửa hàng thử nghiệm với đầy đủ luồng tìm kiếm, yêu thích, giỏ hàng, voucher, đặt hàng và theo dõi đơn.</p><h3>Thông tin trải nghiệm</h3><p>Tên, ảnh, giá, ưu đãi, tồn kho, đánh giá, ví và giao nhận trong cửa hàng dùng để minh họa chức năng. Không phát sinh thanh toán hay vận chuyển thật.</p><p>Những thao tác bạn thực hiện vẫn được lưu trong cơ sở dữ liệu của ứng dụng.</p>${state.demo&&state.debug?'<button class="primary" data-action="muse-info">Mở thông tin kỹ thuật trong Lab</button>':''}</div>`,true);break;
  }
}
let searchTimer=null,searchRequest=0,searchController=null;
function closeSearchDropdown(){
  clearTimeout(searchTimer);searchTimer=null;searchRequest++;
  searchController?.abort();searchController=null;
  const dropdown=$('#search-dropdown');if(dropdown)dropdown.hidden=true;
  $('#search')?.setAttribute('aria-expanded','false');
}
function renderSearchProductCard(p){
  const sale=p.discount_percent>0&&p.original_price>p.price;
  const ai=p.recommendation_source==='ai';
  return `<button type="button" class="search-product-card" data-action="product" data-id="${p.id}"><div class="search-product-thumb"><img loading="lazy" src="${e(p.image_url)}" alt="${e(nameOf(p.name))}">${sale?`<span class="search-product-discount">-${p.discount_percent}%</span>`:''}${p.is_mall?'<span class="search-product-mall">Mall</span>':''}</div><div class="search-product-body"><h4>${e(nameOf(p.name))}</h4><div class="search-product-price"><strong>${money(p.price)}</strong>${sale?`<s>${money(p.original_price)}</s>`:''}</div><div class="search-product-meta"><span>★ ${e(p.rating_star)}</span><span>Đã bán ${compact(p.sold_count)}</span></div></div></button>`;
}
async function refreshSearchDropdown(query=''){
  const dropdown=$('#search-dropdown');if(!dropdown)return;
  if(!$('#search')?.closest('.search-area')?.contains(document.activeElement))return;
  const request=++searchRequest;
  searchController?.abort();
  const controller=new AbortController();searchController=controller;
  try{
    const data=await api('/search/suggestions?q='+encodeURIComponent(query),{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(15000)])});
    if(request!==searchRequest)return;
    let html='';
    const hasQuery=Boolean(query.trim());
    const ctx=data.suggestion_context||{};
    const productSection=(data.products&&data.products.length>0)?`<div class="search-dropdown-section search-products-section"><div class="search-dropdown-header"><div><span>${hasQuery?'Sản phẩm':'Có thể bạn quan tâm'}</span></div></div><div class="search-product-grid">${data.products.map(renderSearchProductCard).join('')}</div></div>`:'';

    if(hasQuery){
      html+=productSection;
      if(data.autocomplete&&data.autocomplete.length>0){
        html+=`<div class="search-dropdown-section"><div class="search-dropdown-header">Tìm kiếm liên quan</div><div class="search-autocomplete-list">`+
          data.autocomplete.map(item=>`<button type="button" class="search-autocomplete-item" data-search-pick="${e(item)}">${icon('search')}<span>${e(item)}</span></button>`).join('')+
          `</div></div>`;
      }
    }
    if(data.history&&data.history.length>0){
      html+=`<div class="search-dropdown-section"><div class="search-dropdown-header"><span>Lịch sử tìm kiếm</span><button type="button" class="search-clear-btn" data-action="clear-all-search">Xóa tất cả</button></div><div class="search-chips">`+
        data.history.map(item=>`<span class="search-chip" data-search-pick="${e(item)}">${icon('clock')} ${e(item)}<button type="button" class="search-chip-del" data-action="del-search" data-query="${e(item)}" aria-label="Xóa">×</button></span>`).join('')+
        `</div></div>`;
    }
    if(data.personalized&&data.personalized.length>0){
      html+=`<div class="search-dropdown-section"><div class="search-dropdown-header">${state.native?(state.user?'Khám phá sản phẩm':'Bắt đầu mua sắm'):'Gợi ý tìm kiếm'}</div><div class="search-chips">`+
        data.personalized.map(item=>`<button type="button" class="search-chip personalized" data-search-pick="${e(item)}">${icon('sparkles')} ${e(item)}</button>`).join('')+
        `</div></div>`;
    }
    if(!hasQuery){
      html+=productSection;
    }
    if(data.trending&&data.trending.length>0){
      html+=`<div class="search-dropdown-section"><div class="search-dropdown-header">${state.native?'Có thể bạn đang tìm':'Tìm kiếm thịnh hành'}</div><div class="search-chips">`+
        data.trending.map(item=>`<button type="button" class="search-chip trending" data-search-pick="${e(item)}">🔥 ${e(item)}</button>`).join('')+
        `</div></div>`;
    }
    dropdown.innerHTML=html;dropdown.hidden=!html;$('#search')?.setAttribute('aria-expanded',String(Boolean(html)));hydrate(dropdown);
  }catch(err){if(request===searchRequest){dropdown.hidden=true;$('#search')?.setAttribute('aria-expanded','false');}}
  finally{if(searchController===controller)searchController=null;}
}

document.addEventListener('pointerdown',event=>{
  if(!event.target.closest('.search-area'))closeSearchDropdown();
});
document.addEventListener('keydown',event=>{
  if(event.key==='Escape'&&(!$('#search-dropdown').hidden||searchController||searchTimer)){
    closeSearchDropdown();event.preventDefault();
  }
});
document.addEventListener('click',async event=>{
  if(!event.target.closest('.search-area'))closeSearchDropdown();
  const target=event.target.closest('button,a,[data-search-pick]');if(!target||target.disabled||target.dataset.pending)return;
  if(target.dataset.searchPick!=null){
    event.preventDefault();const val=target.dataset.searchPick;
    $('#search').value=val;closeSearchDropdown();
    navigate('catalog',{q:val,sort:'relevance'});return;
  }
  if(target.dataset.action==='clear-all-search'){
    event.preventDefault();event.stopPropagation();
    await api('/search/history',{method:'DELETE'});
    await refreshSearchDropdown($('#search')?.value||'');return;
  }
  if(target.dataset.action==='del-search'){
    event.preventDefault();event.stopPropagation();
    await api('/search/history?query='+encodeURIComponent(target.dataset.query),{method:'DELETE'});
    await refreshSearchDropdown($('#search')?.value||'');return;
  }
  target.dataset.pending='true';
  try{
    if(target.dataset.action){event.preventDefault();await handleAction(target.dataset.action,target);}
    else if(target.dataset.search!=null){event.preventDefault();$('#search').value=target.dataset.search;closeSearchDropdown();navigate('catalog',{q:target.dataset.search,sort:'relevance'});}
    else if(target.dataset.displayCategory!=null){event.preventDefault();navigate('catalog',{display_category:target.dataset.displayCategory,sort:'relevance'});}
    else if(target.dataset.category){event.preventDefault();navigate('catalog',{category_id:target.dataset.category});}
    else if(target.dataset.sort){updateCatalogParams({sort:target.dataset.sort});}
    else if(target.dataset.page){updateCatalogParams({page:target.dataset.page});}
    else if(target.dataset.auth){openAuth(target.dataset.auth);}
    else if(target.dataset.tab){state.orderTab=target.dataset.tab;await renderRoute();}
    else if(target.dataset.shop){navigate('catalog',{q:target.dataset.shop});}
  }catch(error){toast(error.message,true);}finally{delete target.dataset.pending;}
});
document.addEventListener('change',async event=>{
  const el=event.target;
  try{
    if(el.id==='native-compare-left'||el.id==='native-compare-right')await loadNativeProfileComparison();
    else if(el.id==='store-home-category'){state.storeBrowse=true;state.storeFocusProductId=null;state.nativeChange=null;state.homeDisplayCategory=el.value;state.homeLimit=24;await refreshHomeRecommendations();}
    else if(el.id==='store-catalog-category')updateCatalogParams({display_category:el.value,category_id:''});
    else if(el.id==='native-home-group'){state.nativeChange=null;state.homeGroup=Number(el.value)||null;state.homeLimit=24;await refreshHomeRecommendations();}
    else if(el.id==='native-catalog-group')updateCatalogParams({category_id:el.value});
    else if(el.id==='profile-switch'&&el.value)await loginDemo(el.value);
    else if(el.id==='debug-toggle'){
      state.debug=state.demo&&el.checked;
      if(!state.debug&&$('#modal').open)closeModal();
      await refreshDebug(state.recommendations?.meta);
      if($('#home-products')&&state.recommendations?.items){
        $('#home-products').innerHTML=productGrid(state.recommendations.items,true);
      }
      if($('#catalog-products')&&state.products?.items){
        $('#catalog-products').innerHTML=productGrid(state.products.items);
      }
      hydrate();
    }
    else if(el.id==='price-sort'&&el.value)updateCatalogParams({sort:el.value});
    else if(el.dataset.cartSelect){const item=state.cart.find(i=>i.cart_item_id===Number(el.dataset.cartSelect));await put('/cart/'+item.cart_item_id,{quantity:item.quantity,is_selected:el.checked});await renderRoute();}
    else if(el.id==='cart-select-all'){await put('/cart/selection',{is_selected:el.checked});await renderRoute();}
    else if(el.name==='checkout_address'||el.id==='checkout-voucher'||el.id==='checkout-coins'||el.name==='payment'){
      if(el.name==='checkout_address')state.checkout.address_id=Number(el.value);if(el.id==='checkout-voucher')state.checkout.voucher_code=el.value;if(el.id==='checkout-coins')state.checkout.use_coins=el.checked;if(el.name==='payment')state.checkout.payment_method=el.value;
      state.checkoutKey=crypto.randomUUID();await updateQuote();
    }
  }catch(error){toast(error.message,true);}
});
document.addEventListener('submit',async event=>{
  const form=event.target;event.preventDefault();const data=Object.fromEntries(new FormData(form));const button=form.querySelector('button[type=submit]');if(button)button.disabled=true;
  try{
    if(form.id==='search-form'){
      closeSearchDropdown();
      navigate('catalog',{q:$('#search').value.trim(),sort:'relevance'});
    }
    else if(form.id==='filter-form'){if(data.max_price&&Number(data.max_price)<Number(data.min_price))throw new Error('Giá tối đa cần lớn hơn giá tối thiểu.');updateCatalogParams(data);}
    else if(form.id==='auth-form'){
      if(state.authMode==='login'||state.authMode==='register'){
        if(state.authMode==='register'){if(data.birth_year)data.birth_year=Number(data.birth_year);else delete data.birth_year;}
        await post('/auth/'+state.authMode,data);resetCheckout();await refreshUser();closeModal();toast('Chào mừng '+nameOf(state.user.full_name)+'!');await resumeShopping();
      }
      else if(state.authMode==='forgot'){const result=await post('/auth/forgot-password',data);state.challenge=result.challenge_id;openAuth('reset');}
      else{await post('/auth/reset-password',{...data,challenge_id:state.challenge});toast('Đã đặt lại mật khẩu. Vui lòng đăng nhập.');openAuth('login');}
    }
    else if(form.id==='profile-form'){await put('/account/profile',{...data,birth_year:data.birth_year?Number(data.birth_year):null});await refreshUser();toast('Đã lưu thông tin tài khoản.');}
    else if(form.id==='address-form'){const body={...data,province_id:Number(data.province_id),is_default:new FormData(form).has('is_default')};if(form.dataset.id)await put('/account/addresses/'+form.dataset.id,body);else{const saved=await post('/account/addresses',body);if(state.route==='checkout')state.checkout.address_id=saved.id;}closeModal();toast('Đã lưu địa chỉ nhận hàng.');await renderRoute();}
    else if(form.id==='password-form'){if(data.new_password!==data.confirm_password)throw new Error('Mật khẩu xác nhận chưa khớp.');await post('/auth/password',data);form.reset();toast('Đã cập nhật mật khẩu.');}
    else if(form.id==='review-form'){await post('/products/'+data.product_id+'/reviews',{rating:Number(data.rating),content:data.content});closeModal();toast('Cảm ơn bạn đã chia sẻ đánh giá.');}
  }catch(error){const target=form.querySelector('#form-error');if(target)target.textContent=error.message;else toast(error.message,true);}
  finally{if(button)button.disabled=false;}
});

const searchInput=$('#search');
if(searchInput){
  searchInput.addEventListener('focus',()=>refreshSearchDropdown(searchInput.value));
  searchInput.addEventListener('click',()=>refreshSearchDropdown(searchInput.value));
  searchInput.addEventListener('input',()=>{
    closeSearchDropdown();
    searchTimer=setTimeout(()=>{searchTimer=null;refreshSearchDropdown(searchInput.value);},180);
  });
  searchInput.closest('.search-area').addEventListener('focusout',event=>{
    if(event.relatedTarget&&!event.currentTarget.contains(event.relatedTarget))closeSearchDropdown();
  });
}

$('#modal').addEventListener('click',event=>{if(event.target===$('#modal')){const r=$('#modal').getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom){state.pendingIntent=null;closeModal();}}});
$('#modal').addEventListener('cancel',()=>{state.modalVersion++;state.pendingIntent=null;});
window.addEventListener('hashchange',renderRoute);
setInterval(()=>{if(state.route==='home'&&!$('#modal').open&&$('#hero')){state.hero=(state.hero+1)%heroes.length;$('#hero').innerHTML=heroHTML();placeholder($('#hero'));}},9000);
async function init(){try{
  const [catalog,current]=await Promise.all([api('/catalog'),api('/auth/me')]);state.native=catalog.source?.mode==='taobao_native_v1';state.source=catalog.source;state.storeCategories=catalog.storefront_categories||[];state.storefront=state.native&&state.storeCategories.length>0;state.categories=catalog.categories;state.provinces=catalog.provinces;state.user=current.user;state.demo=current.demo_mode;
  if(state.demo){
    state.profiles=await api('/auth/demo-profiles');
    $('#profile-switch').innerHTML='<option value="">Chọn hồ sơ mua sắm</option>'+state.profiles.map(p=>`<option value="${p.id}">${e(nameOf(p.full_name))}${state.storefront?'':state.native?' · Hồ sơ dữ liệu':' · '+e(p.member_tier)}</option>`).join('');

  }
  await refreshUser();hydrate();await renderRoute();
}catch(error){appHTML(`<div class="container page">${empty('Chưa kết nối được cửa hàng',error.message,'retry','Thử lại','return')}</div>`);}}
init();
