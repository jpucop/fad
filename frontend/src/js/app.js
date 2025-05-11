// app.js

// alpine.js
import Alpine from 'alpinejs';
window.Alpine = Alpine;
Alpine.start();

// Load SVG sprite
(function () {
  const spriteUrl = '/icons/icons.svg';
  const xhr = new XMLHttpRequest();
  xhr.open('GET', spriteUrl, true);
  xhr.onload = function () {
    if (xhr.status === 200) {
      const div = document.createElement('div');
      div.style.display = 'none';
      div.innerHTML = xhr.responseText;
      document.body.insertBefore(div, document.body.firstChild);
      console.log('✅ SVG sprite loaded successfully');
    } else {
      console.error(`❌ Failed to load SVG sprite: ${xhr.status} ${xhr.statusText}`);
    }
  };
  xhr.onerror = function () {
    console.error('❌ Network error while loading SVG sprite');
  };
  xhr.send();
})();