(() => {
  const $ = (id) => document.getElementById(id);
  const state = { events: [], favorites: new Set(JSON.parse(localStorage.getItem('noh-favorites') || '[]')), favoritesOnly: false };
  const prefectureCodeOrder = new Map([
    '北海道','青森県','岩手県','宮城県','秋田県','山形県','福島県','茨城県','栃木県','群馬県',
    '埼玉県','千葉県','東京都','神奈川県','新潟県','富山県','石川県','福井県','山梨県','長野県',
    '岐阜県','静岡県','愛知県','三重県','滋賀県','京都府','大阪府','兵庫県','奈良県','和歌山県',
    '鳥取県','島根県','岡山県','広島県','山口県','徳島県','香川県','愛媛県','高知県','福岡県',
    '佐賀県','長崎県','熊本県','大分県','宮崎県','鹿児島県','沖縄県'
  ].map((name, index) => [name, index + 1]));
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const dateText = (value) => { const d = new Date(`${value}T00:00:00`); return Number.isNaN(+d) ? value : `${d.getFullYear()}年${d.getMonth()+1}月${d.getDate()}日`; };
  const weekday = (value) => { const d = new Date(`${value}T00:00:00`); return Number.isNaN(+d) ? '' : '日月火水木金土'[d.getDay()] + '曜日'; };
  function render() {
    const q = $('query').value.trim().toLocaleLowerCase('ja');
    const pref = $('prefecture').value;
    const dateFrom = $('date-from').value;
    const dateTo = $('date-to').value;
    let items = state.events.filter(e => {
      const text = [e.title,e.venue,e.prefecture,e.memo,e.source_name].join(' ').toLocaleLowerCase('ja');
      return (!q || text.includes(q)) && (!pref || e.prefecture === pref) &&
        (!state.favoritesOnly || state.favorites.has(e.id)) &&
        (!dateFrom || e.date >= dateFrom) && (!dateTo || e.date <= dateTo);
    });
    items.sort((a,b) => (a.date.localeCompare(b.date) || a.start_time.localeCompare(b.start_time) || a.title.localeCompare(b.title,'ja')) * ($('sort').value === 'date-desc' ? -1 : 1));
    $('result-count').textContent = `${items.length.toLocaleString('ja-JP')} 件の公演`;
    $('favorite-count').textContent = state.favorites.size;
    $('empty').hidden = items.length !== 0;
    $('results').innerHTML = items.map(e => `<article class="event-card"><div class="event-top"><time class="event-date">${escapeHtml(dateText(e.date))}</time><span class="event-weekday">${escapeHtml(weekday(e.date))}</span>${e.prefecture ? `<span class="event-pref">${escapeHtml(e.prefecture)}</span>` : ''}</div><button class="favorite-button ${state.favorites.has(e.id)?'active':''}" type="button" data-fav="${escapeHtml(e.id)}" aria-label="お気に入りに${state.favorites.has(e.id)?'登録済み':'登録'}" aria-pressed="${state.favorites.has(e.id)}">${state.favorites.has(e.id)?'♥':'♡'}</button><h2 class="event-title">${escapeHtml(e.title)}</h2><div class="event-meta">${e.venue?`<span><b class="meta-icon">⌖</b>${escapeHtml(e.venue)}</span>`:''}${e.start_time?`<span><b class="meta-icon">◷</b>${escapeHtml(e.start_time)} 開演</span>`:''}</div>${e.url?`<a class="event-link" href="${escapeHtml(e.url)}" target="_blank" rel="noopener noreferrer">公演情報・主催者サイト ↗</a>`:''}</article>`).join('');
    $('data-note').textContent = state.generatedAt ? `情報更新：${new Date(state.generatedAt).toLocaleString('ja-JP')}` : '公演情報はまだありません。管理者が収集処理を実行すると、ここに表示されます。';
  }
  document.addEventListener('click', e => {
    const button = e.target.closest('[data-fav]'); if (!button) return;
    const id = button.dataset.fav; state.favorites.has(id) ? state.favorites.delete(id) : state.favorites.add(id);
    localStorage.setItem('noh-favorites', JSON.stringify([...state.favorites])); render();
  });
  ['query','prefecture','date-from','date-to','sort'].forEach(id => $(id).addEventListener(id === 'query' ? 'input' : 'change', render));
  $('clear').addEventListener('click', () => { $('query').value=''; $('prefecture').value=''; $('date-from').value=''; $('date-to').value=''; render(); });
  $('favorites-toggle').addEventListener('click', () => { state.favoritesOnly = !state.favoritesOnly; $('favorites-toggle').setAttribute('aria-pressed', state.favoritesOnly); render(); });
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('./sw.js').catch(() => {});
  fetch('shows.json', { cache: 'no-store' }).then(r => { if (!r.ok) throw new Error('公演データを読み込めません'); return r.json(); }).then(data => {
    state.events = Array.isArray(data.events) ? data.events : []; state.generatedAt = data.generatedAt;
    let favoritesMigrated = false;
    for (const event of state.events) {
      if (event.previousId && state.favorites.delete(event.previousId)) {
        state.favorites.add(event.id);
        favoritesMigrated = true;
      }
    }
    if (favoritesMigrated) localStorage.setItem('noh-favorites', JSON.stringify([...state.favorites]));
    [...new Set(state.events.map(e => e.prefecture).filter(Boolean))]
      .sort((a,b) => (prefectureCodeOrder.get(a) ?? Infinity) - (prefectureCodeOrder.get(b) ?? Infinity) || a.localeCompare(b,'ja'))
      .forEach(name => $('prefecture').add(new Option(name,name)));
    render();
  }).catch(() => { $('result-count').textContent='公演データを読み込めません'; $('data-note').textContent='ローカルサイトサーバーから開いてください。 python -m local_noh serve'; });
})();
