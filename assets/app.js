'use strict';
const storeKey = 'pimpmyphone-biapod-guide-v1';
const boxes = [...document.querySelectorAll('[data-step-check]')];
let saved = [];
try { saved = JSON.parse(localStorage.getItem(storeKey) || '[]'); } catch (_) {}
if (!Array.isArray(saved)) saved = [];
boxes.forEach(box => { box.checked = saved.includes(box.dataset.stepCheck); });
function updateProgress() {
  const done = boxes.filter(box => box.checked).map(box => box.dataset.stepCheck);
  try { localStorage.setItem(storeKey, JSON.stringify(done)); } catch (_) {}
  document.querySelectorAll('[data-progress-text]').forEach(el => { el.textContent = `${done.length} / ${boxes.length}`; });
  document.querySelector('[data-progress-bar]').style.width = `${done.length / boxes.length * 100}%`;
  document.querySelectorAll('.step-nav a').forEach(a => a.classList.toggle('done', done.includes(a.hash.slice(1))));
  document.querySelector('[data-mobile-progress]').textContent = `${done.length} di ${boxes.length} tappe completate`;
}
boxes.forEach(box => box.addEventListener('change', updateProgress));
updateProgress();
let toastTimer;
function toast(message) {
  const el = document.querySelector('.toast'); el.textContent = message; el.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.hidden = true; }, 3500);
}
document.querySelector('[data-reset]').addEventListener('click', () => {
  if (window.confirm('Azzerare le tappe completate della guida? I file sul telefono non vengono modificati.')) {
    boxes.forEach(box => { box.checked = false; }); updateProgress(); toast('Percorso azzerato');
  }
});
document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
  const text = document.getElementById(button.dataset.copy).textContent;
  try {
    if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
    else {
      const temp = document.createElement('textarea'); temp.value = text; temp.style.position = 'fixed'; temp.style.opacity = '0';
      document.body.append(temp); temp.select();
      const copied = document.execCommand('copy'); temp.remove(); if (!copied) throw new Error('Copy unavailable');
    }
    button.textContent = 'Copiato ✓'; setTimeout(() => { button.textContent = 'Copia'; }, 2000);
  } catch (_) { toast('Seleziona e copia il comando manualmente.'); }
}));
document.querySelectorAll('[data-tab-group]').forEach(group => {
  const tabs = [...group.querySelectorAll('[role=tab]')];
  function select(tab) {
    tabs.forEach(item => {
      const selected = item === tab; item.setAttribute('aria-selected', String(selected)); item.tabIndex = selected ? 0 : -1;
      document.getElementById(item.getAttribute('aria-controls')).hidden = !selected;
    });
  }
  tabs.forEach((tab, i) => {
    tab.addEventListener('click', () => select(tab));
    tab.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const index = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (i + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      select(tabs[index]); tabs[index].focus();
    });
  });
});
const selector = document.querySelector('#mobile-step');
selector.addEventListener('change', () => { location.hash = selector.value; });
const steps = [...document.querySelectorAll('.step[id]')];
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    for (const entry of entries) if (entry.isIntersecting) {
      const current = entry.target.id;
      document.querySelectorAll('.step-nav a').forEach(a => {
        const active = a.hash === `#${current}`; a.classList.toggle('active', active);
        if (active) a.setAttribute('aria-current', 'step'); else a.removeAttribute('aria-current');
      });
      selector.value = current;
    }
  }, {rootMargin:'-10% 0px -65% 0px', threshold:0});
  steps.forEach(step => observer.observe(step));
}
const search = document.querySelector('#faq-search');
search.addEventListener('input', () => {
  const query = search.value.toLocaleLowerCase('it').trim(); let count = 0;
  document.querySelectorAll('.faq').forEach(faq => {
    const match = faq.textContent.toLocaleLowerCase('it').includes(query); faq.hidden = !match;
    if (match) count++; if (query && match) faq.open = true;
  });
  document.querySelector('[data-no-results]').hidden = count > 0;
});
document.querySelector('[data-print]').addEventListener('click', () => {
  document.querySelectorAll('.faq').forEach(faq => { faq.hidden = false; faq.open = true; }); window.print();
});
const demoPlay = document.querySelector('.demo-play');
demoPlay.addEventListener('click', () => {
  const paused = demoPlay.getAttribute('aria-pressed') === 'true';
  demoPlay.setAttribute('aria-pressed', String(!paused)); demoPlay.textContent = paused ? '▶' : 'Ⅱ';
  demoPlay.setAttribute('aria-label', paused ? 'Avvia la demo visiva' : 'Metti in pausa la demo visiva');
  document.querySelector('[data-demo-status]').textContent = paused ? 'Anteprima illustrata · nessun audio' : 'Demo visiva in riproduzione · nessun audio';
});
