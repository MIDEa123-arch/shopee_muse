/* Native Taobao experience. All aliases are presentation labels, never product metadata. */
function nativeShortProfileName(name){return nameOf(name).replace(/\s*\([^)]*\)/g,'').trim().split(/\s+/).slice(-2).join(' ');}
function nativeGroupName(id){return state.categories.find(c=>c.id===Number(id))?.name||'Nhóm gốc';}
function nativeGroupOptions(selected){return '<option value="">Tất cả nhóm</option>'+state.categories.map(c=>`<option value="${c.id}" ${Number(selected)===c.id?'selected':''}>${e(c.name)} · ${c.product_count} mẫu</option>`).join('');}
function nativeProductCard(p,rank){
  if(state.storefront)return storeProductCard(p,rank);
  const labBadge=(state.debug&&state.demo)?`<div class="lab-item-badge" style="margin:4px 8px 2px;padding:3px 6px;background:#f8fafc;border:1px dashed #94a3b8;border-radius:4px;font-family:monospace;font-size:11px;color:#334155;text-align:left;line-height:1.3;"><div><b style="color:#2563eb;">Mã ID:</b> ${e(p.raw_item_id||p.id)}</div>${p.p_click!==undefined?`<div><b style="color:#059669;">P(click):</b> ${p.p_click.toFixed(4)}</div>`:p.similarity!==undefined?`<div><b style="color:#d97706;">Cosine:</b> ${p.similarity.toFixed(4)}</div>`:''}</div>`:'';
  return `<article class="product-card native-card" data-category="${p.category_id}"><button class="heart-button ${state.wishlist.has(p.id)?'saved':''}" data-action="favorite" data-id="${p.id}" aria-label="${state.wishlist.has(p.id)?'Bỏ lưu':'Lưu'} ${e(p.name)}">${icon('heart')}</button><button class="product-card-main" data-action="product" data-id="${p.id}"><div class="product-image"><img loading="lazy" src="${e(p.image_url)}" alt="${e(p.name)}">${rank?`<span class="native-rank">${String(rank).padStart(2,'0')}</span>`:''}</div><div class="product-info"><div class="native-card-line"><span>${e(p.category_name||nativeGroupName(p.category_id))}</span></div><h3 class="product-name">${e(p.name)}</h3><span class="native-card-link">Xem sản phẩm ${icon('arrow')}</span></div></button>${labBadge}${state.route==='cart'?`<button class="quick-add" data-action="quick-add" data-id="${p.id}">${icon('cart')} Thêm vào giỏ</button>`:''}</article>`;
}
function nativeExplanation(result,compact=false){
  if(state.storefront)return storeExplanation(result,compact);
  state.recommendationContexts[result.meta.touchpoint]=result;
  return '';
}
function nativeAIInfo(el){
  if(state.storefront)return storeAIInfo(el);
  const touchpoint=el?.closest('.ai-explanation')?.dataset.touchpoint;
  const quality=(state.recommendationContexts[touchpoint]||state.recommendations)?.quality;
  openModal('Hiểu gợi ý của bạn',`<div class="help-prose native-help"><span class="native-kicker">AI, ĐƯỢC GIẢI THÍCH RÕ RÀNG</span><h3>Học từ lịch sử thật</h3><p>Hệ thống dùng mô hình đã huấn luyện trên Taobao, giữ nguyên ID, nhóm và lịch sử gốc. Các mẫu bạn xem, lưu, thêm giỏ hoặc mua thử được nối vào lịch sử để cập nhật gợi ý. Chọn nhóm chỉ lọc danh sách; thao tác này không tạo lượt xem giả.</p><h3>Kết quả tốt đến đâu?</h3>${quality?.available?`<p>Trên <b>${quality.sample_size.toLocaleString('vi-VN')} lượt hiển thị thử nghiệm</b>, AI xếp mẫu được nhấp cao hơn mẫu không được nhấp trong <b>${percent(quality.pairwise_ranking_percent)}</b> cặp so sánh. Cặp bằng điểm được tính một nửa.</p><p>Con số này <b>không có nghĩa</b> từng mẫu có ${percent(quality.pairwise_ranking_percent)} khả năng phù hợp. Chất lượng hiện ở mức có tín hiệu hữu ích, còn nhiều dư địa cải thiện. Phép đo lấy mẫu chưa đại diện cho toàn bộ dữ liệu.</p>`:'<p>Chưa có phép đo xếp hạng phù hợp cho lần gợi ý này. Hệ thống không tự tạo phần trăm phù hợp cho sản phẩm.</p>'}<h3>Vì sao các mẫu có hình học?</h3><p>Bộ Taobao-MM công khai đã ẩn danh dữ liệu, không cung cấp tên hoặc ảnh gốc. Vì vậy, mỗi mẫu có một mã tiếng Việt và hình nhận diện riêng. Những hình này không mô tả loại hàng, không được khôi phục từ ảnh hay vector AI. “Nhóm” giữ quan hệ phân nhóm gốc, không tự gán tên ngành hàng.</p><h3>Mua thử hoạt động thế nào?</h3><p>Bạn vẫn có thể thử giỏ hàng, voucher, đặt và hủy đơn. Giá, tồn kho, địa chỉ giao nhận và thanh toán ở đây là mô phỏng; không có giao dịch hoặc vận chuyển thật. Các mẫu chỉ có trong lịch sử nhưng thiếu đặc trưng đầy đủ sẽ không được đưa vào danh sách gợi ý mới.</p><p><a href="https://taobao-mm.github.io/" target="_blank" rel="noopener">Thông tin bộ dữ liệu Taobao-MM ↗</a></p></div>`,true);
}
async function renderNativeHome(version){
  if(state.storefront)return renderStoreHome(version);
  const count=state.source.product_count.toLocaleString('vi-VN');
  appHTML(`<div class="container page native-home experience-home"><section class="native-hero"><div class="native-hero-copy"><span class="native-kicker"><span class="status-dot"></span> KHÁM PHÁ TAOBAO · TRẢI NGHIỆM TIẾNG VIỆT</span><h1>Khám phá theo<br><em>dấu chân của bạn.</em></h1><p>Chọn hồ sơ, xem hoặc lưu một mẫu. Theo dõi lịch sử và những thay đổi thật trong gợi ý của bạn.</p><div class="native-hero-actions"><a class="primary" href="#discovery" id="native-discover">Khám phá gợi ý ${icon('arrow')}</a><button class="native-text-button" data-action="native-ai-info">Đọc câu chuyện gợi ý ${icon('sparkles')}</button></div><div class="native-hero-facts"><span><strong>${count}</strong> mẫu có đặc trưng gốc</span><span><strong>${state.source.group_count}</strong> nhóm khám phá</span><span><strong>8</strong> hồ sơ trải nghiệm</span></div></div><div class="native-hero-art" aria-label="Bộ thẻ nhận diện mẫu Taobao"><div class="native-orbit"></div><span class="native-art-note">MỘT THẾ GIỚI LỰA CHỌN</span><div id="native-hero-tiles"><div class="native-hero-placeholder">${icon('sparkles')}</div></div><span class="native-art-caption">Dữ liệu gốc. Góc nhìn mới.</span></div></section><div class="native-steps"><span><b>01</b> Chọn hồ sơ Taobao</span><i>→</i><span><b>02</b> Xem hoặc lưu mẫu</span><i>→</i><span><b>03</b> Theo dõi thay đổi</span></div><section id="native-evidence"></section><section id="native-context"></section><section class="section" id="discovery"><div class="section-title recommend-title"><div><span class="native-kicker">DÀNH CHO HÀNH TRÌNH CỦA BẠN</span><h2>Gợi ý hôm nay <span class="badge">KHÁM PHÁ</span></h2><p>Đang xếp hạng các lựa chọn mới từ dữ liệu gốc…</p></div><div class="recommend-status"><span class="status-dot"></span> Đang tải</div></div><div id="recommendation-explainer"></div><div class="native-feed-toolbar"><div><span class="native-dot"></span><strong>${state.user?'Góc khám phá của '+e(nativeShortProfileName(state.user.full_name)):'Góc khám phá mở'}</strong><small>Ưu tiên mẫu bạn chưa xem</small></div><label for="native-home-group">Lọc nhóm <select id="native-home-group">${nativeGroupOptions(state.homeGroup)}</select></label></div><div id="home-products"><div class="skeleton-grid">${Array(6).fill('<div class="skeleton"></div>').join('')}</div></div><div class="load-more"><button data-action="home-more">Khám phá thêm ${icon('arrow')}</button></div></section><section class="native-source-note"><span>${icon('layers')}</span><div><strong>Mỗi mẫu là một ID thật trong dữ liệu Taobao.</strong><p>Tên và ảnh gốc được ẩn danh. Mã mẫu và hình học giúp bạn nhận diện, lưu và tìm lại; không mô tả hàng hóa thật.</p></div><button data-action="native-ai-info">Tìm hiểu ${icon('arrow')}</button></section><section class="section native-groups"><div class="section-title"><div><span class="native-kicker">THEO MỘT HƯỚNG KHÁC</span><h2>Ghé qua các nhóm</h2><p>Giữ nguyên cách phân nhóm của dữ liệu gốc.</p></div><button data-action="catalog">Xem tất cả ${icon('arrow')}</button></div><div class="category-list">${state.categories.slice(0,8).map(c=>`<button class="native-group-card" data-category="${c.id}"><span class="native-group-icon">${String(c.id-10000).padStart(3,'0')}</span><strong>${e(c.name)}</strong><small>${c.product_count} mẫu ${icon('arrow')}</small></button>`).join('')}</div></section><div class="native-end-note">Một lần xem thêm, một tín hiệu mới. Gợi ý tiếp tục thay đổi cùng bạn.</div></div>`);
  // A normal hash link would change the SPA route; scroll without navigation.
  $('#native-discover').addEventListener('click',event=>{event.preventDefault();$('#discovery').scrollIntoView({behavior:'smooth'});});
  const result=await api('/recommendations?limit='+state.homeLimit+(state.homeGroup?'&category_id='+state.homeGroup:''));
  if(version!==state.routeVersion)return;
  state.recommendations=result;state.labResult=result;
  $('#home-products').innerHTML=result.items.length?productGrid(result.items,true):empty('Nhóm này tạm hết mẫu','Hãy chọn nhóm khác để tiếp tục khám phá.','home','Xem mọi nhóm');
  finishNativeComparison(result);nativeRecommendationLabel(result.meta);hydrate();refreshDebug(result.meta);refreshNativeEvidence();
}
function nativeRecommendationLabel(meta){
  if(state.storefront)return storeRecommendationLabel(meta);
  const title=$('#discovery .recommend-title p');if(title)title.textContent=state.homeGroup?`Sản phẩm nổi bật trong ${nativeGroupName(state.homeGroup)}.`:state.user?'Dựa trên hoạt động mua sắm gần đây của bạn.':'Những sản phẩm đang được quan tâm.';
  const badge=$('#discovery .badge');if(badge)badge.textContent='HÔM NAY';
  const status=$('.recommend-status');if(status)status.innerHTML='<span class="status-dot"></span> Đã cập nhật';
  const box=$('#recommendation-explainer');if(box)box.innerHTML=nativeExplanation(state.recommendations);
  const select=$('#native-home-group');if(select)select.value=state.homeGroup||'';
  const more=$('[data-action="home-more"]');if(more)more.hidden=!meta.has_more||state.homeLimit>=60;
  const art=$('#native-hero-tiles');if(art)art.innerHTML=state.recommendations.items.slice(0,3).map((p,i)=>`<div class="native-floating-card native-floating-${i}"><img src="${e(p.image_url)}" alt=""><div><strong>${e(p.name)}</strong><span>${e(p.category_name)}</span></div></div>`).join('');
}
async function renderNativeCatalog(version){
  if(state.storefront)return renderStoreCatalog(version);
  const params=routeParams(),q=params.get('q')||'',category=params.get('category_id')||'',page=Number(params.get('page')||1),sort=params.get('sort')||'relevance';
  appHTML(`<div class="container page native-catalog">${breadcrumb('Sản phẩm')}<div class="native-catalog-heading"><div><span class="native-kicker">MUA SẮM DỄ DÀNG</span><h1 class="page-title">${q?`Tìm “${e(q)}”`:category?e(nativeGroupName(category)):'Tất cả sản phẩm'}</h1><p class="page-subtitle">Tìm theo tên sản phẩm hoặc chọn danh mục phù hợp.</p></div><span class="native-count">${state.source.product_count.toLocaleString('vi-VN')}<small>sản phẩm</small></span></div><div class="native-catalog-tools"><label>Danh mục <select id="native-catalog-group">${nativeGroupOptions(category)}</select></label><div class="native-sort"><button data-sort="relevance" class="${sort==='relevance'?'active':''}">Phù hợp nhất</button><button data-sort="popular" class="${sort!=='relevance'?'active':''}">Phổ biến</button></div><small id="result-count"></small></div><div id="catalog-products"><div class="spinner"></div></div><div class="pagination" id="pagination"></div></div>`);
  const query=new URLSearchParams(params);query.set('sort',sort);query.set('page_size',24);
  const result=await api('/products?'+query);if(version!==state.routeVersion)return;state.products=result;
  $('#catalog-products').innerHTML=result.items.length?productGrid(result.items):empty('Chưa tìm thấy mẫu','Thử mã như TB-00001 hoặc tên như Nhóm 001.','catalog','Xem mọi mẫu','search');
  $('#result-count').textContent=result.total.toLocaleString('vi-VN')+' kết quả';
  const first=Math.max(1,Math.min(page-2,result.pages-4));
  $('#pagination').innerHTML=result.pages>1?`<button data-page="${page-1}" ${page<=1?'disabled':''} aria-label="Trang trước">‹</button>${Array.from({length:Math.min(5,result.pages)},(_,i)=>first+i).map(p=>`<button data-page="${p}" class="${p===page?'active':''}">${p}</button>`).join('')}<button data-page="${page+1}" ${page>=result.pages?'disabled':''} aria-label="Trang sau">›</button>`:'';hydrate();
}
async function openNativeProduct(id){
  if(state.storefront)return openStoreProduct(id);
  const version=++state.modalVersion,userId=state.user?.id;
  openModal('Chi tiết sản phẩm','<div class="loading-screen"><div class="spinner"></div></div>');
  const p=await api('/products/'+id);if(version!==state.modalVersion||userId!==state.user?.id)return;
  state.selectedProduct=p;state.quantity=1;
  openModal('Chi tiết sản phẩm',`<div class="native-detail product-detail"><div><div class="detail-image"><img src="${e(p.image_url)}" alt="Hình nhận diện ${e(p.name)}"></div><p class="native-image-caption">Hình nhận diện theo mã · không phải ảnh hàng hóa</p></div><div><span class="native-kicker">${e(p.category_name)} · TAOBAO</span><h1 class="detail-title">${e(p.name)}</h1><p class="native-detail-copy">Một mẫu trong dữ liệu gốc. Khám phá, lưu lại và xem AI tìm những lựa chọn gần với bạn như thế nào.</p><div class="native-detail-actions"><button class="primary" data-action="favorite" data-id="${p.id}">${icon('heart')} ${state.wishlist.has(p.id)?'Đã lưu mẫu':'Lưu mẫu yêu thích'}</button><button class="outline" data-category="${p.category_id}">Khám phá cùng nhóm ${icon('arrow')}</button></div><p class="native-view-receipt">${state.user?'Mở mẫu này gửi một lượt xem thật vào lịch sử của bạn.':'Chọn một hồ sơ để lưu lượt xem và trải nghiệm cá nhân hóa.'}</p><button class="native-result-link" data-action="native-result">${icon('sparkles')} Xem tác động trên gợi ý ${icon('arrow')}</button><div class="native-detail-facts"><span>Nhóm dữ liệu <strong>${e(p.category_name)}</strong></span><span>Thông tin hiển thị <strong>Mã ẩn danh tiếng Việt</strong></span></div><details class="native-try-buy"><summary>${icon('cart')} Trải nghiệm mua thử <span>Chỉ mô phỏng</span></summary><p>Giá và giao nhận dùng để thử chức năng, không phải thông tin bán hàng từ Taobao.</p><strong class="price">${money(p.price)} <small>giá mô phỏng</small></strong><div class="quantity"><button data-action="detail-minus" aria-label="Giảm số lượng">−</button><input id="detail-quantity" type="number" min="1" max="${Math.max(1,Math.min(p.stock,99))}" value="1" aria-label="Số lượng mua"><button data-action="detail-plus" aria-label="Tăng số lượng">+</button></div><div class="detail-actions"><button class="outline" data-action="add-product" ${p.stock<=0?'disabled':''}>${icon('cart')} Thêm giỏ thử</button><button class="primary" data-action="buy-product" ${p.stock<=0?'disabled':''}>Mua thử ngay</button></div>${!p.source_feature_complete?'<p>Mẫu chỉ có trong lịch sử, thiếu đặc trưng đầy đủ để mua thử hoặc gợi ý mới.</p>':''}</details></div></div><section class="detail-similar"><div class="native-similar-heading"><h3>Tiếp nối khám phá</h3><span>Gần nhau theo dữ liệu AI</span></div><div id="similar-products"><div class="spinner"></div></div></section>`);
  if(state.user){captureNativeInteraction(p,'click');await post('/recommendations/behavior/'+id);if(version!==state.modalVersion||userId!==state.user?.id)return;}
  const related=await api('/recommendations?touchpoint=similar&product_id='+id+'&limit=12');if(version!==state.modalVersion||userId!==state.user?.id)return;
  $('#similar-products').innerHTML=nativeExplanation(related,true)+productGrid(related.items);state.labResult=related;hydrate();refreshDebug(related.meta);
}
function nativeLabInfo(){
  if(!(state.demo&&state.debug))return;
  openModal('MUSE Lab · Dữ liệu gốc và suy luận',`<div class="help-prose"><h3>Checkpoint được giữ nguyên</h3><p>ID, nhóm 206, trường địa lý 213/214, vector SCL và chuỗi 1.000 tương tác dùng đúng ánh xạ Taobao gốc. Mô hình MUSE xử lý lịch sử và dự đoán P(click). Không huấn luyện lại.</p><h3>Thứ tự kết quả</h3><p>Chấm toàn bộ ${state.source.product_count} mẫu có đặc trưng đầy đủ, theo lô 64 trên CPU. Sắp xếp P(click) giảm dần, giữ ID làm khóa phụ khi bằng điểm. Không có điểm cộng danh mục, giá, ảnh hay demo_interest. Trang chủ loại mẫu đã xem trong lịch sử gốc và hoạt động thật để tạo khám phá mới; điểm checkpoint giữ nguyên. Tìm kiếm và lọc nhóm lấy từ cùng thứ hạng này. Kết quả được lưu đệm tối đa 8 phiên lịch sử, hết hiệu lực khi có hành vi mới.</p><h3>Giới hạn</h3><p>${state.source.history_only_count} mẫu chỉ đủ ID và nhóm từ chuỗi lịch sử được giữ để mô hình đọc lịch sử; không làm ứng viên mới. Gợi ý gần nhau dùng cosine của vector SCL, chưa được đánh giá bằng nhãn tương đồng sản phẩm. Tên, ảnh, giá và ngành hàng minh họa từ DummyJSON được gắn qua bảng product_presentations, không đổi các trường đầu vào MUSE. Việc gắn ngành hàng không phục hồi ngữ nghĩa của nhóm gốc; chưa có nhãn kiểm chứng độ phù hợp với hàng hóa trong ảnh. Bản commerce lọc theo loại sản phẩm minh họa và chỉ giữ ID có điểm cao nhất cho mỗi cặp tên/ảnh. Lịch sử ngữ cảnh chỉ bắt đầu sau mốc triển khai quy tắc mới, không diễn giải lượt xem mã ẩn danh cũ thành sở thích hàng hóa. API presentation_policy=original vẫn trả thứ hạng ID gốc để đối chiếu. Xem AUC, GAUC và chỉ số nền trong bảng đánh giá.</p><button class="primary" data-action="store-original-ranking">Xem thứ hạng ID gốc trước lớp lọc</button></div>`,true);
}

