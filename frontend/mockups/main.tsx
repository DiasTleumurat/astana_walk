import ReactDOM from 'react-dom/client';
import App from '../src/App';
import '@fontsource-variable/manrope';
import 'leaflet/dist/leaflet.css';
import '../src/styles.css';
import './palettes.css';
import catalog from '../../data/poi.json';

const theme = new URLSearchParams(location.search).get('theme');
const logoFonts = {outfit:'Outfit',fjalla:'Fjalla One',gothic:'Special Gothic Expanded One'};
const logoFont = new URLSearchParams(location.search).get('font') || 'outfit';
document.documentElement.dataset.logoFont = logoFont in logoFonts ? logoFont : 'outfit';
if (theme === 'light' || theme === 'dark') {
  localStorage.setItem('astana-walk-theme', theme);
  // This isolated design preview uses a fixed sample from the local catalog.
  const parks = catalog.pois.filter(p => p.categories.includes('park'))
    .sort((a,b) => Math.hypot(a.latitude-51.1061652, (a.longitude-71.4165705)*.63) - Math.hypot(b.latitude-51.1061652, (b.longitude-71.4165705)*.63)).slice(0,3);
  const recommendations = parks.map((p,i) => ({
    ...p, poi_id:p.id, category:'park', category_label:'Парк',
    distance_m:[350,870,1200][i], walk_minutes:[5,12,17][i], visit_minutes:30, total_minutes:[35,42,47][i],
    reason:'Зелёное пространство для неспешной прогулки и небольшой паузы среди города.',
    suggested_activity:'Пройдитесь по дорожкам в своём темпе и найдите место для отдыха.',
    opening_status:'unknown', opening_hours_raw:null, sources:[], fact_refs:[], warnings:[], wheelchair:null, sockets:null,
    collected_at:catalog.collected_at,
  }));
  const originalFetch = window.fetch.bind(window);
  window.fetch = async (input, init) => {
    if(String(input).includes('/api/recommendations')) return Response.json({request_id:'palette-preview',mode:'demo',generation_mode:'template',retrieval_mode:'keyword',recommendations,warnings:[],empty_reason:null,candidates_count:3,applied_constraints:{minutes:60,radius_m:2500,interests:[]}});
    if(String(input).includes('/api/dataset/status')) return Response.json({count:catalog.pois.length,collected_at:catalog.collected_at,retrieval_mode:'keyword',categories:{}});
    return originalFetch(input,init);
  };
  ReactDOM.createRoot(document.getElementById('root')!).render(<App/>);
} else {
  document.documentElement.dataset.gallery='true';
  ReactDOM.createRoot(document.getElementById('root')!).render(<div className="palette-gallery">
    <header><div><span className="eyebrow">ASTANA WALK / ЦВЕТОВЫЕ МАКЕТЫ</span><h1>Два настроения одной прогулки</h1><p>Текущий интерфейс в ваших палитрах. Демонстрационные места и время в пути.</p></div><span className="edition">01 / 02</span></header>
    <label className="logo-font-picker">Шрифт логотипа <select defaultValue={logoFont} onChange={e=>{const url=new URL(location.href);url.searchParams.set('font',e.target.value);location.href=url.href;}}>{Object.entries(logoFonts).map(([key,name])=><option key={key} value={key}>{name}</option>)}</select></label>
    <div className="preview-grid">{(['light','dark'] as const).map((t,i)=><section className={'preview '+t} key={t}>
      <div className="preview-title"><div><small>0{i+1}</small><h2>{t==='light'?'Светлая · Шалфей':'Тёмная · Лес'}</h2></div><a href={'?theme='+t+'&font='+logoFont} target="_blank">Открыть макет ↗</a></div>
      <div className="swatches">{(t==='light'?['#658864','#B7B78A','#DDDDDD','#EEEEEE']:['#181C14','#3C3D37','#697565','#ECDFCC']).map(c=><span key={c}><i style={{background:c}}/>{c}</span>)}</div>
      <div className="frame"><iframe title={t==='light'?'Светлая тема':'Тёмная тема'} src={'?theme='+t+'&font='+logoFont}/></div>
    </section>)}</div><p className="gallery-note">Откройте макет целиком, чтобы посмотреть мобильную версию и переключить тему. Подбор мест здесь демонстрационный.</p>
  </div>);
}
