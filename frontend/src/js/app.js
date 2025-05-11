// app specific 

// alpine.js
import Alpine from 'alpinejs';
window.Alpine = Alpine;
Alpine.start();

(function () {
  const xhr = new XMLHttpRequest();
  xhr.open('GET', '/icons/icons.svg', true);
  xhr.onload = function () {
    if (xhr.status === 200) {
      const div = document.createElement('div');
      div.style.display = 'none';
      div.innerHTML = xhr.responseText;
      document.body.insertBefore(div, document.body.firstChild);
    }
  };
  xhr.send();
})();