function nativeMiniCards(items,limit=4){
  return `<div class="native-mini-grid">${items.slice(0,limit).map(p=>`<button class="native-mini" data-action="product" data-id="${p.id}"><img loading="lazy" src="${e(p.image_url)}" alt=""><span><strong>${e(p.name)}</strong><small>${e(p.category_name||nativeGroupName(p.category_id))}</small></span>${icon('arrow')}</button>`).join('')}</div>`;
}
function nativeEvidenceHTML(summary){
  if(state.storefront)return storeEvidenceHTML(summary);
  if(!state.user)return `<div class="native-start"><div><span class="native-kicker">MỖI LỊCH SỬ, MỘT GÓC NHÌN</span><h2>Chọn một hồ sơ để bắt đầu.</h2><p>Những hồ sơ này có lịch sử Taobao khác nhau. Chọn hai hồ sơ để quan sát danh sách gợi ý của từng người.</p></div><div class="native-profile-choices">${state.profiles.length?state.profiles.map(p=>`<button data-action="demo-login" data-id="${p.id}"><span>${e(nativeShortProfileName(p.full_name))}</span>${icon('arrow')}</button>`).join(''):'<button class="primary" data-action="login">Đăng nhập để khám phá</button>'}</div><small>${state.profiles.length?'<button class="native-compare-link" data-action="native-compare-profiles">So sánh hai hồ sơ bằng AI →</button>':''} Tên và ảnh hồ sơ là minh họa tiếng Việt; chuỗi hành vi giữ nguyên từ dữ liệu gốc.</small></div>`;
  const maximum=Math.max(1,...summary.top_groups.map(g=>g.events));
  return `<div class="native-profile-story"><section class="native-history-story"><div class="native-story-heading"><div><span class="native-kicker">LỊCH SỬ TẠO NÊN GÓC NHÌN</span><h2>Hồ sơ của ${e(nativeShortProfileName(state.user.full_name))}</h2></div><button data-action="native-profile">Đổi hồ sơ ${icon('users')}</button></div><div class="native-story-counts"><span><b>${summary.original_events.toLocaleString('vi-VN')}</b> lượt gốc</span><span><b>${summary.live_events}</b> tương tác trên web</span><span><b>${summary.top_groups.length?summary.top_groups[0].name:'Bắt đầu mới'}</b> ${summary.top_groups.length?'xuất hiện nhiều nhất':'chưa có lịch sử'}</span></div>${summary.top_groups.length?`<div class="native-interest-bars">${summary.top_groups.slice(0,4).map(g=>`<button data-action="native-group" data-group="${g.id}" title="Lọc ${e(g.name)}; không tạo lượt xem"><span>${e(g.name)}</span><i><b style="width:${Math.round(g.events/maximum*100)}%;background:hsl(${Math.round(g.id*137.508)%360} 28% 55%)"></b></i><small>${g.events} lượt</small></button>`).join('')}</div><p class="native-evidence-caption">${summary.imported?'Số lượt trong hồ sơ gốc':'Số lượt tương tác trên web'}, không phải % phù hợp hoặc mức đóng góp của nhóm vào điểm AI.</p>${state.demo?'<button class="native-compare-link" data-action="native-compare-profiles">So sánh hai hồ sơ bằng AI →</button>':''}`:'<p class="native-story-empty">Bạn chưa có lịch sử Taobao. Xem và lưu mẫu yêu thích để bắt đầu tạo lịch sử riêng.</p>'}</section><section class="native-activity-story"><div class="native-story-heading"><div><span class="native-kicker">DẤU CHÂN GẦN ĐÂY</span><h2>${summary.recent.length?'Bạn vừa khám phá':'Thử từ một mẫu quen thuộc'}</h2></div><span class="native-live-indicator"><span class="status-dot"></span> Cập nhật thật</span></div>${summary.recent.length?`<div class="native-activity-list">${summary.recent.slice(0,3).map(p=>`<button data-action="product" data-id="${p.id}"><img src="${e(p.image_url)}" alt=""><span><small>${e(p.action_label)} · ${e(p.category_name)}</small><strong>${e(p.name)}</strong></span>${icon('arrow')}</button>`).join('')}</div>`:summary.history_examples.length?`<p>Đây là các sản phẩm có thật trong chuỗi gốc. Mở một sản phẩm để quan sát gợi ý tiếp nối.</p>${nativeMiniCards(summary.history_examples,2)}`:'<p class="native-story-empty">Một lượt xem đầu tiên sẽ xuất hiện tại đây. Bạn có thể bắt đầu ngay ở danh sách gợi ý bên dưới.</p>'}
</section></div>`;
}
function captureNativeInteraction(product,action){
  if(!state.native||!product)return;
  if(state.storefront)storeSetFocus(product);
  if(!state.user)return;
  state.nativeChange={userId:state.user.id,group:state.homeDisplayCategory||state.homeGroup||null,action,product,
    before:(state.recommendations?.items||[]).slice(0,12),beforeContext:storeContextKey(state.recommendations?.meta),pending:true};
  renderNativeContext();
}
function finishNativeComparison(result){
  const change=state.nativeChange;
  if(!change||change.userId!==state.user?.id||(!state.storefront&&change.group!==(state.homeDisplayCategory||state.homeGroup||null))||!change.pending)return;
  if(state.storefront){
    const key=p=>p.template_id??p.id,after=result.items.slice(0,12),oldIds=new Set(change.before.map(key)),newIds=new Set(after.map(key));
    change.after=after;change.newItems=after.filter(p=>!oldIds.has(key(p)));change.removed=change.before.filter(p=>!newIds.has(key(p)));
    change.moved=after.filter((p,i)=>oldIds.has(key(p))&&change.before.findIndex(q=>key(q)===key(p))!==i).length;
    change.context=result.meta.merchandise_context;change.contextChanged=change.beforeContext!==storeContextKey(result.meta);
    change.modelUsed=result.meta.model_used;change.pending=false;renderNativeContext();return;
  }
  const after=result.items.slice(0,12),oldIds=new Set(change.before.map(p=>p.id)),newIds=new Set(after.map(p=>p.id));
  change.after=after;change.newItems=after.filter(p=>!oldIds.has(p.id));change.removed=change.before.filter(p=>!newIds.has(p.id));
  change.moved=after.filter((p,i)=>oldIds.has(p.id)&&change.before.findIndex(q=>q.id===p.id)!==i).length;
  change.modelUsed=result.meta.model_used;change.pending=false;
  renderNativeContext();
}
function nativeComparisonHTML(){
  const change=state.nativeChange;if(!change||change.userId!==state.user?.id)return '';
  if(state.storefront)return storeChangeHTML(change);
  const actions={click:'xem',favorite:'lưu',add_to_cart:'thêm giỏ'};
  return `<section class="native-change-card" aria-live="polite"><div class="native-change-icon">${icon('sparkles')}</div><div class="native-change-content"><span class="native-kicker">SAU KHI BẠN ${e((actions[change.action]||'khám phá').toUpperCase())} ${e(change.product.name)}</span><h3>${change.failed?'Chưa tải được danh sách mới':change.pending?'Đang cập nhật gợi ý…':!change.modelUsed?'AI tạm thời chưa khả dụng':change.before.length?`${change.newItems.length} sản phẩm mới trong ${change.after.length} gợi ý đầu`:'Lịch sử của bạn đã được cập nhật'}</h3><p>${change.failed?'Tương tác đã được lưu. Danh sách bên dưới thuộc lần tải trước.':change.pending?'Sản phẩm vừa chọn đang được thêm vào lịch sử.':!change.modelUsed?'Lượt tương tác vẫn được lưu. Danh sách hiện dùng thứ tự danh mục.':change.before.length?`${change.moved} sản phẩm thay đổi vị trí. So sánh với danh sách trước thao tác, trong cùng bộ lọc.`:'Xem thêm một sản phẩm để so sánh danh sách trước và sau.'}</p>${change.failed?'<button class="native-compare-link" data-action="native-refresh">Tải lại gợi ý →</button>':''}${!change.pending&&change.modelUsed?`<div class="native-before-after"><div><small>TRƯỚC THAO TÁC</small>${nativeMiniCards(change.before,3)}</div><div><small>SAU THAO TÁC</small>${nativeMiniCards(change.after,3)}</div></div><p class="native-evidence-caption">Danh sách đổi theo lịch sử và việc bỏ qua sản phẩm đã xem. Đây không phải phép đo độ chính xác; model không được huấn luyện lại.</p>`:''}</div></section>`;
}
function renderNativeContext(){
  const box=$('#native-context');if(!box)return;
  if(state.storefront){box.innerHTML='';return;}
  const latest=state.nativeExperience?.recent?.[0];
  box.innerHTML=nativeComparisonHTML()+(latest?`<section class="native-continuation"><div class="native-story-heading"><div><span class="native-kicker">TIẾP NỐI LỰA CHỌN VỪA RỒI</span><h2>Từ ${e(latest.name)}, khám phá tiếp.</h2><p>${state.nativeNeighbours?.id===latest.id&&state.nativeNeighbours?.used?'Những sản phẩm gần nhau theo đặc trưng AI, tách riêng với danh sách xếp hạng theo lịch sử bên dưới.':'Khám phá tiếp từ sản phẩm vừa chọn. Trạng thái gợi ý được cập nhật khi tải xong.'}</p></div><button data-action="product" data-id="${latest.id}">Xem lại sản phẩm ${icon('arrow')}</button></div><div id="native-neighbours">${state.nativeNeighbours?.userId===state.user?.id&&state.nativeNeighbours?.id===latest.id?(state.nativeNeighbours.used?nativeMiniCards(state.nativeNeighbours.items,4):'<p class="native-evidence-caption">Gợi ý tiếp nối AI tạm thời chưa khả dụng.</p>'):'<p class="native-evidence-caption">Đang tìm các lựa chọn gần nhau…</p>'}</div></section>`:'');
  hydrate();
}
async function refreshNativeEvidence(){
  if(!state.native||state.route!=='home')return;
  const version=state.routeVersion,userId=state.user?.id,request=(state.nativeEvidenceVersion||0)+1;state.nativeEvidenceVersion=request;
  try{
    const summary=await api('/recommendations/experience');
    if(version!==state.routeVersion||userId!==state.user?.id||request!==state.nativeEvidenceVersion)return;
    state.nativeExperience=summary;const box=$('#native-evidence');if(box)box.innerHTML=nativeEvidenceHTML(summary);renderNativeContext();hydrate();
    if(state.storefront)return;
    const latest=summary.recent[0];if(!latest)return;
    if(state.nativeNeighbours?.userId===userId&&state.nativeNeighbours?.id===latest.id)return;
    const result=await api('/recommendations?touchpoint=similar&product_id='+latest.id+'&limit=4');
    if(version!==state.routeVersion||userId!==state.user?.id||request!==state.nativeEvidenceVersion)return;
    state.nativeNeighbours={id:latest.id,userId,items:result.items,used:result.meta.model_used};renderNativeContext();const target=$('#native-neighbours');
    if(target){target.innerHTML=!result.meta.model_used?'<p class="native-evidence-caption">Gợi ý tiếp nối AI tạm thời chưa khả dụng.</p>':result.items.length?nativeMiniCards(result.items,4):'<p class="native-evidence-caption">Chưa có sản phẩm gần nhau trong danh mục.</p>';hydrate();}
  }catch{
    if(version!==state.routeVersion||userId!==state.user?.id||request!==state.nativeEvidenceVersion)return;
    const box=$('#native-evidence');if(box&&!box.innerHTML)box.innerHTML='<p class="native-evidence-caption">Phần lịch sử tạm thời chưa tải được. Bạn vẫn có thể khám phá các gợi ý bên dưới.</p>';
    const target=$('#native-neighbours');if(target)target.innerHTML='<p class="native-evidence-caption">Gợi ý tiếp nối tạm thời chưa tải được.</p>';
  }
}
function nativeUpdating(busy){
  const box=$('#home-products');if(box)box.setAttribute('aria-busy',String(busy));
  const status=$('.recommend-status');if(status&&busy)status.innerHTML='<span class="status-dot"></span> Đang cập nhật…';
}

function openNativeProfileComparison(){
  const version=++state.modalVersion;
  const left=state.profiles.some(p=>p.id===state.user?.id)?state.user.id:state.profiles[0]?.id;
  const right=state.profiles.find(p=>p.id!==left)?.id;
  const options=id=>state.profiles.map(p=>`<option value="${p.id}" ${p.id===id?'selected':''}>${e(nameOf(p.full_name))}</option>`).join('');
  openModal('Hai lịch sử. Hai góc khám phá.',`<div class="native-compare-intro"><span class="native-kicker">QUAN SÁT CÁ NHÂN HÓA</span><p>Cùng danh mục, cùng mô hình; mỗi hồ sơ có lịch sử riêng. Sản phẩm đã xem được loại riêng theo từng hồ sơ. So sánh không tạo tương tác hay đổi hồ sơ đang đăng nhập.</p></div><div class="native-compare-selects"><label>Hồ sơ thứ nhất<select id="native-compare-left">${options(left)}</select></label><label>Hồ sơ thứ hai<select id="native-compare-right">${options(right)}</select></label></div><div id="native-profile-comparison"><div class="loading-screen"><div class="spinner"></div><p>AI đang chuẩn bị hai danh sách…</p></div></div>`);
  loadNativeProfileComparison(version);
}
async function loadNativeProfileComparison(version=state.modalVersion){
  const left=$('#native-compare-left')?.value,right=$('#native-compare-right')?.value,request=(state.nativeCompareVersion||0)+1;
  state.nativeCompareVersion=request;
  const target=$('#native-profile-comparison');if(!target)return;
  if(left===right){target.innerHTML='<p class="native-evidence-caption">Chọn hai hồ sơ khác nhau để quan sát cá nhân hóa.</p>';return;}
  target.innerHTML='<div class="loading-screen"><div class="spinner"></div><p>AI đang xếp hạng hai hồ sơ…</p></div>';
  try{
    const result=await api('/recommendations/compare-profiles?left='+left+'&right='+right);
    if(version!==state.modalVersion||request!==state.nativeCompareVersion||!$('#modal').open)return;
    const used=result.left.model_used&&result.right.model_used;
    target.innerHTML=`<div class="native-compare-result"><strong>${used?`${result.shared_items} sản phẩm trùng trong hai danh sách đầu`:'Gợi ý AI tạm thời chưa khả dụng'}</strong><p>${used?'Khác biệt đến từ hồ sơ và lịch sử, cùng quy tắc bỏ qua sản phẩm đã xem; đây không phải tỷ lệ chính xác.':'Hai danh sách hiện dùng thứ tự danh mục. Chưa thể đánh giá khác biệt cá nhân hóa.'}</p></div><div class="native-profile-columns">${[result.left,result.right].map(side=>`<section><div class="native-story-heading"><div><h3>${e(nameOf(side.profile.full_name))}</h3><small>${side.history_length.toLocaleString('vi-VN')} hành vi đầu vào · ${side.model_used?'AI xếp hạng':'Theo danh mục'}</small></div></div>${nativeMiniCards(side.items,6)}</section>`).join('')}</div><p class="native-evidence-caption">Trọng số được giữ nguyên. Danh sách dùng tối đa 12 sản phẩm để tính phần trùng; hiển thị 6 sản phẩm đầu mỗi bên.</p>`;hydrate();
  }catch(error){if(version===state.modalVersion&&request===state.nativeCompareVersion)target.innerHTML=`<p class="native-evidence-caption">${e(error.message)}</p>`;}
}
